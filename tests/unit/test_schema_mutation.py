"""Schema 变更场景（内存快照，不依赖数据库）。"""

from __future__ import annotations

from app.db.catalog import table_content_hash
from app.schema_registry.diff import diff_snapshots
from app.schema_registry.registry import SchemaRegistry
from app.schema_registry.snapshot import SchemaSnapshot
from app.schemas.catalog import ColumnDocument, TableDocument


def _table(name: str) -> TableDocument:
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


def test_add_table_changes_fingerprint_and_registry_staging() -> None:
    registry = SchemaRegistry()
    v1 = SchemaSnapshot.build(
        database_id="demo",
        schema_name="public",
        documents=(_table("orders"),),
        edges=(),
    )
    registry.register(v1, activate=True)
    v2 = SchemaSnapshot.build(
        database_id="demo",
        schema_name="public",
        documents=(_table("orders"), _table("customers")),
        edges=(),
    )
    diff = registry.register(v2, activate=False)
    assert diff is not None
    assert diff.added_tables == ("customers",)
    assert registry.staging_fingerprint("demo") == v2.fingerprint
    registry.activate("demo", v2.fingerprint)
    assert registry.active_snapshot("demo") == v2


def test_remove_table_detected_in_diff() -> None:
    before = SchemaSnapshot.build(
        database_id="demo",
        schema_name="public",
        documents=(_table("a"), _table("b")),
        edges=(),
    )
    after = SchemaSnapshot.build(
        database_id="demo",
        schema_name="public",
        documents=(_table("a"),),
        edges=(),
    )
    diff = diff_snapshots(before, after)
    assert diff.removed_tables == ("b",)
    assert diff.is_empty is False
