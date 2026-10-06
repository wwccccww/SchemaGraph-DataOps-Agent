"""SQLite 只读静态校验。"""

from __future__ import annotations

from app.sandbox.sqlite import check_sqlite_read_only


def test_semicolon_inside_group_concat_string_is_allowed() -> None:
    sql = (
        "SELECT GROUP_CONCAT(category || ': ' || cnt, '; ') AS breakdown "
        "FROM (SELECT 'High' AS category, 3 AS cnt)"
    )
    assert check_sqlite_read_only(sql) is not None


def test_multiple_statements_still_rejected() -> None:
    assert check_sqlite_read_only("SELECT 1; SELECT 2") is None
