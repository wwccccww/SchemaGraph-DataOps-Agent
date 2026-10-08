"""Schema 同步与版本查询（阶段 4 最小接口）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config.settings import get_settings
from app.db.catalog_loader import get_schema_registry, load_catalog_for_runtime
from app.db.registry_sync import hydrate_schema_registry, persist_activation_audit, persist_schema_registry
from app.db.engine import get_admin_engine, get_sandbox_engine
from app.retrieval.embedder import BgeM3Embedder
from app.retrieval.index import ensure_embedding_tables
from app.schema_registry.extract import extract_snapshot
from app.schema_registry.gate import evaluate_activation_gate
from app.schema_registry.indexing import schema_version_from_fingerprint, sync_embeddings_for_snapshot
from app.schema_registry.tenant import (
    default_schema_database_id,
    ensure_tenant_database_id,
    tenant_database_ids,
)
from app.api.deps import TenantHeader

router = APIRouter(prefix="/v1/schema", tags=["schema"])


class GateCheckResponse(BaseModel):
    name: str
    passed: bool
    detail: str


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
    staging_fingerprint: str | None = None
    gate_passed: bool | None = None
    gate_checks: list[GateCheckResponse] = Field(default_factory=list)


class ActivationAuditResponse(BaseModel):
    database_id: str
    fingerprint: str
    activated_at: str
    forced: bool


class SchemaActivateRequest(BaseModel):
    fingerprint: str = Field(min_length=8)
    database_id: str | None = None


def _gate_checks_response(snapshot, embedding_rows, settings) -> tuple:
    gate = evaluate_activation_gate(
        snapshot,
        embedding_rows=embedding_rows,
        require_embeddings=settings.schema_registry_require_embeddings,
    )
    checks = [
        GateCheckResponse(name=item.name, passed=item.passed, detail=item.detail)
        for item in gate.checks
    ]
    return gate, checks


async def _embedding_row_count(snapshot) -> int | None:
    settings = get_settings()
    if not settings.schema_registry_require_embeddings:
        return None
    version = schema_version_from_fingerprint(snapshot.fingerprint)
    async with get_admin_engine().connect() as conn:
        count = await conn.scalar(
            text(
                """
                SELECT count(*) FROM schema_embedding
                WHERE database_id = :database_id
                  AND schema_name = :schema_name
                  AND schema_version = :schema_version
                """
            ),
            {
                "database_id": snapshot.database_id,
                "schema_name": snapshot.schema_name,
                "schema_version": version,
            },
        )
    return int(count) if count is not None else None


def _response_from_snapshot(
    snapshot,
    *,
    activated: bool,
    diff,
    indexed: int | None,
    staging_fingerprint: str | None,
    gate_passed: bool | None,
    gate_checks: list[GateCheckResponse],
) -> SchemaSyncResponse:
    return SchemaSyncResponse(
        database_id=snapshot.database_id,
        schema_name=snapshot.schema_name,
        fingerprint=snapshot.fingerprint,
        version_id=snapshot.version_id,
        table_count=len(snapshot.documents),
        edge_count=len(snapshot.edges),
        activated=activated,
        changed=diff is not None and not diff.is_empty,
        added_tables=list(diff.added_tables) if diff else [],
        removed_tables=list(diff.removed_tables) if diff else [],
        changed_tables=list(diff.changed_tables) if diff else [],
        indexed_tables=indexed,
        staging_fingerprint=staging_fingerprint,
        gate_passed=gate_passed,
        gate_checks=gate_checks,
    )


@router.post("/sync", response_model=SchemaSyncResponse)
async def sync_schema(
    *,
    index: bool = False,
    database_id: str | None = None,
    tenant_header: TenantHeader = None,
) -> SchemaSyncResponse:
    """提取 Catalog → staging → 可选索引 → 门禁 → 按配置激活。"""

    settings = get_settings()
    target = database_id or default_schema_database_id(settings)
    ensure_tenant_database_id(target, tenant_header=tenant_header, settings=settings)
    await hydrate_schema_registry()
    registry = get_schema_registry()
    async with get_sandbox_engine().connect() as conn:
        snapshot = await extract_snapshot(conn, settings, database_id=target)
    if snapshot.database_id != target:
        raise HTTPException(status_code=409, detail="extracted snapshot database_id mismatch")
    previous = registry.active_snapshot(snapshot.database_id)
    diff = registry.register(snapshot, activate=False)
    await persist_schema_registry(registry)
    indexed: int | None = None
    if index or settings.schema_registry_auto_index:
        embedder = BgeM3Embedder()
        async with get_admin_engine().begin() as conn:
            await ensure_embedding_tables(conn)
            indexed = await sync_embeddings_for_snapshot(conn, snapshot, embedder)
    embedding_rows = await _embedding_row_count(snapshot)
    if embedding_rows is None and indexed is not None:
        embedding_rows = indexed
    gate, gate_checks = _gate_checks_response(snapshot, embedding_rows, settings)
    staging_fp = registry.staging_fingerprint(snapshot.database_id)
    activated = False
    if gate.passed and (
        previous is None
        or settings.schema_registry_auto_activate
    ):
        registry.activate(snapshot.database_id, snapshot.fingerprint)
        await persist_activation_audit(registry.activation_audit()[-1])
        activated = True
        staging_fp = None
    await persist_schema_registry(registry)
    active = registry.active_snapshot(snapshot.database_id)
    reported = active if active is not None else snapshot
    return _response_from_snapshot(
        reported,
        activated=activated or (
            active is not None and active.fingerprint == snapshot.fingerprint
        ),
        diff=diff,
        indexed=indexed,
        staging_fingerprint=staging_fp,
        gate_passed=gate.passed,
        gate_checks=gate_checks,
    )


@router.post("/activate", response_model=SchemaSyncResponse)
async def activate_schema(
    body: SchemaActivateRequest,
    *,
    force: bool = False,
    tenant_header: TenantHeader = None,
) -> SchemaSyncResponse:
    settings = get_settings()
    database_id = body.database_id or default_schema_database_id(settings)
    ensure_tenant_database_id(database_id, tenant_header=tenant_header, settings=settings)
    await hydrate_schema_registry()
    registry = get_schema_registry()
    snapshot = registry.get(database_id, body.fingerprint)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="unknown schema fingerprint")
    if snapshot.database_id != database_id:
        raise HTTPException(status_code=403, detail="snapshot belongs to another tenant")
    embedding_rows: int | None = None
    if settings.schema_registry_require_embeddings:
        version = schema_version_from_fingerprint(snapshot.fingerprint)
        async with get_admin_engine().connect() as conn:
            embedding_rows = await conn.scalar(
                text(
                    """
                    SELECT count(*) FROM schema_embedding
                    WHERE database_id = :database_id
                      AND schema_name = :schema_name
                      AND schema_version = :schema_version
                    """
                ),
                {
                    "database_id": snapshot.database_id,
                    "schema_name": snapshot.schema_name,
                    "schema_version": version,
                },
            )
    if embedding_rows is None:
        embedding_rows = await _embedding_row_count(snapshot)
    gate, gate_checks = _gate_checks_response(
        snapshot,
        int(embedding_rows) if embedding_rows is not None else None,
        settings,
    )
    if force and not settings.schema_registry_allow_force:
        raise HTTPException(
            status_code=403,
            detail="forced schema activation is disabled (set SCHEMA_REGISTRY_ALLOW_FORCE=1)",
        )
    if not gate.passed and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "schema activation gate failed",
                "checks": [item.model_dump() for item in gate_checks],
            },
        )
    active = registry.activate(database_id, body.fingerprint, forced=force)
    await persist_activation_audit(registry.activation_audit()[-1])
    await persist_schema_registry(registry)
    return _response_from_snapshot(
        active,
        activated=True,
        diff=None,
        indexed=None,
        staging_fingerprint=None,
        gate_passed=gate.passed,
        gate_checks=gate_checks,
    )


@router.get("/active", response_model=SchemaSyncResponse)
async def active_schema(
    database_id: str | None = None,
    tenant_header: TenantHeader = None,
) -> SchemaSyncResponse:
    settings = get_settings()
    target = database_id or default_schema_database_id(settings)
    ensure_tenant_database_id(target, tenant_header=tenant_header, settings=settings)
    database_id = target
    registry = get_schema_registry()
    active = registry.active_snapshot(database_id)
    if active is None:
        async with get_sandbox_engine().connect() as conn:
            await load_catalog_for_runtime(conn, settings)
            active = registry.active_snapshot(database_id)
    if active is None:
        raise RuntimeError("no active schema snapshot")
    return _response_from_snapshot(
        active,
        activated=True,
        diff=None,
        indexed=None,
        staging_fingerprint=registry.staging_fingerprint(database_id),
        gate_passed=None,
        gate_checks=[],
    )


@router.get("/audit", response_model=list[ActivationAuditResponse])
async def schema_activation_audit(
    database_id: str | None = None,
    tenant_header: TenantHeader = None,
) -> list[ActivationAuditResponse]:
    settings = get_settings()
    allowed = tenant_database_ids(settings)
    if database_id is not None:
        ensure_tenant_database_id(database_id, tenant_header=tenant_header, settings=settings)
    registry = get_schema_registry()
    rows = registry.activation_audit(database_id)
    if database_id is None:
        rows = tuple(item for item in rows if item.database_id in allowed)
    return [
        ActivationAuditResponse(
            database_id=item.database_id,
            fingerprint=item.fingerprint,
            activated_at=item.activated_at.isoformat(),
            forced=item.forced,
        )
        for item in rows
    ]
