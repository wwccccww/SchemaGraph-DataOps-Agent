"""外部评测 Gold 指纹与执行 attestation。

BIRD 与 TPC-DS 派生用例不在 Git 里带数据库，因此分两层保障：

1. ``fingerprint_verified``：冻结 Gold SQL、列名与墙钟敏感标记与 attestation 一致；
2. ``gold_matched``：在固定数据库快照上执行 Gold，``result_digest`` 与 attestation 一致。

正式全量模型评测（覆盖全部冻结用例）必须在 ``gold_matched`` 状态下启动。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Literal

from app.evaluation.custom_cases import normalize_sql
from app.evaluation.ex import canonical_cell
from app.evaluation.gold_oracle import result_digest
from app.schemas.benchmark import BenchmarkCase

ExternalSource = Literal["tpcds-derived", "bird"]
AttestationStatus = Literal["fingerprint_verified", "gold_matched"]

_WALL_CLOCK = re.compile(
    r"strftime\s*\(\s*'%[^']+'\s*,\s*'now'\s*\)|\bdate\s*\(\s*'now'\s*\)|\bCURRENT_DATE\b|\bnow\s*\(\s*\)",
    re.IGNORECASE,
)

_ATTESTATION_PATHS: dict[ExternalSource, Path] = {
    "tpcds-derived": Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "tpcds_derived"
    / "gold_attestation.json",
    "bird": Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "bird_complex"
    / "gold_attestation.json",
}

# PR / 冒烟子集：覆盖 CTE、多表 Join、子查询、聚合；大结果用例在 nightly 全量验证。
TPCDS_GOLD_SMOKE_IDS = (
    "tpcds_complex_001",
    "tpcds_complex_004",
    "tpcds_complex_008",
    "tpcds_complex_015",
    "tpcds_complex_022",
)

BIRD_GOLD_SMOKE_IDS = (
    "bird_0000",
    "bird_0002",
    "bird_0003",
    "bird_0005",
    "bird_0006",
)


def attestation_path(source: ExternalSource) -> Path:
    return _ATTESTATION_PATHS[source]


def wall_clock_sensitive(gold_sql: str) -> bool:
    """Gold SQL 是否依赖运行时钟。此类用例的 result_digest 会随日期漂移。"""

    return _WALL_CLOCK.search(gold_sql) is not None


def gold_sql_fingerprint(gold_sql: str) -> str:
    normalized = normalize_sql(gold_sql)
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    return f"sha256:{digest}"


def fingerprint_entry(case: BenchmarkCase) -> dict[str, object]:
    return {
        "gold_sql_digest": gold_sql_fingerprint(case.gold_sql),
        "expected_columns": list(case.expected_columns),
        "order_sensitive": case.order_sensitive,
        "wall_clock_sensitive": wall_clock_sensitive(case.gold_sql),
        "row_count": None,
        "result_digest": None,
        "status": "fingerprint_verified",
    }


def build_fingerprint_document(
    cases: Sequence[BenchmarkCase],
    *,
    source: ExternalSource,
    benchmark_version: str,
) -> dict[str, object]:
    if not cases:
        raise ValueError("attestation needs cases")
    for case in cases:
        if case.source != source:
            raise ValueError(f"{case.id} source {case.source} != {source}")
    records = {case.id: fingerprint_entry(case) for case in cases}
    return {
        "benchmark_source": source,
        "benchmark_version": benchmark_version,
        "database_snapshot": None,
        "status": "fingerprint_verified",
        "cases": records,
    }


def load_attestation(source: ExternalSource, path: Path | None = None) -> dict[str, object]:
    file = path or attestation_path(source)
    payload = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("attestation must be an object")
    return payload


def ensure_fingerprints(cases: Sequence[BenchmarkCase], source: ExternalSource) -> None:
    """拒绝 Gold SQL 或列名与冻结 attestation 不一致的用例。"""

    document = load_attestation(source)
    if document.get("benchmark_source") != source:
        raise RuntimeError("attestation benchmark_source mismatch")
    stored_version = document.get("benchmark_version")
    if not isinstance(stored_version, str) or not stored_version:
        raise RuntimeError("attestation missing benchmark_version")
    for case in cases:
        if case.source_version != stored_version:
            raise RuntimeError(
                f"{case.id} source_version {case.source_version} != attestation {stored_version}"
            )
    stored_cases = document.get("cases")
    if not isinstance(stored_cases, dict):
        raise RuntimeError("attestation missing cases")
    if set(stored_cases) != {case.id for case in cases}:
        raise RuntimeError("attestation case ids do not match the frozen benchmark")
    for case in cases:
        item = stored_cases.get(case.id)
        if not isinstance(item, dict):
            raise RuntimeError(f"{case.id} missing attestation entry")
        digest = item.get("gold_sql_digest")
        if digest != gold_sql_fingerprint(case.gold_sql):
            raise RuntimeError(f"{case.id} gold SQL changed without attestation refresh")
        columns = item.get("expected_columns")
        if columns != case.expected_columns:
            raise RuntimeError(f"{case.id} expected_columns diverged from attestation")
        flagged = item.get("wall_clock_sensitive")
        actual = wall_clock_sensitive(case.gold_sql)
        if flagged is not True and flagged is not False:
            raise RuntimeError(f"{case.id} attestation wall_clock_sensitive must be boolean")
        if flagged != actual:
            raise RuntimeError(f"{case.id} wall_clock_sensitive flag is stale")


def ensure_gold_matched(cases: Sequence[BenchmarkCase], source: ExternalSource) -> None:
    """全量正式评测前：要求 attestation 已在固定快照上执行并对账。"""

    ensure_fingerprints(cases, source)
    document = load_attestation(source)
    if document.get("status") != "gold_matched":
        raise RuntimeError(
            "外部 Gold 尚未达到 gold_matched；请先运行 verify-bird / verify-tpcds 并刷新 attestation"
        )
    snapshot = document.get("database_snapshot")
    if not isinstance(snapshot, str) or not snapshot:
        raise RuntimeError("gold_matched attestation needs database_snapshot")
    stored_cases = document.get("cases")
    assert isinstance(stored_cases, dict)
    for case in cases:
        item = stored_cases[case.id]
        assert isinstance(item, dict)
        if item.get("status") != "gold_matched":
            raise RuntimeError(f"{case.id} is not gold_matched in attestation")
        result = item.get("result_digest")
        if not isinstance(result, str) or not result.startswith("sha256:"):
            raise RuntimeError(f"{case.id} missing result_digest in attestation")
        row_count = item.get("row_count")
        if not isinstance(row_count, int) or row_count < 1:
            raise RuntimeError(f"{case.id} missing row_count in attestation")


def merge_execution_into_attestation(
    cases: Sequence[BenchmarkCase],
    *,
    source: ExternalSource,
    benchmark_version: str,
    database_snapshot: str,
    executions: Mapping[str, tuple[int, str]],
) -> dict[str, object]:
    """把一次 verify 的执行摘要写回 attestation 文档。"""

    document = build_fingerprint_document(cases, source=source, benchmark_version=benchmark_version)
    records = document["cases"]
    assert isinstance(records, dict)
    for case in cases:
        outcome = executions.get(case.id)
        if outcome is None:
            raise ValueError(f"missing execution for {case.id}")
        row_count, digest_hex = outcome
        if row_count < 1:
            raise ValueError(f"{case.id} returned no rows")
        entry = records[case.id]
        assert isinstance(entry, dict)
        entry["row_count"] = row_count
        entry["result_digest"] = (
            f"sha256:{digest_hex}" if not digest_hex.startswith("sha256:") else digest_hex
        )
        entry["status"] = "gold_matched"
    document["database_snapshot"] = database_snapshot
    document["status"] = "gold_matched"
    return document


def write_attestation(document: Mapping[str, object], source: ExternalSource) -> Path:
    path = attestation_path(source)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def digest_rows_for_attestation(rows: Sequence[Sequence[object]], *, order_sensitive: bool) -> str:
    """与 Execution Accuracy 使用同一 canonical 规则，返回带 sha256: 前缀的摘要。"""

    materialized = [tuple(row) for row in rows]
    return result_digest(materialized, order_sensitive=order_sensitive)


def trace_digest_hex(rows: Sequence[Sequence[object]], *, order_sensitive: bool) -> str:
    """verify 路径沿用的 hex 摘要（无 sha256: 前缀），与历史 GoldTrace 兼容。"""

    full = digest_rows_for_attestation(rows, order_sensitive=order_sensitive)
    return full.removeprefix("sha256:")


def trace_digest_hex_from_stream(
    rows: Iterable[Sequence[object]], *, order_sensitive: bool
) -> tuple[int, str]:
    """大结果 verify 时流式计算 canonical 摘要，避免重复分配行对象。"""

    materialized = [
        json.dumps(
            [canonical_cell(cell) for cell in row],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for row in rows
    ]
    count = len(materialized)
    if not order_sensitive:
        materialized.sort()
    payload = "\n".join(materialized)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return count, digest


def smoke_case_ids(source: ExternalSource) -> tuple[str, ...]:
    return TPCDS_GOLD_SMOKE_IDS if source == "tpcds-derived" else BIRD_GOLD_SMOKE_IDS
