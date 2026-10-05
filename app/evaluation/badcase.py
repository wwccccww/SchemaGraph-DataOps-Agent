"""把一条预测归入互斥主类，并保留非互斥症状。

分类可以读取 Gold，因为它只运行在评测进程里，不进入生成或修复 Prompt。
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.agents.text_to_sql.contract import extract_answer_contract
from app.evaluation.sql_shape import PredictionShape, describe_sql

_SQL_ERRORS = frozenset(
    {
        "syntax_error",
        "multi_statement",
        "not_read_only",
        "disallowed_function",
        "recursive_cte_missing",
        "undefined_table",
        "undefined_column",
        "undefined_function",
        "database_error",
        "result_limit_exceeded",
        "result_size_exceeded",
        "grouping_error",
        "ambiguous_column",
    }
)
_REVIEW_ERRORS = frozenset(
    {
        "missing_entity",
        "projection_mismatch",
        "join_not_on_graph",
        "join_unverified",
        "cartesian_product",
        "aggregation_grain",
        "empty_result",
        "result_too_large",
        "explain_cardinality",
        "contract_mismatch",
    }
)
_CLOCK = re.compile(r"\b(?:current_date|current_timestamp|clock_timestamp)\b", re.IGNORECASE)
_LITERAL = re.compile(r"'([^']+)'")


def classify_badcase(
    *,
    question: str,
    gold_sql: str,
    predicted_sql: str | None,
    required_tables: Sequence[str],
    error_category: str | None,
    ex: int,
    anchor_date: str = "2026-10-01",
    repair_trace: Sequence[tuple[str, str, str, str]] = (),
) -> tuple[str, tuple[tuple[str, str], ...]]:
    """返回主类和症状。主类按固定优先级只取一个。"""

    predicted = describe_sql(predicted_sql)
    gold = describe_sql(gold_sql)
    symptoms = _symptoms(
        question=question,
        gold=gold,
        predicted=predicted,
        anchor_date=anchor_date,
        repair_trace=repair_trace,
    )
    primary = _primary(
        question=question,
        gold=gold,
        predicted=predicted,
        required_tables=required_tables,
        error_category=error_category,
        ex=ex,
        anchor_date=anchor_date,
        symptoms=symptoms,
    )
    return primary, symptoms


def _primary(
    *,
    question: str,
    gold: PredictionShape,
    predicted: PredictionShape,
    required_tables: Sequence[str],
    error_category: str | None,
    ex: int,
    anchor_date: str,
    symptoms: tuple[tuple[str, str], ...],
) -> str:
    if ex == 1:
        return "matched"
    if error_category in {"circuit_breaker", "no_progress"}:
        return "circuit_breaker"
    if error_category in _SQL_ERRORS or (
        error_category is not None and error_category not in _REVIEW_ERRORS
    ):
        return "sql_error"
    referenced = {name.lower() for name in predicted.referenced_tables}
    if any(name.lower() not in referenced for name in required_tables):
        return "missing_required_table"
    if _time_mismatch(question, predicted.sql or "", anchor_date):
        return "time_anchor"
    if _grain_mismatch(gold, predicted):
        return "grouping_grain"
    if _symptom_value(symptoms, "missing_filter_literals"):
        return "filter_scope"
    if _symptom_value(symptoms, "join_difference"):
        return "join_shape"
    if _symptom_value(symptoms, "missing_projections") or _symptom_value(
        symptoms, "extra_projections"
    ):
        return "projection"
    return "other_result_mismatch"


def _symptoms(
    *,
    question: str,
    gold: PredictionShape,
    predicted: PredictionShape,
    anchor_date: str,
    repair_trace: Sequence[tuple[str, str, str, str]],
) -> tuple[tuple[str, str], ...]:
    gold_projection = set(gold.projections)
    predicted_projection = set(predicted.projections)
    missing = sorted(gold_projection - predicted_projection)
    extra = sorted(predicted_projection - gold_projection)
    gold_groups = _groups(gold)
    predicted_groups = _groups(predicted)
    rows = [
        ("missing_projections", ",".join(missing)),
        ("extra_projections", ",".join(extra)),
        ("gold_group_by", " | ".join(gold_groups)),
        ("predicted_group_by", " | ".join(predicted_groups)),
        ("aggregation_only_in_cte", _cte_only(predicted)),
        ("missing_filter_literals", ",".join(_missing_literals(gold, predicted))),
        ("category_scope", _category_scope(question, predicted.sql or "")),
        ("join_difference", _join_difference(gold, predicted)),
        ("runtime_clock", "true" if _CLOCK.search(predicted.sql or "") else ""),
        ("recursive_cte", _recursive_symptom(predicted.sql or "")),
        ("repair_trace", _repair_symptom(repair_trace)),
    ]
    return tuple(rows)


def _repair_symptom(repair_trace: Sequence[tuple[str, str, str, str]]) -> str:
    return ";".join(
        f"{attempt}:{category}:{symptom}" for attempt, category, symptom, _sql_hash in repair_trace
    )


def _groups(shape: PredictionShape) -> tuple[str, ...]:
    if shape.scopes:
        return tuple(
            f"{scope.name}:{'、'.join(scope.group_by)}" for scope in shape.scopes if scope.group_by
        )
    return shape.group_by


def _cte_only(shape: PredictionShape) -> str:
    outer = next((scope for scope in shape.scopes if scope.name == "outer"), None)
    nested = [scope for scope in shape.scopes if scope.name != "outer" and scope.aggregations]
    if outer is not None and not outer.aggregations and nested:
        return ",".join(scope.name for scope in nested)
    return ""


def _missing_literals(gold: PredictionShape, predicted: PredictionShape) -> tuple[str, ...]:
    predicted_text = predicted.sql or ""
    missing: list[str] = []
    for literal in _LITERAL.findall(gold.sql or ""):
        labeled = literal in {"PAID", "CANCELLED"} or _looks_like_label(literal)
        if labeled and literal not in predicted_text:
            missing.append(literal)
    return tuple(dict.fromkeys(missing))


def _looks_like_label(literal: str) -> bool:
    if len(literal) < 2 or literal[:4].isdigit():
        return False
    return all(
        "\u4e00" <= char <= "\u9fff" or (char.isascii() and char.isalpha()) for char in literal
    )


def _category_scope(question: str, sql: str) -> str:
    contract = extract_answer_contract(question)
    lowered = sql.lower()
    expanded = "with recursive" in lowered or (
        "parent_id" in lowered and "一级" not in question and "末级" not in question
    )
    if contract.category_scope == "exact" and expanded:
        return "descendants"
    return ""


def _join_difference(gold: PredictionShape, predicted: PredictionShape) -> str:
    gold_joins = set(gold.joins)
    predicted_joins = set(predicted.joins)
    if gold_joins == predicted_joins:
        return ""
    return f"gold={len(gold_joins)};predicted={len(predicted_joins)}"


def _recursive_symptom(sql: str) -> str:
    lowered = sql.lower()
    if "with recursive" in lowered:
        return "declared"
    if re.search(r"\bwith\b", lowered) and "recursive" not in lowered:
        return "not_declared"
    return ""


def _time_mismatch(question: str, sql: str, anchor_date: str) -> bool:
    contract = extract_answer_contract(question, anchor_date=anchor_date)
    if contract.time_window is None:
        return False
    if _CLOCK.search(sql):
        return True
    start, end = contract.time_window
    return start not in sql or end not in sql


def _grain_mismatch(gold: PredictionShape, predicted: PredictionShape) -> bool:
    if _groups(gold) and not _groups(predicted):
        return True
    gold_aggs = _aggs(gold)
    predicted_aggs = _aggs(predicted)
    return bool(gold_aggs) and not predicted_aggs


def _aggs(shape: PredictionShape) -> set[str]:
    found = set(shape.aggregations)
    for scope in shape.scopes:
        found.update(scope.aggregations)
    return found


def _symptom_value(symptoms: tuple[tuple[str, str], ...], key: str) -> str:
    for name, value in symptoms:
        if name == key:
            return value
    return ""
