"""Schema 快照、Diff 与 Registry。"""

from __future__ import annotations

from app.db.catalog import table_content_hash
from app.schema_registry.diff import diff_snapshots
from app.schema_registry.registry import SchemaRegistry
from app.schema_registry.snapshot import SchemaSnapshot, snapshot_fingerprint
from app.schemas.catalog import ColumnDocument, SchemaEdge, TableDocument


def _table(name: str, *, comment: str = "实体") -> TableDocument:
    columns = [
        ColumnDocument(name="id", data_type="bigint", nullable=False, comment="主键"),
    ]
    return TableDocument(
        database_id="demo",
        schema_name="public",
        table_name=name,
        table_comment=comment,
        columns=columns,
        is_junction=False,
        content_hash=table_content_hash(name, comment, columns),
    )


def _edge(name: str, source: str, target: str) -> SchemaEdge:
    return SchemaEdge(
        source_table=source,
        source_columns=["id"],
        target_table=target,
        target_columns=["id"],
        constraint_name=name,
        weight=1.0,
        inferred=False,
        confidence=1.0,
    )


def test_fingerprint_stable_for_same_catalog() -> None:
    docs = (_table("a"), _table("b"))
    edges = (_edge("fk1", "a", "b"),)
    left = snapshot_fingerprint(docs, edges)
    right = snapshot_fingerprint(docs, edges)
    assert left == right


def test_diff_detects_table_and_edge_changes() -> None:
    before = SchemaSnapshot.build(
        database_id="demo",
        schema_name="public",
        documents=(_table("a"), _table("b")),
        edges=(_edge("fk1", "a", "b"),),
    )
    changed_b = _table("b")
    changed_b = changed_b.model_copy(
        update={
            "columns": [
                ColumnDocument(name="id", data_type="bigint", nullable=False, comment="主键"),
                ColumnDocument(name="extra", data_type="text", nullable=True, comment="新列"),
            ]
        }
    )
    changed_b = changed_b.model_copy(
        update={"content_hash": table_content_hash("b", "实体", changed_b.columns)}
    )
    after = SchemaSnapshot.build(
        database_id="demo",
        schema_name="public",
        documents=(_table("a"), changed_b, _table("c")),
        edges=(_edge("fk2", "a", "c"),),
    )
    diff = diff_snapshots(before, after)
    assert diff.added_tables == ("c",)
    assert diff.removed_tables == ()
    assert diff.changed_tables == ("b",)
    assert "fk1" in diff.removed_edges
    assert "fk2" in diff.added_edges


def test_registry_activate_and_lookup() -> None:
    registry = SchemaRegistry()
    snap = SchemaSnapshot.build(
        database_id="demo",
        schema_name="public",
        documents=(_table("a"),),
        edges=(),
    )
    registry.register(snap, activate=True)
    active = registry.active_snapshot("demo")
    assert active is not None
    assert active.fingerprint == snap.fingerprint
    assert registry.get("demo", snap.fingerprint) == snap
