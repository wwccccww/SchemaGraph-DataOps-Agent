"""静态规则覆盖文档中的反模式，并且不把字面量运算误判为索引失效。"""

from __future__ import annotations

import pytest
from app.agents.slow_sql.rules import diagnose_sql, finding_for_seq_scan
from app.agents.slow_sql.snapshot import validate_index_precondition

_CAST_MESSAGE = "索引列发生隐式类型转换"


def _ids(sql: str) -> set[str]:
    return {item.rule_id for item in diagnose_sql(sql)}


def test_each_static_rule_has_a_stable_id() -> None:
    samples = {
        "select-star": "SELECT * FROM t_order",
        "missing-filter-on-large-table": "SELECT order_id FROM t_order_detail",
        "function-on-index-column": "SELECT order_id FROM t_order WHERE (user_id + 0) = 1",
        "implicit-cast-on-index-column": "SELECT order_id FROM t_order WHERE user_id::text = '1'",
        "correlated-subquery": (
            "SELECT d.detail_id FROM t_order_detail AS d "
            "WHERE EXISTS (SELECT 1 FROM t_order AS o WHERE o.order_id = d.order_id)"
        ),
        "aggregate-after-join": (
            "SELECT o.order_status, SUM(o.total_amount) AS amount FROM t_order AS o "
            "JOIN t_order_detail AS d ON d.order_id = o.order_id GROUP BY o.order_status"
        ),
        "unbounded-sort": "SELECT order_id FROM t_order ORDER BY created_at",
        "repeated-distinct": (
            "SELECT DISTINCT order_status, COUNT(DISTINCT user_id) "
            "FROM t_order GROUP BY order_status"
        ),
        "redundant-join": (
            "SELECT o.order_id FROM t_order AS o JOIN t_user AS u ON u.user_id = o.user_id"
        ),
    }
    for rule_id, sql in samples.items():
        assert rule_id in _ids(sql)


def test_implicit_cast_message_matches_the_api_example() -> None:
    findings = diagnose_sql("SELECT order_id FROM t_order WHERE user_id::text = '1'")
    matched = [item for item in findings if item.rule_id == "implicit-cast-on-index-column"]
    assert len(matched) == 1
    assert matched[0].message == _CAST_MESSAGE


def test_literal_expression_and_literal_cast_are_not_index_findings() -> None:
    arithmetic = _ids("SELECT order_id FROM t_order WHERE user_id = 1 + 0")
    literal_cast = _ids("SELECT order_id FROM t_order WHERE order_status = CAST('paid' AS TEXT)")
    limited = _ids("SELECT order_id FROM t_order ORDER BY created_at LIMIT 10")
    child_aggregate = _ids(
        "SELECT d.order_id, SUM(d.quantity) FROM t_order AS o "
        "JOIN t_order_detail AS d ON d.order_id = o.order_id GROUP BY d.order_id"
    )
    assert "function-on-index-column" not in arithmetic
    assert "implicit-cast-on-index-column" not in literal_cast
    assert "unbounded-sort" not in limited
    assert "aggregate-after-join" not in child_aggregate


def test_filter_inside_join_condition_is_not_a_redundant_join() -> None:
    sql = (
        "SELECT o.order_id FROM t_order AS o "
        "JOIN t_user AS u ON u.user_id = o.user_id AND u.username = 'a'"
    )
    assert "redundant-join" not in _ids(sql)


def test_filtered_large_table_is_not_missing_a_predicate() -> None:
    assert "missing-filter-on-large-table" not in _ids(
        "SELECT order_id FROM t_order WHERE user_id = 1"
    )


def test_seq_scan_finding_comes_from_the_plan_node() -> None:
    finding = finding_for_seq_scan([("Index Scan", "t_order"), ("Seq Scan", "t_order_detail")])
    assert finding is not None
    assert finding.rule_id == "seq-scan-on-large-table"
    assert finding_for_seq_scan([("Index Scan", "t_order")]) is None


def test_index_precondition_accepts_only_index_ddl() -> None:
    rendered = validate_index_precondition("DROP INDEX IF EXISTS idx_order_status")
    assert rendered.startswith("DROP INDEX")
    assert "idx_order_status" in rendered
    created = validate_index_precondition("CREATE INDEX idx_example ON t_order (user_id)")
    assert created.startswith("CREATE INDEX")
    with pytest.raises(ValueError):
        validate_index_precondition("DELETE FROM t_order")
    with pytest.raises(ValueError):
        validate_index_precondition("DROP INDEX a; DROP INDEX b")
    with pytest.raises(ValueError):
        validate_index_precondition("CREATE INDEX idx_example ON t_order ((user_id + 0))")
