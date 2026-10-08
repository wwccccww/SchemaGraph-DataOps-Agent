"""外部模型评测的 badcase 分类。Gold 只在此层读取，不进入 Prompt。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.evaluation.badcase import classify_badcase
from app.schemas.benchmark import BenchmarkCase

_COARSE_SQL = frozenset(
    {
        "sql_error",
        "circuit_breaker",
        "cross_database_leak",
    }
)


def classify_external_case(
    case: BenchmarkCase,
    *,
    predicted_sql: str | None,
    error_category: str | None,
    ex: int,
    leaked_tables: Sequence[str],
    repair_trace: Sequence[Mapping[str, object]] = (),
) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    """返回 (粗类, 细类, 症状)。粗类用于汇总 EX，细类用于诊断。"""

    if leaked_tables:
        return (
            "sql_error",
            "cross_database_leak",
            (("leaked_tables", ",".join(leaked_tables)),),
        )
    trace = _repair_steps(repair_trace)
    detail, symptoms = classify_badcase(
        question=case.question,
        gold_sql=case.gold_sql,
        predicted_sql=predicted_sql,
        required_tables=case.required_tables,
        error_category=error_category,
        ex=ex,
        anchor_date=case.anchor_date.isoformat(),
        repair_trace=trace,
        dialect=case.dialect,
    )
    return _coarse_class(detail), detail, symptoms


def _coarse_class(detail: str) -> str:
    if detail == "matched":
        return "matched"
    if detail in _COARSE_SQL:
        return "sql_error"
    return "other_result_mismatch"


def _repair_steps(
    repair_trace: Sequence[Mapping[str, object]],
) -> tuple[tuple[str, str, str, str], ...]:
    steps: list[tuple[str, str, str, str]] = []
    for index, step in enumerate(repair_trace, start=1):
        category = step.get("category")
        symptom = step.get("symptom")
        sql_hash = step.get("sql_hash")
        if (
            not isinstance(category, str)
            or not isinstance(symptom, str)
            or not isinstance(sql_hash, str)
        ):
            continue
        steps.append((str(index), category, symptom, sql_hash))
    return tuple(steps)
