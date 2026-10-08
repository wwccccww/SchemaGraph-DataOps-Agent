"""Schema 激活门禁。"""

from __future__ import annotations

from app.schema_registry.gate import evaluate_activation_gate
from app.schema_registry.registry import SchemaRegistry
from app.schema_registry.snapshot import SchemaSnapshot
from tests.unit.test_schema_mutation import _table


def test_gate_rejects_empty_snapshot() -> None:
    snap = SchemaSnapshot.build(
        database_id="demo",
        schema_name="public",
        documents=(),
        edges=(),
    )
    result = evaluate_activation_gate(snap)
    assert result.passed is False
    assert any(item.name == "non_empty_catalog" and not item.passed for item in result.checks)


def test_registry_records_activation_audit() -> None:
    registry = SchemaRegistry()
    snap = SchemaSnapshot.build(
        database_id="demo",
        schema_name="public",
        documents=(_table("a"),),
        edges=(),
    )
    registry.register(snap, activate=True)
    registry.activate("demo", snap.fingerprint, forced=True)
    audit = registry.activation_audit("demo")
    assert len(audit) >= 1
    assert audit[-1].fingerprint == snap.fingerprint
