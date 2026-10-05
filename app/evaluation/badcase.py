"""把一条预测归入互斥主类，并保留非互斥症状。

分类可以读取 Gold，因为它只运行在评测进程里，不进入生成或修复 Prompt。
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.agents.text_to_sql.contract import extract_answer_contract
from app.agents.text_to_sql.semantic import SemanticFinding, check_fact_grain
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
        "missing_fact_dedup",
        "refanout_after_dedup",
        "aggregate_over_fanout",
        "unstable_group_key",
        "wrong_entity_literal",
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
    dialect: str = "postgres",
) -> tuple[str, tuple[tuple[str, str], ...]]:
    """返回主类和症状。主类按固定优先级只取一个。"""

    predicted = describe_sql(predicted_sql, dialect=dialect)
    gold = describe_sql(gold_sql, dialect=dialect)
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
    if _fact_grain(symptoms):
        return "fact_grain"
    if _response_shape(symptoms):
        return "response_shape"
    if _symptom_value(symptoms, "missing_filter_literals"):
        return "filter_scope"
    if _join_semantics(gold.sql or "", predicted.sql or "", symptoms):
        return "join_semantics"
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
    predicted_findings = check_fact_grain(predicted.sql or "")
    missing = sorted(gold_projection - predicted_projection)
    extra = sorted(predicted_projection - gold_projection)
    gold_groups = _groups(gold)
    predicted_groups = _groups(predicted)
    rows = [
        ("missing_projections", ",".join(missing)),
        ("extra_projections", ",".join(extra)),
        ("projection_order", _projection_order(gold, predicted)),
        ("gold_group_by", " | ".join(gold_groups)),
        ("predicted_group_by", " | ".join(predicted_groups)),
        ("aggregation_only_in_cte", _cte_only(predicted)),
        ("missing_output_labels", ",".join(_missing_output_labels(gold, predicted))),
        ("missing_filter_literals", ",".join(_missing_filter_literals(gold, predicted))),
        ("missing_dedup_key", _symptom_flag(predicted_findings, "missing_fact_dedup")),
        ("refanout_after_dedup", _symptom_flag(predicted_findings, "refanout_after_dedup")),
        (
            "aggregate_source_grain",
            _symptom_flag(predicted_findings, "aggregate_over_fanout"),
        ),
        ("missing_group_identifier", _missing_group_identifier(gold, predicted)),
        ("wrong_entity_literal", _wrong_entity_literal(gold, predicted)),
        ("category_scope", _category_scope(question, predicted.sql or "")),
        ("join_shape_difference", _join_difference(gold, predicted)),
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


def _fact_grain(symptoms: tuple[tuple[str, str], ...]) -> bool:
    return any(
        _symptom_value(symptoms, name)
        for name in (
            "missing_dedup_key",
            "refanout_after_dedup",
            "aggregate_source_grain",
        )
    )


def _symptom_flag(findings: tuple[SemanticFinding, ...], category: str) -> str:
    messages = [item.message for item in findings if item.category == category]
    return messages[0] if messages else ""


def _missing_group_identifier(gold: PredictionShape, predicted: PredictionShape) -> str:
    gold_text = " ".join(_groups(gold)).lower()
    predicted_text = " ".join(_groups(predicted)).lower()
    missing = [
        key
        for key in ("merchant_id", "category_id", "detail_id", "order_id")
        if key in gold_text and key not in predicted_text
    ]
    return ",".join(missing)


def _wrong_entity_literal(gold: PredictionShape, predicted: PredictionShape) -> str:
    predicted_text = predicted.sql or ""
    quoted = _quoted_literals(predicted_text)
    wrong = [
        literal
        for literal in _where_literals(gold.sql or "")
        if _is_label(literal)
        and f"'{literal}'" not in predicted_text
        and any(token.startswith(literal) and token != literal for token in quoted)
    ]
    return ",".join(dict.fromkeys(wrong))


def _quoted_literals(sql: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_LITERAL.findall(sql)))


def _response_shape(symptoms: tuple[tuple[str, str], ...]) -> bool:
    return any(
        _symptom_value(symptoms, name)
        for name in (
            "missing_projections",
            "extra_projections",
            "projection_order",
            "missing_output_labels",
        )
    )


def _join_semantics(
    gold_sql: str,
    predicted_sql: str,
    symptoms: tuple[tuple[str, str], ...],
) -> bool:
    if not _symptom_value(symptoms, "join_shape_difference"):
        return False
    gold_dedup = "distinct" in gold_sql.lower() and "order_id" in gold_sql.lower()
    predicted_dedup = "distinct" in predicted_sql.lower() and "order_id" in predicted_sql.lower()
    if gold_dedup and not predicted_dedup:
        return True
    gold_groups = _symptom_value(symptoms, "gold_group_by")
    predicted_groups = _symptom_value(symptoms, "predicted_group_by")
    if not gold_groups or not predicted_groups or gold_groups == predicted_groups:
        return False
    if _group_by_equivalent(gold_groups, predicted_groups):
        return False
    return True


def _group_by_equivalent(gold: str, predicted: str) -> bool:
    """表别名不同但分组列相同时不算 Join 语义错误。"""

    return _group_by_tokens(gold) == _group_by_tokens(predicted)


def _group_by_tokens(text: str) -> frozenset[str]:
    parts = re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", text.lower())
    return frozenset(part.split(".")[-1] for part in parts if part)


def _projection_order(gold: PredictionShape, predicted: PredictionShape) -> str:
    if gold.projections == predicted.projections:
        return ""
    if set(gold.projections) != set(predicted.projections):
        return ""
    return f"gold={','.join(gold.projections)};predicted={','.join(predicted.projections)}"


def _missing_output_labels(gold: PredictionShape, predicted: PredictionShape) -> tuple[str, ...]:
    predicted_text = predicted.sql or ""
    missing = [
        literal
        for literal in _select_literals(gold.sql or "")
        if _is_label(literal) and f"'{literal}'" not in predicted_text
    ]
    return tuple(dict.fromkeys(missing))


def _missing_filter_literals(gold: PredictionShape, predicted: PredictionShape) -> tuple[str, ...]:
    predicted_text = predicted.sql or ""
    output_labels = set(_select_literals(gold.sql or ""))
    missing = [
        literal
        for literal in _where_literals(gold.sql or "")
        if literal not in output_labels
        and _is_label(literal)
        and f"'{literal}'" not in predicted_text
    ]
    return tuple(dict.fromkeys(missing))


def _select_literals(sql: str) -> tuple[str, ...]:
    if not sql.strip():
        return ()
    try:
        expression = sqlglot.parse_one(sql, read="postgres")
    except SqlglotError:
        return ()
    outer = expression if isinstance(expression, exp.Select) else expression.find(exp.Select)
    if not isinstance(outer, exp.Select):
        return ()
    found: list[str] = []
    for projection in outer.expressions:
        found.extend(_LITERAL.findall(projection.sql(dialect="postgres")))
    return tuple(dict.fromkeys(found))


def _where_literals(sql: str) -> tuple[str, ...]:
    return _literals_in(sql, exp.Where, exp.Having)


def _literals_in(sql: str, *kinds: type[exp.Expression]) -> tuple[str, ...]:
    if not sql.strip():
        return ()
    try:
        expression = sqlglot.parse_one(sql, read="postgres")
    except SqlglotError:
        return ()
    found: list[str] = []
    for kind in kinds:
        for node in expression.find_all(kind):
            found.extend(_LITERAL.findall(node.sql(dialect="postgres")))
    return tuple(dict.fromkeys(found))


def _is_label(literal: str) -> bool:
    if literal in {"PAID", "CANCELLED"}:
        return True
    return _looks_like_label(literal)


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
    if not sql.strip():
        return ""
    try:
        expression = sqlglot.parse_one(sql, read="postgres")
    except SqlglotError:
        return ""
    for clause in expression.find_all(exp.With):
        recursive = bool(clause.args.get("recursive"))
        for cte in clause.find_all(exp.CTE):
            name = cte.alias if isinstance(cte.alias, str) else ""
            body = cte.this
            if not name or not isinstance(body, exp.Expression):
                continue
            refers_to_self = any(table.name == name for table in body.find_all(exp.Table))
            if refers_to_self and not recursive:
                return "self_reference"
            if refers_to_self and recursive:
                return "declared"
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
