"""50 条慢 SQL Benchmark 用例定义。参考改写不在此模块。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

FULL_CASE_COUNT = 50
_SNAPSHOT = "ecommerce-v1"
_DATABASE = "ecommerce"
_DEFAULT_METRIC = {
    "primary_metric": "planner_cost",
    "min_primary_drop": 0.2,
    "max_secondary_regression": 0.5,
    "order_sensitive": False,
    "numeric_tolerance": None,
    "timeout_ms": 5000,
}


def _base(
    case_id: str,
    antipattern: str,
    sql: str,
    *,
    index_preconditions: Sequence[str] = (),
    allowed_rewrite_categories: Sequence[str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    categories = (
        list(allowed_rewrite_categories)
        if allowed_rewrite_categories is not None
        else [antipattern, "rewrite"]
    )
    payload: dict[str, Any] = {
        "id": case_id,
        "snapshot_version": _SNAPSHOT,
        "database_id": _DATABASE,
        "antipattern": antipattern,
        "sql": sql.strip() + "\n",
        "index_preconditions": list(index_preconditions),
        "allowed_rewrite_categories": categories,
        **_DEFAULT_METRIC,
    }
    payload.update(overrides)
    return payload


def full_slow_sql_case_payloads() -> list[dict[str, Any]]:
    """返回 50 条用例 dict，供 YAML 与单测校验。"""

    cases: list[dict[str, Any]] = []

    for index in range(1, 6):
        cases.append(
            _base(
                f"slow_select_star_{index:02d}",
                "select-star",
                f"SELECT * FROM t_order WHERE (user_id + {index - 1}) = {index}",
            )
        )

    for index in range(1, 6):
        cases.append(
            _base(
                f"slow_missing_filter_{index:02d}",
                "missing-filter-on-large-table",
                f"""
                SELECT detail_id, quantity, order_id
                FROM t_order_detail
                WHERE NOT EXISTS (SELECT 1 WHERE false)
                LIMIT {400 + index}
                """.strip(),
                primary_metric="execution_time",
                min_primary_drop=0.1,
            )
        )

    for index in range(1, 6):
        cases.append(
            _base(
                f"slow_function_index_{index:02d}",
                "function-on-index-column",
                f"SELECT order_id FROM t_order WHERE (user_id + {index - 1}) = {index}",
            )
        )

    for index in range(1, 6):
        cases.append(
            _base(
                f"slow_implicit_cast_{index:02d}",
                "implicit-cast-on-index-column",
                f"SELECT order_id FROM t_order WHERE user_id::text = '{index}'",
            )
        )

    for index in range(1, 6):
        cases.append(
            _base(
                f"slow_correlated_{index:02d}",
                "correlated-subquery",
                f"""
                SELECT o.order_id
                FROM t_order o
                WHERE o.total_amount > (
                  SELECT AVG(o2.total_amount)
                  FROM t_order o2
                  WHERE o2.user_id = o.user_id AND o2.order_status = 'paid'
                )
                AND o.user_id = {index}
                """.strip(),
            )
        )

    for index in range(1, 6):
        cases.append(
            _base(
                f"slow_agg_after_join_{index:02d}",
                "aggregate-after-join",
                f"""
                SELECT o.order_status, SUM(o.total_amount) AS amount
                FROM t_order o
                JOIN t_order_detail d ON d.order_id = o.order_id
                JOIN t_order_detail d2 ON d2.detail_id = d.detail_id
                WHERE o.user_id >= {index}
                GROUP BY o.order_status
                """.strip(),
            )
        )

    for index in range(1, 6):
        cases.append(
            _base(
                f"slow_unbounded_sort_{index:02d}",
                "unbounded-sort",
                f"""
                SELECT order_id, total_amount
                FROM t_order
                WHERE user_id <= {index + 4}
                ORDER BY created_at DESC, order_id
                """.strip(),
                primary_metric="execution_time",
                min_primary_drop=0.1,
            )
        )

    for index in range(1, 6):
        cases.append(
            _base(
                f"slow_repeated_distinct_{index:02d}",
                "repeated-distinct",
                f"""
                SELECT DISTINCT user_id
                FROM (
                  SELECT DISTINCT user_id FROM t_order WHERE (user_id + {index - 1}) = {index}
                ) nested
                """.strip(),
            )
        )

    for index in range(1, 6):
        cases.append(
            _base(
                f"slow_redundant_join_{index:02d}",
                "redundant-join",
                f"""
                SELECT o.order_id
                FROM t_order o
                JOIN t_user u ON u.user_id = o.user_id
                JOIN t_region r ON r.region_id = u.user_id
                JOIN t_user u2 ON u2.user_id = u.user_id
                WHERE o.user_id = {index}
                """.strip(),
            )
        )

    for index in range(1, 6):
        cases.append(
            _base(
                f"slow_seq_scan_{index:02d}",
                "seq-scan-on-large-table",
                f"""
                SELECT d.detail_id, d.quantity
                FROM t_order_detail d
                WHERE d.order_id NOT IN (
                  SELECT o.order_id FROM t_order o WHERE o.user_id <> {index}
                )
                """.strip(),
                index_preconditions=["DROP INDEX IF EXISTS idx_order_status"],
            )
        )

    if len(cases) != FULL_CASE_COUNT:
        raise RuntimeError(f"expected {FULL_CASE_COUNT} slow sql cases, got {len(cases)}")
    return cases
