"""问数运行时统一的 Catalog 加载入口。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncConnection

from app.config.settings import Settings, get_settings
from app.schema_registry.extract import extract_snapshot
from app.schema_registry.registry import SchemaRegistry
from app.schemas.catalog import SchemaEdge, TableDocument

_global_registry = SchemaRegistry()


def get_schema_registry() -> SchemaRegistry:
    return _global_registry


def reset_schema_registry() -> None:
    global _global_registry
    _global_registry = SchemaRegistry()
    from app.db import registry_sync

    registry_sync._hydrated = False


async def load_catalog_for_runtime(
    conn: AsyncConnection,
    settings: Settings | None = None,
) -> tuple[tuple[TableDocument, ...], tuple[SchemaEdge, ...], str]:
    """返回 documents、edges 与 active schema fingerprint。"""

    from app.db.registry_sync import hydrate_schema_registry, persist_schema_registry

    resolved = settings or get_settings()
    await hydrate_schema_registry()
    snapshot = await extract_snapshot(conn, resolved)
    registry = get_schema_registry()
    active = registry.active_snapshot(snapshot.database_id)
    if active is not None and active.fingerprint == snapshot.fingerprint:
        return active.documents, active.edges, active.fingerprint
    registry.register(snapshot, activate=False)
    await persist_schema_registry(registry)
    if active is None or resolved.schema_registry_auto_activate:
        audit_before = len(registry.activation_audit())
        registry.activate(snapshot.database_id, snapshot.fingerprint)
        if len(registry.activation_audit()) > audit_before:
            from app.db.registry_sync import persist_activation_audit

            await persist_activation_audit(registry.activation_audit()[-1])
    await persist_schema_registry(registry)
    active = registry.active_snapshot(snapshot.database_id)
    if active is None:
        raise RuntimeError("schema registry has no active snapshot")
    return active.documents, active.edges, active.fingerprint
