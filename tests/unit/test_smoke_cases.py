"""冒烟 Gold SQL 的静态审计。"""

from __future__ import annotations

import re
from datetime import date

from app.evaluation.smoke import canonical_rows, load_smoke_cases, single_statement

_TABLE = re.compile(r"\bt_[a-z0-9_]+\b")
_LIMITS = {
    "basic": range(1, 4),
    "medium": range(4, 7),
    "complex": range(7, 13),
}


def test_smoke_file_has_ten_audited_cases() -> None:
    cases = load_smoke_cases()

    assert [case.id for case in cases] == [
        "smoke_basic_001",
        "smoke_basic_002",
        "smoke_basic_003",
        "smoke_medium_001",
        "smoke_medium_002",
        "smoke_medium_003",
        "smoke_complex_001",
        "smoke_complex_002",
        "smoke_complex_003",
        "smoke_complex_004",
    ]
    assert [case.difficulty for case in cases].count("basic") == 3
    assert [case.difficulty for case in cases].count("medium") == 3
    assert [case.difficulty for case in cases].count("complex") == 4
    complex_with_junction = [
        case for case in cases if case.difficulty == "complex" and case.required_junctions
    ]
    assert len(complex_with_junction) >= 2

    for case in cases:
        assert case.source == "custom"
        assert case.anchor_date == date(2026, 10, 1)
        assert case.numeric_tolerance is None
        assert case.order_sensitive is ("升序" in case.question)
        statement = single_statement(case.gold_sql)
        assert "now()" not in statement.lower()
        assert "current_timestamp" not in statement.lower()
        referenced = set(_TABLE.findall(statement))
        declared = set(case.required_tables) | set(case.required_junctions)
        assert referenced == declared
        assert len(declared) in _LIMITS[case.difficulty]
        if case.order_sensitive:
            assert re.search(r"\bORDER\s+BY\b", statement, re.IGNORECASE)
        else:
            assert re.search(r"\bORDER\s+BY\b", statement, re.IGNORECASE) is None


def test_unordered_results_compare_as_multisets() -> None:
    left = [(2, "b"), (1, "a"), (1, "a")]
    right = [(1, "a"), (2, "b"), (1, "a")]

    assert canonical_rows(left, order_sensitive=False) == canonical_rows(
        right, order_sensitive=False
    )
    assert canonical_rows(left, order_sensitive=True) != canonical_rows(right, order_sensitive=True)
