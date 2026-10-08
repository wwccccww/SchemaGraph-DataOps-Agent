"""Schema 同步与版本查询（阶段 4 最小接口）。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config.settings import get_settings
from app.db.catalog_loader import get_schema_registry, load_catalog_for_runtime
from app.db.engine import get_sandbox_engine
from app.schema_registry.diff import diff_snapshots
router = APIRouter(prefix="/v1/schema", tags=["schema"])


class SchemaSyncResponse(BaseModel):
    database_id: str
    schema_name: str
    fingerprint: str
    version_id: str
    table_count: int
    edge_count: int
    activated: bool
    changed: bool = False
    added_tables: list[str] = Field(default_factory=list)
    removed_tables: list[str] = Field(default_factory=list)
    changed_tables: list[str] = Field(default_factory=list)


@router.post("/sync", response_model=SchemaSyncResponse)
async def sync_schema() -> SchemaSyncResponse:
    """从数据库提取 Catalog，登记 Registry，并按配置激活。"""

    settings = get_settings()
    registry = get_schema_registry()
    previous = registry.active_snapshot(settings.postgres_db if settings.text_to_sql_catalog_mode == "live_public" else "ecommerce")
    async with get_sandbox_engine().connect() as conn:
        documents, _, fingerprint = await load_catalog_for_runtime(conn, settings)
    database_id = documents[0].database_id if documents else "ecommerce"
    active = registry.active_snapshot(database_id)
    if active is None:
        raise RuntimeError("schema sync did not produce an active snapshot")
    diff = None
    if previous is not None and previous.fingerprint != fingerprint:
        diff = diff_snapshots(previous, active)
    return SchemaSyncResponse(
        database_id=active.database_id,
        schema_name=active.schema_name,
        fingerprint=active.fingerprint,
        version_id=active.version_id,
        table_count=len(active.documents),
        edge_count=len(active.edges),
        activated=registry.active_snapshot(active.database_id) is not None,
        changed=diff is not None and not diff.is_empty,
        added_tables=list(diff.added_tables) if diff else [],
        removed_tables=list(diff.removed_tables) if diff else [],
        changed_tables=list(diff.changed_tables) if diff else [],
    )


@router.get("/active", response_model=SchemaSyncResponse)
async def active_schema() -> SchemaSyncResponse:
    settings = get_settings()
    database_id = settings.postgres_db if settings.text_to_sql_catalog_mode == "live_public" else "ecommerce"
    registry = get_schema_registry()
    active = registry.active_snapshot(database_id)
    if active is None:
        async with get_sandbox_engine().connect() as conn:
            await load_catalog_for_runtime(conn, settings)
            active = registry.active_snapshot(database_id)
    if active is None:
        raise RuntimeError("no active schema snapshot")
    return SchemaSyncResponse(
        database_id=active.database_id,
        schema_name=active.schema_name,
        fingerprint=active.fingerprint,
        version_id=active.version_id,
        table_count=len(active.documents),
        edge_count=len(active.edges),
        activated=True,
    )
