"""RuleCatalog 构建。"""

from __future__ import annotations

from app.agents.slow_sql.rule_catalog import TableStat, build_rule_catalog
from app.db.catalog import table_content_hash
from app.schemas.catalog import ColumnDocument, TableDocument


def _doc(name: str) -> TableDocument:
    columns = [ColumnDocument(name="id", data_type="bigint", nullable=False, comment="pk")]
    return TableDocument(
        database_id="demo",
        schema_name="public",
        table_name=name,
        table_comment="t",
        columns=columns,
        is_junction=False,
        content_hash=table_content_hash(name, "t", columns),
    )


def test_build_rule_catalog_marks_large_table_from_stats() -> None:
    docs = (_doc("t_order"), _doc("tiny"))
    stats = {
        "tiny": TableStat(est_rows=100, total_bytes=1000),
        "t_order": TableStat(est_rows=20_000, total_bytes=1_000),
    }
    catalog = build_rule_catalog(docs, stats, frozenset({("t_order", "user_id")}))
    assert "t_order" in catalog.large_tables
    assert "tiny" not in catalog.large_tables
    assert ("t_order", "user_id") in catalog.indexed_columns
