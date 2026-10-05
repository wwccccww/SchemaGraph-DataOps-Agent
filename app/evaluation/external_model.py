"""在已登记的外部库上跑问数模型。

Gold SQL 只在生成结束之后单独执行，不会作为工作流参数。
电商业务契约和事实粒度规则不参与这些库。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.agents.text_to_sql.prompt import GENERIC_PROMPT_VERSION
from app.agents.text_to_sql.shape import extract_generic_shape, generic_coverage
from app.agents.text_to_sql.workflow import (
    TEXT_TO_SQL_VARIANTS,
    ServiceBundle,
    SqlExecutor,
    TextToSqlInspection,
    TextToSqlVariant,
    inspect_text_to_sql,
)
from app.config.llm_settings import get_llm_settings
from app.datasources.bundle import build_static_bundle
from app.datasources.postgres_catalog import load_public_catalog
from app.datasources.postgres_exec import EXTERNAL_RESULT_CEILING, execute_registered_postgres
from app.datasources.registry import resolve_data_source
from app.datasources.sqlite_catalog import load_sqlite_catalog
from app.datasources.sqlite_exec import sqlite_executor
from app.evaluation.bird import (
    BIRD_SOURCE_VERSION,
    QUESTIONS_SHA256,
    load_bird_cases,
    load_database_checksums,
)
from app.evaluation.ex import results_match
from app.evaluation.external_data import (
    PostgresTarget,
    postgres_connection_kwargs,
    sha256_file,
    snapshot_from_counts,
)
from app.evaluation.external_report import (
    ExternalSource,
    ModelCaseTrace,
    build_external_model_summary,
    write_external_model_report,
)
from app.evaluation.sql_shape import describe_sql
from app.evaluation.text_to_sql import EVALUATION_MAX_ROWS
from app.evaluation.external_badcase import classify_external_case
from app.evaluation.external_gold import ensure_fingerprints, ensure_gold_matched
from app.evaluation.tpcds import TPCDS_SOURCE_VERSION, load_tpcds_cases
from app.graph.expand import TokenCounter
from app.llm.gateway import DeepSeekGateway
from app.llm.tokenizer import DeepSeekTokenCounter
from app.sandbox.errors import ExecutionError, normalize_message
from app.sandbox.execute import ExecutionSuccess
from app.schemas.benchmark import BenchmarkCase
from app.schemas.catalog import SchemaEdge, TableDocument

LOGGER = logging.getLogger(__name__)
_PROMPT_MARKERS = ("答案契约", "查询计划：", "事实粒度：", "防放大：")
_ECOMMERCE_CATEGORIES = frozenset(
    {
        "missing_fact_dedup",
        "aggregate_over_fanout",
        "refanout_after_dedup",
        "contract_mismatch",
        "wrong_entity_literal",
    }
)
_TPCDS_COUNT_TABLES = (
    "catalog_sales",
    "customer",
    "date_dim",
    "inventory",
    "item",
    "store_sales",
    "web_sales",
)
InspectCase = Callable[[BenchmarkCase], Awaitable[TextToSqlInspection]]
ExecuteSql = Callable[[str], Awaitable[ExecutionSuccess | ExecutionError]]
ExecuteCase = Callable[[BenchmarkCase, str], Awaitable[ExecutionSuccess | ExecutionError]]


def select_sample(
    cases: Sequence[BenchmarkCase],
    *,
    per_database: int | None,
    limit: int | None,
) -> list[BenchmarkCase]:
    """按库或总条数截取样本。两个上限都缺省时拒绝，避免误跑全量。"""

    if per_database is not None and per_database < 1:
        raise ValueError("per_database must be positive")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    if per_database is None and limit is None:
        raise ValueError("pass limit or per_database")
    chosen: list[BenchmarkCase] = []
    counts: dict[str, int] = {}
    for case in cases:
        used = counts.get(case.database_id, 0)
        if per_database is not None and used >= per_database:
            continue
        chosen.append(case)
        counts[case.database_id] = used + 1
        if limit is not None and len(chosen) >= limit:
            break
    if not chosen:
        raise ValueError("sample is empty")
    return chosen


def ecommerce_rule_hits(
    *,
    prompt: str,
    question: str,
    categories: Sequence[str],
) -> tuple[str, ...]:
    """电商契约文本和事实粒度类别。问句本身里的词不算命中。"""

    remainder = prompt.replace(question, "", 1)
    hits = [marker for marker in _PROMPT_MARKERS if marker in remainder]
    for category in categories:
        if category in _ECOMMERCE_CATEGORIES and category not in hits:
            hits.append(category)
    return tuple(hits)


async def evaluate_predictions(
    cases: Sequence[BenchmarkCase],
    *,
    inspect_case: InspectCase,
    execute_sql: ExecuteCase,
    catalog_for: Callable[[str], Collection[str]],
) -> list[ModelCaseTrace]:
    """先生成，再执行预测和 Gold。目录表名用于检查有没有串库。"""

    traces: list[ModelCaseTrace] = []
    for case in cases:
        source = resolve_data_source(case.database_id)
        if source is None or source.profile != "generic":
            raise ValueError("external model evaluation only runs generic databases")
        if case.dialect != source.dialect:
            raise ValueError("case dialect does not match the registered source")
        LOGGER.info("start %s", case.id)
        inspection = await inspect_case(case)

        async def execute(
            sql: str, *, current: BenchmarkCase = case
        ) -> ExecutionSuccess | ExecutionError:
            return await execute_sql(current, sql)

        trace = await score_prediction(
            case,
            inspection,
            execute=execute,
            catalog_tables=catalog_for(case.database_id),
        )
        traces.append(trace)
        LOGGER.info("%s %s ex=%s", trace.case_id, trace.primary_class, trace.ex)
    return traces


async def score_prediction(
    case: BenchmarkCase,
    inspection: TextToSqlInspection,
    *,
    execute: ExecuteSql,
    catalog_tables: Collection[str],
) -> ModelCaseTrace:
    """比较一条已经生成的 SQL。Gold 不会回到生成 Prompt。"""

    response = inspection.response
    context = response.schema_context
    seeds = tuple(context.seed_tables) if context is not None else ()
    expanded = tuple(context.expanded_tables) if context is not None else ()
    known = set(catalog_tables)
    leaked = tuple(name for name in (*seeds, *expanded) if name not in known)
    categories = tuple(
        str(step["category"])
        for step in inspection.repair_trace
        if isinstance(step.get("category"), str)
    )
    hits = ecommerce_rule_hits(
        prompt=inspection.prompt,
        question=case.question,
        categories=categories,
    )
    predicted = inspection.generated_sql
    error_category = None if response.error is None else response.error.category
    ex = 0
    primary = "sql_error"
    diagnosis = "sql_error"
    symptoms: tuple[tuple[str, str], ...] = ()
    predicted_outcome: ExecutionSuccess | ExecutionError | None = None
    if leaked:
        error_category = error_category or "cross_database_catalog"
    elif response.status == "succeeded" and predicted:
        predicted_outcome = await execute(predicted)
        if isinstance(predicted_outcome, ExecutionError):
            error_category = predicted_outcome.category
        else:
            gold_outcome = await execute(case.gold_sql)
            if isinstance(gold_outcome, ExecutionError):
                raise RuntimeError(f"gold execution failed for {case.id}")
            same = results_match(
                predicted_outcome.rows,
                gold_outcome.rows,
                order_sensitive=case.order_sensitive,
                numeric_tolerance=case.numeric_tolerance,
            )
            if same:
                ex = 1
                error_category = None
    primary, diagnosis, symptoms = classify_external_case(
        case,
        predicted_sql=predicted,
        error_category=error_category,
        ex=ex,
        leaked_tables=leaked,
        repair_trace=inspection.repair_trace,
    )
    shape = describe_sql(predicted, dialect=case.dialect)
    message = None if response.error is None else response.error.message
    if isinstance(predicted_outcome, ExecutionError):
        message = predicted_outcome.normalized_message
    coverage = generic_coverage(
        extract_generic_shape(case.question, _stub_documents(case.database_id, catalog_tables)),
        predicted or "",
        dialect=case.dialect,
    )
    return ModelCaseTrace(
        case_id=case.id,
        database_id=case.database_id,
        primary_class=primary,
        ex=ex,
        error_category=error_category,
        attempts=response.attempts or 0,
        seed_tables=seeds,
        expanded_tables=expanded,
        leaked_tables=leaked,
        ecommerce_rule_hits=hits,
        prediction=shape.as_json(),
        normalized_message=None if message is None else normalize_message(message),
        context_recall=_table_recall(case.required_tables, (*seeds, *expanded)),
        sql_table_recall=_table_recall(case.required_tables, shape.referenced_tables),
        dimension_coverage=coverage["dimension_coverage"],
        entity_coverage=coverage["entity_coverage"],
        measure_coverage=coverage["measure_coverage"],
        diagnosis_class=diagnosis,
        symptoms=symptoms,
    )


def _table_recall(required: Sequence[str], found: Sequence[str]) -> float | None:
    if not required:
        return None
    seen = {name.lower() for name in found}
    return sum(1 for name in required if name.lower() in seen) / len(required)


def _stub_documents(database_id: str, names: Collection[str]) -> tuple[TableDocument, ...]:
    return tuple(
        TableDocument(
            database_id=database_id,
            schema_name="public",
            table_name=name,
            table_comment=None,
            columns=[],
            is_junction=False,
            content_hash=f"sha256:{name}",
        )
        for name in names
    )


def render_model_diagnosis(
    summary: Mapping[str, object],
    cases: Sequence[Mapping[str, object]],
) -> str:
    """从报告 JSON 整理分类。不重新推断 Gold 或调用模型。"""

    measured = summary.get("measured")
    accuracy = measured.get("execution_accuracy") if isinstance(measured, dict) else None
    execution = summary.get("model_execution")
    counts = execution if isinstance(execution, dict) else {}
    environment = summary.get("environment")
    sample = not (isinstance(environment, dict) and environment.get("sample") is False)
    lines = [
        "# 外部问数小样本诊断" if sample else "# 外部问数诊断",
        "",
        f"- 来源：{summary.get('benchmark_source')}",
        f"- 模型：{summary.get('model')}",
        f"- Prompt：{summary.get('prompt_version')}",
        f"- 执行准确率：{accuracy}",
        f"- 匹配：{counts.get('matched')}",
        f"- SQL 错误：{counts.get('sql_error')}",
        f"- 可执行率：{counts.get('executable_rate')}",
        f"- 方言错误率：{counts.get('dialect_error_rate')}",
        f"- 上下文召回：{counts.get('context_recall')}",
        f"- 引用表召回：{counts.get('sql_table_recall')}",
        f"- 维度覆盖：{counts.get('dimension_coverage')}",
        f"- 实体覆盖：{counts.get('entity_coverage')}",
        f"- 度量覆盖：{counts.get('measure_coverage')}",
        f"- 结果不一致：{counts.get('other_result_mismatch')}",
        f"- 电商规则命中用例：{counts.get('ecommerce_rule_cases')}",
        f"- 串库用例：{counts.get('cross_database_leaks')}",
        "- 这是注册库上的模型执行，不是 Gold-only，也不是官方 TPC-DS 分数。",
        "",
        "## 未匹配",
        "",
    ]
    misses = [case for case in cases if case.get("primary_class") != "matched"]
    if not misses:
        lines.append("没有未匹配用例。")
        lines.append("")
        return "\n".join(lines)
    for case in misses:
        prediction = case.get("prediction")
        shape = prediction if isinstance(prediction, dict) else {}
        lines.extend(
            (
                f"### {case.get('case_id')}",
                "",
                f"- 数据库：{case.get('database_id')}",
                f"- 分类：{case.get('primary_class')}",
                f"- 细分类：{case.get('diagnosis_class')}",
                f"- 症状：{case.get('symptoms')}",
                f"- 错误类别：{case.get('error_category')}",
                f"- 脱敏错误：{case.get('normalized_message')}",
                f"- 上下文召回：{case.get('context_recall')}",
                f"- 引用表召回：{case.get('sql_table_recall')}",
                f"- 维度覆盖：{case.get('dimension_coverage')}",
                f"- 实体覆盖：{case.get('entity_coverage')}",
                f"- 度量覆盖：{case.get('measure_coverage')}",
                f"- 种子表：{case.get('seed_tables')}",
                f"- 引用表：{shape.get('referenced_tables')}",
                f"- 投影：{shape.get('projections')}",
                f"- 聚合：{shape.get('aggregations')}",
                f"- 分组：{shape.get('group_by')}",
                f"- 电商规则：{case.get('ecommerce_rule_hits')}",
                f"- 串库表：{case.get('leaked_tables')}",
                "",
                "```sql",
                _diagnosis_sql(shape.get("sql")),
                "```",
                "",
            )
        )
    return "\n".join(lines)


def _diagnosis_sql(sql: object) -> str:
    text = "" if sql is None else str(sql)
    if len(text) <= 2000:
        return text
    return text[:2000] + "\n-- truncated"


def write_model_diagnosis(directory: Path) -> Path:
    """读取刚写好的 summary 和用例文件，再写诊断。"""

    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise ValueError("model summary must be an object")
    names = summary.get("case_files")
    if not isinstance(names, list):
        raise ValueError("model summary needs case files")
    cases: list[dict[str, object]] = []
    for name in names:
        if not isinstance(name, str):
            raise ValueError("model case file name must be a string")
        payload = json.loads((directory / name).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("model case file must be an object")
        cases.append(payload)
    path = directory / "badcase_diagnosis.md"
    path.write_text(render_model_diagnosis(summary, cases), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="在 BIRD 或 TPC-DS 上运行问数模型")
    parser.add_argument("--source", choices=("bird", "tpcds-derived"), required=True)
    parser.add_argument("--database-root", type=Path)
    parser.add_argument("--per-database", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--full",
        action="store_true",
        help="run every frozen case; requires gold_matched attestation",
    )
    parser.add_argument(
        "--variant",
        default="self_healing",
        help="text-to-sql workflow variant (default self_healing for external EX)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180,
        help="SQL execution timeout seconds (TPC-DS Gold 可能超过 30s)",
    )
    parser.add_argument("--report-root", type=Path)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.variant not in TEXT_TO_SQL_VARIANTS:
        raise SystemExit(f"unknown variant: {args.variant}")
    code = asyncio.run(
        _run(
            source=args.source,
            database_root=args.database_root,
            per_database=args.per_database,
            limit=args.limit,
            full=args.full,
            variant=args.variant,
            timeout_seconds=args.timeout,
            report_root=args.report_root,
        )
    )
    if code:
        sys.exit(code)


async def _run(
    *,
    source: ExternalSource,
    database_root: Path | None,
    per_database: int | None,
    limit: int | None,
    full: bool,
    variant: TextToSqlVariant,
    timeout_seconds: float,
    report_root: Path | None,
) -> int:
    loaded = load_bird_cases() if source == "bird" else load_tpcds_cases()
    ensure_fingerprints(loaded, source)
    if full:
        if per_database is not None or limit is not None:
            raise ValueError("--full cannot be combined with --limit or --per-database")
        cases = list(loaded)
        ensure_gold_matched(loaded, source)
    else:
        cases = select_sample(
            loaded,
            per_database=per_database,
            limit=limit,
        )
        if len(cases) == len(loaded):
            ensure_gold_matched(loaded, source)
    llm = get_llm_settings()
    if llm.deepseek_api_key is None:
        raise RuntimeError("DEEPSEEK_API_KEY is required")
    model = DeepSeekGateway(
        api_key=llm.deepseek_api_key,
        base_url=llm.deepseek_base_url,
        model=llm.deepseek_model,
        timeout_seconds=120,
    )
    counter = DeepSeekTokenCounter()
    bundles: dict[str, ServiceBundle] = {}
    catalogs: dict[str, tuple[str, ...]] = {}
    runners: dict[str, SqlExecutor] = {}
    if source == "bird":
        if database_root is None:
            raise ValueError("bird model evaluation needs --database-root")
        _verify_bird_files(database_root, {case.database_id for case in cases})
        snapshot = QUESTIONS_SHA256
        version = BIRD_SOURCE_VERSION
        root = report_root or Path("reports/bird")
    else:
        snapshot = await _tpcds_snapshot(timeout_seconds)
        version = TPCDS_SOURCE_VERSION
        root = report_root or Path("reports/tpcds-derived")

    async def services_for(database_id: str) -> ServiceBundle:
        if database_id not in bundles:
            bundle, tables, runner = await _bundle_for(
                source,
                database_id,
                database_root=database_root,
                model=model,
                token_counter=counter,
                timeout_seconds=timeout_seconds,
            )
            bundles[database_id] = bundle
            catalogs[database_id] = tables
            runners[database_id] = runner
        return bundles[database_id]

    async def inspect_case(case: BenchmarkCase) -> TextToSqlInspection:
        services = await services_for(case.database_id)
        return await inspect_text_to_sql(
            services,
            question=case.question,
            database_id=case.database_id,
            execute=True,
            max_rows=_evaluation_max_rows(source),
            variant=variant,
        )

    async def execute_sql(case: BenchmarkCase, sql: str) -> ExecutionSuccess | ExecutionError:
        await services_for(case.database_id)
        return await runners[case.database_id](sql, max_rows=_evaluation_max_rows(source))

    traces = await evaluate_predictions(
        cases,
        inspect_case=inspect_case,
        execute_sql=execute_sql,
        catalog_for=lambda database_id: catalogs[database_id],
    )
    started = datetime.now(UTC).replace(microsecond=0)
    summary = build_external_model_summary(
        traces,
        source=source,
        benchmark_version=version,
        git_commit=_git_commit(),
        database_snapshot=snapshot,
        started_at=started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        model=model.model,
        prompt_version=GENERIC_PROMPT_VERSION,
        environment={
            "variant": variant,
            "sample": len(cases) < len(loaded),
            "per_database": per_database,
            "limit": limit,
            "lexical_seeds": True,
            "business_rules": False,
            "official_tpcds_result": False,
            "timeout_seconds": timeout_seconds,
        },
    )
    directory = write_external_model_report(
        root,
        stamp=started.strftime("%Y%m%dT%H%M%SZ"),
        commit=_git_commit(),
        summary=summary,
        traces=traces,
    )
    diagnosis = write_model_diagnosis(directory)
    LOGGER.info("wrote %s", directory)
    LOGGER.info("wrote %s", diagnosis)
    if any(trace.leaked_tables or trace.ecommerce_rule_hits for trace in traces):
        return 2
    return 0


def _evaluation_max_rows(source: ExternalSource) -> int:
    """SQLite 适配器上限是 1 万行。PostgreSQL 外部库要盖住 TPC-DS 的 Gold 行数。"""

    if source == "bird":
        return EVALUATION_MAX_ROWS
    return EXTERNAL_RESULT_CEILING


def _verify_bird_files(database_root: Path, database_ids: set[str]) -> None:
    checksums = load_database_checksums()
    for database_id in sorted(database_ids):
        path = _sqlite_path(database_root, database_id)
        if checksums.get(database_id) != sha256_file(path):
            raise RuntimeError(f"sqlite checksum mismatch for {database_id}")


async def _bundle_for(
    source: ExternalSource,
    database_id: str,
    *,
    database_root: Path | None,
    model: DeepSeekGateway,
    token_counter: TokenCounter,
    timeout_seconds: float,
) -> tuple[ServiceBundle, tuple[str, ...], SqlExecutor]:
    if source == "bird":
        if database_root is None:
            raise ValueError("bird model evaluation needs --database-root")
        path = _sqlite_path(database_root, database_id)
        documents, edges = load_sqlite_catalog(path, database_id)
        runner = sqlite_executor(path, timeout_seconds=timeout_seconds)
    else:
        documents, edges = await _read_tpcds_catalog()
        runner = _tpcds_runner(timeout_seconds)
    bundle = build_static_bundle(
        model=model,
        token_counter=token_counter,
        documents=documents,
        edges=edges,
        execute=runner,
        database_id=database_id,
    )
    return bundle, tuple(document.table_name for document in documents), runner


def _tpcds_runner(timeout_seconds: float) -> SqlExecutor:
    target = _tpcds_target()

    async def execute(sql: str, *, max_rows: int) -> ExecutionSuccess | ExecutionError:
        return await execute_registered_postgres(
            sql,
            max_rows=max_rows,
            timeout_seconds=timeout_seconds,
            host=target["host"],
            port=target["port"],
            user=target["user"],
            password=target["password"],
            database=target["database"],
        )

    return execute


async def _read_tpcds_catalog() -> tuple[list[TableDocument], list[SchemaEdge]]:
    target = _tpcds_target()
    url = URL.create(
        "postgresql+asyncpg",
        username=target["user"],
        password=target["password"],
        host=target["host"],
        port=target["port"],
        database=target["database"],
    )
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return await load_public_catalog(connection, "tpcds")
    except Exception as exc:
        if target["password"] and target["password"] in str(exc):
            raise RuntimeError("could not read the tpcds catalog") from None
        raise
    finally:
        await engine.dispose()


async def _tpcds_snapshot(timeout_seconds: float) -> str:
    counts: dict[str, int] = {}
    runner = _tpcds_runner(timeout_seconds)
    for name in _TPCDS_COUNT_TABLES:
        outcome = await runner(f"SELECT count(*) FROM {name}", max_rows=1)
        if isinstance(outcome, ExecutionError) or not outcome.rows:
            raise RuntimeError("could not count tpcds tables")
        value = outcome.rows[0][0]
        if not isinstance(value, int):
            raise RuntimeError("could not count tpcds tables")
        counts[name] = value
    return snapshot_from_counts(counts)


def _tpcds_target() -> PostgresTarget:
    target = postgres_connection_kwargs()
    if target["database"] == "text2sql_db":
        raise ValueError("TPC-DS evaluation must not use the ecommerce database")
    return target


def _sqlite_path(database_root: Path, database_id: str) -> Path:
    return database_root / database_id / f"{database_id}.sqlite"


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
