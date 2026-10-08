"""Schema Registry 持久化钩子。"""

from __future__ import annotations

from app.config.settings import get_settings
from app.db.engine import get_admin_engine
from app.schema_registry.persistence import (
    append_activation_audit,
    ensure_registry_tables,
    load_registry,
    persist_registry_state,
)
from app.schema_registry.registry import ActivationAudit, SchemaRegistry

_hydrated = False


async def hydrate_schema_registry() -> None:
    global _hydrated
    if _hydrated:
        return
    settings = get_settings()
    if not settings.schema_registry_persist:
        _hydrated = True
        return
    async with get_admin_engine().begin() as conn:
        loaded = await load_registry(conn)
    from app.db import catalog_loader

    catalog_loader._global_registry = loaded
    _hydrated = True


async def persist_schema_registry(registry: SchemaRegistry) -> None:
    settings = get_settings()
    if not settings.schema_registry_persist:
        return
    async with get_admin_engine().begin() as conn:
        await ensure_registry_tables(conn)
        await persist_registry_state(conn, registry)


async def persist_activation_audit(audit: ActivationAudit) -> None:
    settings = get_settings()
    if not settings.schema_registry_persist:
        return
    async with get_admin_engine().begin() as conn:
        await ensure_registry_tables(conn)
        await append_activation_audit(conn, audit)
