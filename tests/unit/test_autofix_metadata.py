"""元数据驱动的慢 SQL autofix。"""

from __future__ import annotations

from app.agents.slow_sql.autofix import try_autofix_sql
from app.agents.slow_sql.optimizer_context import OptimizerContext
from app.agents.slow_sql.rule_catalog import RuleCatalog
from app.agents.slow_sql.rules import Finding


def _finding(rule_id: str) -> Finding:
    return Finding(rule_id=rule_id, severity="high", message=rule_id)


def test_expand_select_star_uses_optimizer_context_columns() -> None:
    context = OptimizerContext(
        database_id="demo",
        schema_name="public",
        catalog=RuleCatalog(frozenset(), frozenset(), frozenset()),
        table_columns={"items": ("item_id", "name")},
        schema_fingerprint="sha256:abc",
    )
    sql = "SELECT * FROM items"
    fixed = try_autofix_sql(sql, (_finding("select-star"),), context=context)
    assert fixed is not None
    assert "item_id" in fixed
    assert "name" in fixed
    assert "*" not in fixed


def test_large_table_guard_uses_catalog_not_hardcoded_only() -> None:
    catalog = RuleCatalog(
        large_tables=frozenset({"events"}),
        child_tables=frozenset(),
        indexed_columns=frozenset({("events", "event_id")}),
    )
    context = OptimizerContext(
        database_id="demo",
        schema_name="public",
        catalog=catalog,
        table_columns={"events": ("event_id", "payload")},
        schema_fingerprint=None,
    )
    sql = "SELECT payload FROM events"
    fixed = try_autofix_sql(
        sql,
        (_finding("missing-filter-on-large-table"),),
        context=context,
        catalog=catalog,
    )
    assert fixed is not None
    assert "event_id IS NOT NULL" in fixed
