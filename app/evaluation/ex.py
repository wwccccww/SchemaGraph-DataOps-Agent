"""Execution Accuracy 的语义比较。"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

Cell = tuple[str, str]


def results_match(
    actual: Sequence[Sequence[object]],
    expected: Sequence[Sequence[object]],
    *,
    order_sensitive: bool,
    numeric_tolerance: float | None = None,
) -> bool:
    """列数和列顺序必须一致。无顺序要求时按多重集合比较。"""

    if len(actual) != len(expected):
        return False
    if not actual:
        return True
    width = len(expected[0])
    if any(len(row) != width for row in actual) or any(len(row) != width for row in expected):
        return False
    actual_rows = [_row(row) for row in actual]
    expected_rows = [_row(row) for row in expected]
    if numeric_tolerance is None:
        if not order_sensitive:
            actual_rows.sort()
            expected_rows.sort()
        return actual_rows == expected_rows
    if order_sensitive:
        return all(
            _rows_close(left, right, numeric_tolerance)
            for left, right in zip(actual_rows, expected_rows, strict=True)
        )
    return _multiset_close(actual_rows, expected_rows, numeric_tolerance)


def canonical_cell(value: object) -> Cell:
    """把一个单元格归一成可比较的类型标记和文本。"""

    if value is None:
        return ("null", "")
    if isinstance(value, bool):
        return ("bool", "true" if value else "false")
    if isinstance(value, int):
        return ("decimal", str(value))
    if isinstance(value, Decimal):
        if not value.is_finite():
            return ("decimal_nonfinite", str(value))
        return ("decimal", format(value, "f"))
    if isinstance(value, float):
        if math.isnan(value):
            return ("float_nan", "nan")
        if math.isinf(value):
            return ("float_inf", "inf" if value > 0 else "-inf")
        return ("decimal", format(Decimal(str(value)), "f"))
    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return ("timestamp", moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    if isinstance(value, date):
        return ("date", value.isoformat())
    if isinstance(value, str):
        return ("string", value.strip())
    return ("string", str(value).strip())


def _row(row: Sequence[object]) -> tuple[Cell, ...]:
    return tuple(canonical_cell(cell) for cell in row)


def _rows_close(
    actual: Sequence[Cell],
    expected: Sequence[Cell],
    tolerance: float,
) -> bool:
    return all(
        _cells_close(left, right, tolerance) for left, right in zip(actual, expected, strict=True)
    )


def _cells_close(actual: Cell, expected: Cell, tolerance: float) -> bool:
    if actual[0] != expected[0]:
        return False
    if actual[0] != "decimal":
        return actual == expected
    return abs(Decimal(actual[1]) - Decimal(expected[1])) <= Decimal(str(tolerance))


def _multiset_close(
    actual: list[tuple[Cell, ...]],
    expected: list[tuple[Cell, ...]],
    tolerance: float,
) -> bool:
    unmatched = list(expected)
    for row in actual:
        for index, candidate in enumerate(unmatched):
            if _rows_close(row, candidate, tolerance):
                unmatched.pop(index)
                break
        else:
            return False
    return not unmatched
