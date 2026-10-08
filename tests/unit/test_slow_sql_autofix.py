"""慢 SQL 确定性改写。"""

from __future__ import annotations

from app.agents.slow_sql.autofix import try_autofix_sql
from app.agents.slow_sql.rules import Finding, diagnose_sql


def _finding(rule_id: str) -> Finding:
    return Finding(rule_id, "high", rule_id)


def test_autofix_implicit_cast() -> None:
    sql = "SELECT order_id FROM t_order WHERE user_id::text = '3'"
    out = try_autofix_sql(sql, [_finding("implicit-cast-on-index-column")])
    assert out == "SELECT order_id FROM t_order WHERE user_id = 3"


def test_autofix_function_on_index() -> None:
    sql = "SELECT order_id FROM t_order WHERE (user_id + 2) = 5"
    out = try_autofix_sql(sql, [_finding("function-on-index-column")])
    assert out == "SELECT order_id FROM t_order WHERE user_id = 3"


def test_autofix_select_star_expands_order_columns() -> None:
    sql = "SELECT * FROM t_order WHERE user_id = 1"
    out = try_autofix_sql(sql, [_finding("select-star")])
    assert out is not None
    assert "SELECT *" not in out.upper()
    assert "order_id" in out and "user_id" in out


def test_autofix_agg_after_join_uses_preaggregate() -> None:
    sql = """
    SELECT o.order_status, SUM(o.total_amount) AS amount
    FROM t_order o
    JOIN t_order_detail d ON d.order_id = o.order_id
    JOIN t_order_detail d2 ON d2.detail_id = d.detail_id
    WHERE o.user_id >= 2
    GROUP BY o.order_status
    """.strip()
    out = try_autofix_sql(sql, [_finding("aggregate-after-join")])
    assert out is not None
    assert "line_count" in out
    assert "d2" not in out


def test_autofix_missing_filter_strips_noop_exists() -> None:
    sql = (
        "SELECT detail_id FROM t_order_detail "
        "WHERE NOT EXISTS (SELECT 1 WHERE false) LIMIT 401"
    )
    out = try_autofix_sql(sql, [_finding("missing-filter-on-large-table")])
    assert out == "SELECT detail_id FROM t_order_detail LIMIT 401"


def test_autofix_unbounded_sort_strips_order_by() -> None:
    sql = (
        "SELECT order_id, total_amount FROM t_order "
        "WHERE user_id <= 5 ORDER BY created_at DESC, order_id"
    )
    out = try_autofix_sql(sql, [_finding("unbounded-sort")])
    assert out is not None
    assert "ORDER BY" not in out.upper()


def test_autofix_redundant_join_collapses_to_order_scan() -> None:
    sql = """
    SELECT o.order_id
    FROM t_order o
    JOIN t_user u ON u.user_id = o.user_id
    JOIN t_region r ON r.region_id = u.user_id
    JOIN t_user u2 ON u2.user_id = u.user_id
    WHERE o.user_id = 2
    """.strip()
    out = try_autofix_sql(sql, [_finding("redundant-join")])
    assert out == "SELECT order_id FROM t_order WHERE user_id = 2"


def test_autofix_repeated_distinct_flattens_and_fixes_index_expr() -> None:
    sql = """
    SELECT DISTINCT user_id
    FROM (
      SELECT DISTINCT user_id FROM t_order WHERE (user_id + 1) = 2
    ) nested
    """.strip()
    out = try_autofix_sql(sql, diagnose_sql(sql))
    assert out is not None
    assert "nested" not in out
    assert "user_id = 1" in out


def test_full_agg_cases_still_flag_aggregate_after_join() -> None:
    from app.evaluation.slow_sql_catalog import full_slow_sql_case_payloads

    for payload in full_slow_sql_case_payloads():
        if payload["id"].startswith("slow_agg_after_join"):
            findings = {item.rule_id for item in diagnose_sql(payload["sql"])}
            assert "aggregate-after-join" in findings
