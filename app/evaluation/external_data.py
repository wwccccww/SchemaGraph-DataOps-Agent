"""获取、生成并执行外部评测数据。

导入本模块不会发网络请求，也不会调用模型。Gold 结果只写进报告痕迹。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, TypedDict

import asyncpg

from app.evaluation.bird import (
    BIRD_SOURCE_VERSION,
    CASES_PATH,
    CHECKSUMS_PATH,
    DATABASE_DRIVE_ID,
    DATABASE_ZIP_SHA256,
    DATASET_COMMIT,
    EXCLUSIONS_PATH,
    QUESTIONS_SHA256,
    build_bird_cases,
    dump_bird_cases,
    load_bird_questions,
    load_database_checksums,
    materialize_bird_case,
)
from app.evaluation.external_report import (
    ExternalSource,
    GoldTrace,
    build_external_summary,
    write_external_report,
)
from app.evaluation.tpcds import (
    KIT_COMMIT,
    KIT_REPO,
    TPCDS_SOURCE_VERSION,
    build_tpcds_cases,
)
from app.sandbox.sqlite import (
    SqliteFailure,
    SqliteSuccess,
    check_sqlite_read_only,
    execute_sqlite_readonly,
)
from app.schemas.benchmark import BenchmarkCase


class PostgresTarget(TypedDict):
    """TPC-DS 库的连接参数。"""

    host: str
    port: int
    user: str
    password: str
    database: str


LOGGER = logging.getLogger(__name__)
QUESTIONS_URL = (
    "https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/"
    f"{DATASET_COMMIT}/data/dev_20251106-00000-of-00001.json"
)
DATABASE_URL = (
    "https://drive.usercontent.google.com/download"
    f"?id={DATABASE_DRIVE_ID}&export=download&confirm=t"
)
_TABLE_NAME = re.compile(r"[a-z_]+")


def schema_statements(sql_text: str) -> list[tuple[str, str]]:
    """从 TPC-DS schema 文本得到建表语句。派生加载不建主键，以便 SF=1 放进受限内存。"""

    statements: list[tuple[str, str]] = []
    for part in re.split(r"\ncreate table ", sql_text)[1:]:
        name = part.split("(", 1)[0].strip()
        if _TABLE_NAME.fullmatch(name) is None:
            raise ValueError(f"unexpected TPC-DS table name: {name}")
        body = "create table " + part.split(";", 1)[0]
        body = re.sub(r",?\s*primary key\s*\([^)]*\)", "", body, flags=re.IGNORECASE)
        statements.append((name, body.strip() + ";"))
    return statements


def patch_tpcds_makefile(text: str) -> str:
    """让现代 GCC 接受工具里的重复暂定定义。"""

    lines = text.splitlines(keepends=True)
    if not any(line.startswith("LINUX_CFLAGS") for line in lines):
        raise ValueError("TPC-DS makefile has no LINUX_CFLAGS")
    patched: list[str] = []
    for line in lines:
        if line.startswith("LINUX_CFLAGS") and "-fcommon" not in line:
            ending = "\n" if line.endswith("\n") else ""
            line = line.rstrip("\n") + " -fcommon" + ending
        patched.append(line)
    return "".join(patched)


def build_tpcds_tools(kit_dir: Path) -> None:
    """克隆固定提交并编译 dsdgen。只在显式调用时访问网络。"""

    if not (kit_dir / ".git").is_dir():
        kit_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", KIT_REPO, str(kit_dir)], check=True)
    subprocess.run(["git", "checkout", "--force", KIT_COMMIT], cwd=kit_dir, check=True)
    makefile = kit_dir / "tools" / "makefile"
    updated = patch_tpcds_makefile(makefile.read_text(encoding="utf-8"))
    makefile.write_text(updated, encoding="utf-8")
    tools = kit_dir / "tools"
    subprocess.run(["make", "clean"], cwd=tools, check=True)
    subprocess.run(["make", "OS=LINUX", f"-j{os.cpu_count() or 2}"], cwd=tools, check=True)


def generate_tpcds_scale(kit_dir: Path, data_dir: Path, *, scale: int = 1) -> None:
    """用已编译的 dsdgen 生成 SF=1。生成文件不进入 Git。"""

    if scale != 1:
        raise ValueError("this phase generates TPC-DS SF=1 only")
    dsdgen = kit_dir / "tools" / "dsdgen"
    if not dsdgen.is_file():
        raise FileNotFoundError("dsdgen is missing; build the pinned TPC-DS tools first")
    data_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(dsdgen),
            "-SCALE",
            "1",
            "-FORCE",
            "Y",
            "-DIR",
            str(data_dir),
            "-TERMINATE",
            "N",
        ],
        cwd=kit_dir / "tools",
        check=True,
    )


async def load_tpcds_tables(
    data_dir: Path,
    schema_sql: str,
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
) -> dict[str, int]:
    """把扁平文件载入名为 tpcds 的数据库。已有行的表不会重载。"""

    if database == "text2sql_db":
        raise ValueError("TPC-DS data must not be loaded into the ecommerce database")
    tables = schema_statements(schema_sql)
    if len(tables) < 24:
        raise ValueError("TPC-DS schema did not contain the business tables")
    try:
        connection = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
    except Exception as exc:
        if password and password in str(exc):
            raise RuntimeError("could not connect to the tpcds database") from None
        raise RuntimeError("could not connect to the tpcds database") from exc
    counts: dict[str, int] = {}
    try:
        await connection.execute("SET synchronous_commit TO off")
        for name, statement in tables:
            existing = await connection.fetchval("SELECT to_regclass($1)", f"public.{name}")
            if existing is None:
                await connection.execute(statement)
            count = await connection.fetchval(f"SELECT count(*) FROM {name}")
            if not isinstance(count, int):
                raise RuntimeError(f"could not count {name}")
            if count == 0:
                path = data_dir / f"{name}.dat"
                LOGGER.info("loading %s", name)
                with path.open("rb") as handle:
                    await _copy_table(connection, name, handle)
                count = await connection.fetchval(f"SELECT count(*) FROM {name}")
                if not isinstance(count, int) or count == 0:
                    raise RuntimeError(f"TPC-DS table {name} stayed empty")
            counts[name] = count
    finally:
        await connection.close()
    return counts


async def execute_tpcds_gold(
    cases: Sequence[BenchmarkCase],
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    timeout_seconds: float = 180,
) -> list[GoldTrace]:
    """在 tpcds 库上执行 Gold SQL。结果不进入问数 Prompt。"""

    connection = await asyncpg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )
    traces: list[GoldTrace] = []
    try:
        await connection.execute(f"SET statement_timeout = {int(timeout_seconds * 1000)}")
        for case in cases:
            if case.source != "tpcds-derived":
                raise ValueError("tpcds gold execution only accepts tpcds-derived cases")
            LOGGER.info("executing %s", case.id)
            traces.append(await _one_tpcds(connection, case))
    finally:
        await connection.close()
    return traces


def select_bird_cases_with_adapter(
    database_root: Path,
    questions: Sequence[Mapping[str, object]],
    *,
    timeout_seconds: float,
) -> tuple[list[int], dict[str, str]]:
    """按 question_id 升序执行，记录未能通过受限适配器的题目。"""

    exclusions: list[int] = []
    accepted_databases: set[str] = set()
    accepted = 0
    ordered = sorted(
        (row for row in questions if row.get("difficulty") == "challenging"),
        key=lambda row: int(str(row["question_id"])),
    )
    for row in ordered:
        question_id = int(str(row["question_id"]))
        gold_sql = str(row["SQL"])
        if check_sqlite_read_only(gold_sql) is None:
            exclusions.append(question_id)
            continue
        database_id = str(row["db_id"])
        result = execute_sqlite_readonly(
            _sqlite_path(database_root, database_id),
            gold_sql,
            timeout_seconds=timeout_seconds,
        )
        if isinstance(result, SqliteFailure):
            LOGGER.info("exclude %s %s", question_id, result.category)
            exclusions.append(question_id)
            continue
        case = materialize_bird_case(row)
        if list(result.columns) != case.expected_columns:
            LOGGER.info("exclude %s column_mismatch", question_id)
            exclusions.append(question_id)
            continue
        accepted_databases.add(database_id)
        accepted += 1
        LOGGER.info("accepted %s (%s)", question_id, accepted)
        if accepted == 50:
            break
    checksums = {
        database_id: sha256_file(_sqlite_path(database_root, database_id))
        for database_id in sorted(accepted_databases)
    }
    return exclusions, checksums


def execute_bird_gold(
    cases: Sequence[BenchmarkCase],
    database_root: Path,
    checksums: Mapping[str, str],
    *,
    timeout_seconds: float,
) -> list[GoldTrace]:
    """用同一只读适配器执行已入选的 BIRD Gold SQL。"""

    traces: list[GoldTrace] = []
    for case in cases:
        if case.source != "bird":
            raise ValueError("bird gold execution only accepts bird cases")
        path = _sqlite_path(database_root, case.database_id)
        digest = sha256_file(path)
        if checksums.get(case.database_id) != digest:
            raise RuntimeError(f"sqlite checksum mismatch for {case.database_id}")
        result = execute_sqlite_readonly(path, case.gold_sql, timeout_seconds=timeout_seconds)
        if isinstance(result, SqliteSuccess):
            if list(result.columns) != case.expected_columns:
                traces.append(
                    GoldTrace(case.id, "error", None, None, "column names diverged from the case")
                )
                continue
            traces.append(
                GoldTrace(case.id, "ok", len(result.rows), digest_rows(result.rows), None)
            )
            continue
        traces.append(GoldTrace(case.id, "error", None, None, result.category))
    return traces


def fetch_bird_questions(dest: Path) -> None:
    """下载固定提交的问题文件并核对摘要。"""

    _download(QUESTIONS_URL, dest, QUESTIONS_SHA256)


def fetch_bird_databases(dest: Path) -> None:
    """下载固定的开发库压缩包并核对摘要。压缩包不进入 Git。"""

    _download(DATABASE_URL, dest, DATABASE_ZIP_SHA256)
    if dest.read_bytes()[:2] != b"PK":
        raise RuntimeError("BIRD database download was not a zip file")


def sha256_file(path: Path) -> str:
    """计算文件摘要。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def digest_rows(rows: Sequence[Sequence[object]]) -> str:
    """结果多重集的摘要。顺序不敏感。"""

    lines = sorted(
        json.dumps(list(row), ensure_ascii=False, default=_json_default, sort_keys=False)
        for row in rows
    )
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def snapshot_from_counts(counts: Mapping[str, int]) -> str:
    """用表行数生成可写入报告的快照标识。"""

    lines = [f"{name}:{counts[name]}" for name in sorted(counts)]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def postgres_connection_kwargs() -> PostgresTarget:
    """从环境变量读取 TPC-DS 连接参数。不记录密码。"""

    password = os.environ.get("TPCDS_POSTGRES_PASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    user = os.environ.get("TPCDS_POSTGRES_USER") or os.environ.get("POSTGRES_USER")
    if not password or not user:
        raise RuntimeError("TPC-DS loading needs POSTGRES_USER and POSTGRES_PASSWORD")
    raw_port = os.environ.get("TPCDS_POSTGRES_PORT") or os.environ.get("POSTGRES_PORT", "5432")
    return {
        "host": os.environ.get("TPCDS_POSTGRES_HOST")
        or os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(raw_port),
        "user": user,
        "password": password,
        "database": os.environ.get("TPCDS_POSTGRES_DB", "tpcds"),
    }


def main(argv: list[str] | None = None) -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="获取或执行外部评测数据")
    subcommands = parser.add_subparsers(dest="command", required=True)
    tools = subcommands.add_parser("build-tpcds-tools")
    tools.add_argument("--kit-dir", type=Path, required=True)
    generate = subcommands.add_parser("generate-tpcds")
    generate.add_argument("--kit-dir", type=Path, required=True)
    generate.add_argument("--data-dir", type=Path, required=True)
    load = subcommands.add_parser("load-tpcds")
    load.add_argument("--data-dir", type=Path, required=True)
    load.add_argument("--schema", type=Path, required=True)
    select = subcommands.add_parser("select-bird")
    select.add_argument("--database-root", type=Path, required=True)
    select.add_argument("--timeout", type=float, default=20)
    verify_bird = subcommands.add_parser("verify-bird")
    verify_bird.add_argument("--database-root", type=Path, required=True)
    verify_bird.add_argument("--timeout", type=float, default=20)
    verify_bird.add_argument("--report-root", type=Path, default=Path("reports/bird"))
    verify_tpcds = subcommands.add_parser("verify-tpcds")
    verify_tpcds.add_argument("--timeout", type=float, default=180)
    verify_tpcds.add_argument("--report-root", type=Path, default=Path("reports/tpcds-derived"))
    questions = subcommands.add_parser("fetch-bird-questions")
    questions.add_argument("--dest", type=Path, required=True)
    databases = subcommands.add_parser("fetch-bird-databases")
    databases.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if args.command == "build-tpcds-tools":
        build_tpcds_tools(args.kit_dir)
    elif args.command == "generate-tpcds":
        generate_tpcds_scale(args.kit_dir, args.data_dir)
    elif args.command == "load-tpcds":
        schema_sql = args.schema.read_text(encoding="utf-8")
        counts = asyncio.run(
            load_tpcds_tables(args.data_dir, schema_sql, **postgres_connection_kwargs())
        )
        LOGGER.info("loaded %s tables", len(counts))
    elif args.command == "select-bird":
        _write_bird_selection(args.database_root, args.timeout)
    elif args.command == "verify-bird":
        _verify_bird(args.database_root, args.timeout, args.report_root)
    elif args.command == "verify-tpcds":
        asyncio.run(_verify_tpcds(args.timeout, args.report_root))
    elif args.command == "fetch-bird-questions":
        fetch_bird_questions(args.dest)
    elif args.command == "fetch-bird-databases":
        fetch_bird_databases(args.dest)


def _write_bird_selection(database_root: Path, timeout_seconds: float) -> None:
    questions = load_bird_questions()
    exclusions, checksums = select_bird_cases_with_adapter(
        database_root,
        questions,
        timeout_seconds=timeout_seconds,
    )
    EXCLUSIONS_PATH.write_text(
        json.dumps({"question_ids": exclusions}, indent=2) + "\n",
        encoding="utf-8",
    )
    CHECKSUMS_PATH.write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")
    cases = build_bird_cases(questions, set(exclusions))
    CASES_PATH.write_text(dump_bird_cases(cases), encoding="utf-8")
    LOGGER.info("froze %s bird cases and %s exclusions", len(cases), len(exclusions))


def _verify_bird(database_root: Path, timeout_seconds: float, report_root: Path) -> None:
    cases = build_bird_cases()
    traces = execute_bird_gold(
        cases,
        database_root,
        load_database_checksums(),
        timeout_seconds=timeout_seconds,
    )
    failed = [trace.case_id for trace in traces if trace.status != "ok"]
    if failed:
        raise RuntimeError(f"bird gold execution failed: {failed}")
    _write_report(
        report_root,
        source="bird",
        version=BIRD_SOURCE_VERSION,
        cases=cases,
        traces=traces,
        snapshot=QUESTIONS_SHA256,
        environment={"executor": "sqlite-readonly-adapter", "cpu_limit": 2, "memory_limit_gb": 2},
    )


async def _verify_tpcds(timeout_seconds: float, report_root: Path) -> None:
    cases = build_tpcds_cases()
    settings = postgres_connection_kwargs()
    traces = await execute_tpcds_gold(cases, timeout_seconds=timeout_seconds, **settings)
    failed = [trace.case_id for trace in traces if trace.status != "ok" or trace.row_count == 0]
    if failed:
        raise RuntimeError(f"tpcds gold execution failed or was empty: {failed}")
    digests = [trace.digest for trace in traces]
    if len(set(digests)) != len(digests):
        raise RuntimeError("tpcds gold results are not unique")
    connection = await asyncpg.connect(**settings)
    try:
        counts = {}
        for name in sorted(
            {
                "store_sales",
                "catalog_sales",
                "web_sales",
                "inventory",
                "date_dim",
                "item",
                "customer",
            }
        ):
            value = await connection.fetchval(f"SELECT count(*) FROM {name}")
            if isinstance(value, int):
                counts[name] = value
    finally:
        await connection.close()
    _write_report(
        report_root,
        source="tpcds-derived",
        version=TPCDS_SOURCE_VERSION,
        cases=cases,
        traces=traces,
        snapshot=snapshot_from_counts(counts),
        environment={
            "postgres": "16",
            "scale_factor": 1,
            "cpu_limit": 2,
            "memory_limit_gb": 2,
            "official_tpcds_result": False,
        },
    )


def _write_report(
    report_root: Path,
    *,
    source: ExternalSource,
    version: str,
    cases: Sequence[BenchmarkCase],
    traces: Sequence[GoldTrace],
    snapshot: str,
    environment: Mapping[str, object],
) -> None:
    started = datetime.now(UTC).replace(microsecond=0)
    summary = build_external_summary(
        cases,
        traces,
        source=source,
        benchmark_version=version,
        git_commit=_git_commit(),
        database_snapshot=snapshot,
        started_at=started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        environment=environment,
    )
    directory = write_external_report(
        report_root,
        stamp=started.strftime("%Y%m%dT%H%M%SZ"),
        commit=_git_commit(),
        summary=summary,
        traces=traces,
    )
    LOGGER.info("wrote %s", directory)


async def _copy_table(connection: asyncpg.Connection, name: str, handle: BinaryIO) -> None:
    await connection.copy_to_table(name, source=handle, format="csv", delimiter="|", null="")


async def _one_tpcds(connection: asyncpg.Connection, case: BenchmarkCase) -> GoldTrace:
    try:
        prepared = await connection.prepare(case.gold_sql)
        actual = [attribute.name for attribute in prepared.get_attributes()]
        if actual != case.expected_columns:
            return GoldTrace(case.id, "error", None, None, "column names diverged from the case")
        rows = await prepared.fetch()
    except asyncpg.PostgresError as exc:
        return GoldTrace(case.id, "error", None, None, exc.sqlstate or "database_error")
    materialized = [tuple(row) for row in rows]
    return GoldTrace(case.id, "ok", len(materialized), digest_rows(materialized), None)


def _sqlite_path(database_root: Path, database_id: str) -> Path:
    return database_root / database_id / f"{database_id}.sqlite"


def _download(url: str, dest: Path, expected: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response, dest.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    digest = sha256_file(dest)
    if digest != expected:
        dest.unlink(missing_ok=True)
        raise RuntimeError("downloaded file did not match the pinned digest")


def _json_default(value: object) -> str:
    return str(value)


def _git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


if __name__ == "__main__":
    main()
