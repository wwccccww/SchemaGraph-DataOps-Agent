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


def test_full_agg_cases_still_flag_aggregate_after_join() -> None:
    from app.evaluation.slow_sql_catalog import full_slow_sql_case_payloads

    for payload in full_slow_sql_case_payloads():
        if payload["id"].startswith("slow_agg_after_join"):
            findings = {item.rule_id for item in diagnose_sql(payload["sql"])}
            assert "aggregate-after-join" in findings
