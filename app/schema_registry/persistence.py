"""Schema Registry 可选持久化（admin 库）。"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.schema_registry.registry import ActivationAudit, SchemaRegistry
from app.schema_registry.snapshot import SchemaSnapshot
from app.schemas.catalog import SchemaEdge, TableDocument

_DDL = """
CREATE TABLE IF NOT EXISTS schema_registry_snapshot (
    database_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    PRIMARY KEY (database_id, fingerprint)
);
CREATE TABLE IF NOT EXISTS schema_registry_state (
    database_id TEXT PRIMARY KEY,
    active_fingerprint TEXT,
    staging_fingerprint TEXT
);
CREATE TABLE IF NOT EXISTS schema_registry_activation_audit (
    id BIGSERIAL PRIMARY KEY,
    database_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    activated_at TIMESTAMPTZ NOT NULL,
    forced BOOLEAN NOT NULL DEFAULT FALSE
);
"""


async def ensure_registry_tables(conn: AsyncConnection) -> None:
    for statement in _DDL.strip().split(";"):
        chunk = statement.strip()
        if chunk:
            await conn.execute(text(chunk))


def _snapshot_payload(snapshot: SchemaSnapshot) -> str:
    body = {
        "documents": [document.model_dump() for document in snapshot.documents],
        "edges": [edge.model_dump() for edge in snapshot.edges],
        "captured_at": snapshot.captured_at.isoformat(),
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"))


def _snapshot_from_row(
    database_id: str,
    fingerprint: str,
    schema_name: str,
    payload: dict,
) -> SchemaSnapshot:
    documents = tuple(TableDocument.model_validate(item) for item in payload["documents"])
    edges = tuple(SchemaEdge.model_validate(item) for item in payload["edges"])
    captured = datetime.fromisoformat(payload["captured_at"])
    return SchemaSnapshot(
        database_id=database_id,
        schema_name=schema_name,
        fingerprint=fingerprint,
        documents=documents,
        edges=edges,
        captured_at=captured,
    )


async def persist_snapshot(conn: AsyncConnection, snapshot: SchemaSnapshot) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO schema_registry_snapshot (
                database_id, fingerprint, schema_name, captured_at, payload
            ) VALUES (
                :database_id, :fingerprint, :schema_name, :captured_at, CAST(:payload AS jsonb)
            )
            ON CONFLICT (database_id, fingerprint) DO UPDATE SET
                schema_name = EXCLUDED.schema_name,
                captured_at = EXCLUDED.captured_at,
                payload = EXCLUDED.payload
            """
        ),
        {
            "database_id": snapshot.database_id,
            "fingerprint": snapshot.fingerprint,
            "schema_name": snapshot.schema_name,
            "captured_at": snapshot.captured_at,
            "payload": _snapshot_payload(snapshot),
        },
    )


async def persist_registry_state(conn: AsyncConnection, registry: SchemaRegistry) -> None:
    for database_id in registry.database_ids():
        bucket = registry._versions.get(database_id, {})
        for snapshot in bucket.values():
            await persist_snapshot(conn, snapshot)
        active = registry._active.get(database_id)
        staging = registry._staging.get(database_id)
        await conn.execute(
            text(
                """
                INSERT INTO schema_registry_state (
                    database_id, active_fingerprint, staging_fingerprint
                ) VALUES (
                    :database_id, :active, :staging
                )
                ON CONFLICT (database_id) DO UPDATE SET
                    active_fingerprint = EXCLUDED.active_fingerprint,
                    staging_fingerprint = EXCLUDED.staging_fingerprint
                """
            ),
            {"database_id": database_id, "active": active, "staging": staging},
        )


async def append_activation_audit(conn: AsyncConnection, audit: ActivationAudit) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO schema_registry_activation_audit (
                database_id, fingerprint, activated_at, forced
            ) VALUES (
                :database_id, :fingerprint, :activated_at, :forced
            )
            """
        ),
        {
            "database_id": audit.database_id,
            "fingerprint": audit.fingerprint,
            "activated_at": audit.activated_at,
            "forced": audit.forced,
        },
    )


async def load_registry(conn: AsyncConnection) -> SchemaRegistry:
    await ensure_registry_tables(conn)
    registry = SchemaRegistry()
    rows = (
        await conn.execute(
            text(
                """
                SELECT database_id, fingerprint, schema_name, payload
                FROM schema_registry_snapshot
                """
            )
        )
    ).all()
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else json.loads(row.payload)
        snapshot = _snapshot_from_row(
            str(row.database_id),
            str(row.fingerprint),
            str(row.schema_name),
            payload,
        )
        registry._versions.setdefault(snapshot.database_id, {})[snapshot.fingerprint] = snapshot
    state_rows = (await conn.execute(text("SELECT * FROM schema_registry_state"))).all()
    for row in state_rows:
        database_id = str(row.database_id)
        if row.active_fingerprint:
            registry._active[database_id] = str(row.active_fingerprint)
        if row.staging_fingerprint:
            registry._staging[database_id] = str(row.staging_fingerprint)
    audit_rows = (
        await conn.execute(
            text(
                """
                SELECT database_id, fingerprint, activated_at, forced
                FROM schema_registry_activation_audit
                ORDER BY id
                """
            )
        )
    ).all()
    for row in audit_rows:
        registry._audit.append(
            ActivationAudit(
                database_id=str(row.database_id),
                fingerprint=str(row.fingerprint),
                activated_at=row.activated_at,
                forced=bool(row.forced),
            )
        )
    return registry
