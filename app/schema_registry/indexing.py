"""按 Schema 版本同步向量索引。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncConnection

from app.retrieval.embedder import Embedder
from app.retrieval.index import upsert_schema_embeddings
from app.schema_registry.snapshot import SchemaSnapshot


def schema_version_from_fingerprint(fingerprint: str) -> str:
    return fingerprint.removeprefix("sha256:")


async def sync_embeddings_for_snapshot(
    conn: AsyncConnection,
    snapshot: SchemaSnapshot,
    embedder: Embedder,
) -> int:
    """为 snapshot 写入或刷新该 schema_version 下的全部表向量。"""

    version = schema_version_from_fingerprint(snapshot.fingerprint)
    await upsert_schema_embeddings(
        conn,
        snapshot.documents,
        embedder,
        schema_version=version,
    )
    return len(snapshot.documents)
