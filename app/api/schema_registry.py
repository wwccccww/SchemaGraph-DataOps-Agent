"""Schema 同步与版本查询（阶段 4 最小接口）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config.settings import get_settings
from app.db.catalog_loader import get_schema_registry, load_catalog_for_runtime
from app.db.engine import get_admin_engine, get_sandbox_engine
from app.retrieval.embedder import BgeM3Embedder
from app.retrieval.index import ensure_embedding_tables
from app.schema_registry.diff import diff_snapshots
from app.schema_registry.indexing import sync_embeddings_for_snapshot

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
    indexed_tables: int | None = None


class SchemaActivateRequest(BaseModel):
    fingerprint: str = Field(min_length=8)


@router.post("/sync", response_model=SchemaSyncResponse)
async def sync_schema(*, index: bool = False) -> SchemaSyncResponse:
    """从数据库提取 Catalog，登记 Registry，并按配置激活。`index=true` 时重建该版本的向量。"""

    settings = get_settings()
    registry = get_schema_registry()
    database_id = (
        settings.postgres_db if settings.text_to_sql_catalog_mode == "live_public" else "ecommerce"
    )
    previous = registry.active_snapshot(database_id)
    async with get_sandbox_engine().connect() as conn:
        documents, _, _ = await load_catalog_for_runtime(conn, settings)
    if documents:
        database_id = documents[0].database_id
    active = registry.active_snapshot(database_id)
    if active is None:
        raise RuntimeError("schema sync did not produce an active snapshot")
    diff = None
    if previous is not None and previous.fingerprint != active.fingerprint:
        diff = diff_snapshots(previous, active)
    indexed: int | None = None
    if index or settings.schema_registry_auto_index:
        embedder = BgeM3Embedder()
        async with get_admin_engine().begin() as conn:
            await ensure_embedding_tables(conn)
            indexed = await sync_embeddings_for_snapshot(conn, active, embedder)
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
        indexed_tables=indexed,
    )


@router.post("/activate", response_model=SchemaSyncResponse)
async def activate_schema(body: SchemaActivateRequest) -> SchemaSyncResponse:
    settings = get_settings()
    database_id = (
        settings.postgres_db if settings.text_to_sql_catalog_mode == "live_public" else "ecommerce"
    )
    registry = get_schema_registry()
    try:
        active = registry.activate(database_id, body.fingerprint)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown schema fingerprint") from exc
    return SchemaSyncResponse(
        database_id=active.database_id,
        schema_name=active.schema_name,
        fingerprint=active.fingerprint,
        version_id=active.version_id,
        table_count=len(active.documents),
        edge_count=len(active.edges),
        activated=True,
    )


@router.get("/active", response_model=SchemaSyncResponse)
async def active_schema() -> SchemaSyncResponse:
    settings = get_settings()
    database_id = (
        settings.postgres_db if settings.text_to_sql_catalog_mode == "live_public" else "ecommerce"
    )
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
