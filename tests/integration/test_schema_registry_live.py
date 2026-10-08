"""Registry 与 OptimizerContext 在真实 Catalog 上的行为。"""

from __future__ import annotations

import pytest

from app.agents.slow_sql.optimizer_context import load_optimizer_context
from app.db.catalog_loader import get_schema_registry, reset_schema_registry
from app.db.ecommerce_schema import apply_ecommerce_schema
from app.db.engine import get_admin_engine
from app.schema_registry.extract import extract_fixed_ecommerce_snapshot
from app.schema_registry.gate import evaluate_activation_gate

pytestmark = pytest.mark.integration


async def test_extract_and_gate_passes_for_ecommerce_catalog(database_settings) -> None:
    del database_settings
    reset_schema_registry()
    registry = get_schema_registry()
    async with get_admin_engine().begin() as conn:
        await apply_ecommerce_schema(conn)
        snapshot = await extract_fixed_ecommerce_snapshot(conn)
        context = await load_optimizer_context(conn, snapshot)
    registry.register(snapshot, activate=False)
    gate = evaluate_activation_gate(snapshot)
    assert gate.passed is True
    assert len(snapshot.documents) >= 12
    assert "t_order" in context.catalog.large_tables
    assert context.table_columns["t_order"]
