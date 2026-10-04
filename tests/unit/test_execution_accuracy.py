"""EX 比较列顺序和多重集合，不比较别名。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.evaluation.ex import canonical_cell, results_match


def test_unordered_rows_match_as_a_multiset() -> None:
    actual = [("b", 2), ("a", 1), ("a", 1)]
    expected = [("a", Decimal("1")), ("b", Decimal("2")), ("a", 1)]

    assert results_match(actual, expected, order_sensitive=False) is True
    assert results_match(actual, expected, order_sensitive=True) is False


def test_column_count_mismatch_fails() -> None:
    assert results_match([[1, 2]], [[1]], order_sensitive=False) is False


def test_null_bool_and_text_keep_their_types() -> None:
    assert canonical_cell(None) == ("null", "")
    assert canonical_cell(True) != canonical_cell(1)
    assert canonical_cell(" 华东 ") == ("string", "华东")
    assert canonical_cell("华东") == canonical_cell("华东 ")
    assert canonical_cell("华 东") != canonical_cell("华东")
    assert results_match([[None]], [[None]], order_sensitive=True) is True


def test_timestamps_are_compared_in_utc() -> None:
    naive = datetime(2026, 10, 1, 8, 0, 0)
    aware = datetime(2026, 10, 1, 8, 0, 0, tzinfo=UTC)

    assert canonical_cell(naive) == canonical_cell(aware)
    assert canonical_cell(naive)[1].endswith("Z")


def test_numeric_tolerance_is_explicit() -> None:
    actual = [[Decimal("10.01")]]
    expected = [[Decimal("10.00")]]

    assert results_match(actual, expected, order_sensitive=False) is False
    assert results_match(actual, expected, order_sensitive=False, numeric_tolerance=0.02) is True


def test_nonfinite_floats_are_distinct() -> None:
    assert canonical_cell(float("nan")) != canonical_cell(float("inf"))
    assert canonical_cell(float("inf")) != canonical_cell(float("-inf"))
