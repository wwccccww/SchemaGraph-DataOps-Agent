"""Registry 按 database_id 隔离。"""

from __future__ import annotations

from app.schema_registry.registry import SchemaRegistry
from app.schema_registry.snapshot import SchemaSnapshot
from tests.unit.test_schema_mutation import _table


def test_registry_isolates_active_versions_per_database() -> None:
    registry = SchemaRegistry()
    a = SchemaSnapshot.build(
        database_id="db_a",
        schema_name="public",
        documents=(_table("only_a"),),
        edges=(),
    )
    b = SchemaSnapshot.build(
        database_id="db_b",
        schema_name="public",
        documents=(_table("only_b"),),
        edges=(),
    )
    registry.register(a, activate=True)
    registry.register(b, activate=True)
    active_a = registry.active_snapshot("db_a")
    active_b = registry.active_snapshot("db_b")
    assert active_a is not None and active_b is not None
    assert active_a.fingerprint != active_b.fingerprint
    assert active_a.documents[0].table_name == "only_a"
    assert active_b.documents[0].table_name == "only_b"
