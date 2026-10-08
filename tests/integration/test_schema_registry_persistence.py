"""Registry 持久化 round-trip。"""

from __future__ import annotations

import pytest

from app.config.settings import get_settings
from app.db.catalog_loader import get_schema_registry, load_catalog_for_runtime, reset_schema_registry
from app.db.engine import get_sandbox_engine
from app.db.seed import seed_ecommerce

pytestmark = pytest.mark.integration


async def test_registry_persistence_hydrates_active_fingerprint(
    database_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del database_settings
    monkeypatch.setenv("SCHEMA_REGISTRY_PERSIST", "1")
    get_settings.cache_clear()
    reset_schema_registry()
    await seed_ecommerce()

    async with get_sandbox_engine().connect() as conn:
        await load_catalog_for_runtime(conn)
    fingerprint = get_schema_registry().active_snapshot("ecommerce")
    assert fingerprint is not None
    expected = fingerprint.fingerprint

    reset_schema_registry()
    get_settings.cache_clear()
    monkeypatch.setenv("SCHEMA_REGISTRY_PERSIST", "1")
    get_settings.cache_clear()

    async with get_sandbox_engine().connect() as conn:
        await load_catalog_for_runtime(conn)
    restored = get_schema_registry().active_snapshot("ecommerce")
    assert restored is not None
    assert restored.fingerprint == expected
