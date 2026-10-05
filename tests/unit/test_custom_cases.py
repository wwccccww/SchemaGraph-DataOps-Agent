"""132 条自建用例的静态审计。不连接数据库。"""

from __future__ import annotations

import re
from datetime import date

from app.db.tables import JUNCTION_TABLES
from app.evaluation.custom_cases import (
    _SMOKE_IDS,
    CUSTOM_CASE_COUNTS,
    build_custom_cases,
    load_custom_cases,
    normalize_sql,
    referenced_tables,
)
from app.evaluation.smoke import load_smoke_cases, single_statement
from app.sandbox.gate import check_read_only_sql

_LIMITS = {
    "basic": range(1, 4),
    "medium": range(4, 7),
    "complex": range(7, 13),
}


def test_frozen_file_matches_the_builder() -> None:
    built = [case.model_dump(mode="json") for case in build_custom_cases()]
    loaded = [case.model_dump(mode="json") for case in load_custom_cases()]

    assert loaded == built


def test_custom_cases_match_the_static_contract() -> None:
    cases = load_custom_cases()
    questions = [case.question for case in cases]
    normalized = [normalize_sql(case.gold_sql) for case in cases]

    assert [case.difficulty for case in cases].count("basic") == CUSTOM_CASE_COUNTS["basic"]
    assert [case.difficulty for case in cases].count("medium") == CUSTOM_CASE_COUNTS["medium"]
    assert [case.difficulty for case in cases].count("complex") == CUSTOM_CASE_COUNTS["complex"]
    assert len(questions) == len(set(questions))
    assert len(normalized) == len(set(normalized))
    complex_with_junction = [
        case for case in cases if case.difficulty == "complex" and case.required_junctions
    ]
    assert len(complex_with_junction) >= 2

    for case in cases:
        assert case.source == "custom"
        assert case.source_version == "ecommerce-v1"
        assert case.database_id == "ecommerce"
        assert case.dialect == "postgres"
        assert case.anchor_date == date(2026, 10, 1)
        assert case.numeric_tolerance is None
        assert case.order_sensitive is ("升序" in case.question)
        statement = single_statement(case.gold_sql)
        lowered = statement.lower()
        assert "now()" not in lowered
        assert "current_timestamp" not in lowered
        assert check_read_only_sql(statement).error is None
        referenced = referenced_tables(statement)
        declared = set(case.required_tables) | set(case.required_junctions)
        assert referenced == declared
        assert set(case.required_junctions) == referenced & set(JUNCTION_TABLES)
        assert set(case.required_tables).isdisjoint(JUNCTION_TABLES)
        assert len(declared) in _LIMITS[case.difficulty]
        ordered = re.search(r"\bORDER\s+BY\b", statement, re.IGNORECASE)
        if case.order_sensitive:
            assert ordered
        else:
            assert ordered is None


def test_python_oracle_attestation_covers_every_case() -> None:
    from app.evaluation.gold_oracle import ensure_oracle_matched

    cases = load_custom_cases()
    ensure_oracle_matched(cases)
    leaf = next(case for case in cases if case.id == "custom_basic_048")
    last_month = next(case for case in cases if case.id == "custom_complex_001")
    assert leaf.semantic_contract is not None
    assert "末级品类定义为 parent_id <> 0" in leaf.semantic_contract.filters
    assert leaf.semantic_contract.category_scope == "exact"
    assert last_month.semantic_contract is not None
    assert last_month.semantic_contract.time_window is not None
    assert last_month.semantic_contract.time_window.start == "2026-09-01 00:00:00"
    assert last_month.semantic_contract.dedup_key == "order_id"
    assert last_month.oracle is not None
    assert last_month.oracle.method == "python"
    assert all(
        case.semantic_contract is not None
        and case.semantic_contract.category_scope == "exact"
        and case.oracle is not None
        and case.oracle.row_count > 0
        for case in cases
    )


def test_smoke_slice_is_copied_into_the_full_suite() -> None:
    smoke = {case.id: case for case in load_smoke_cases()}
    full = {case.id: case for case in load_custom_cases()}

    for old_id, new_id in _SMOKE_IDS:
        assert full[new_id].question == smoke[old_id].question
        assert full[new_id].gold_sql.strip() == smoke[old_id].gold_sql.strip()
        assert full[new_id].required_tables == smoke[old_id].required_tables
        assert full[new_id].required_junctions == smoke[old_id].required_junctions
