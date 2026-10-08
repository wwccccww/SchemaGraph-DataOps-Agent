"""从 PostgreSQL 提取 SchemaSnapshot。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncConnection

from app.config.settings import Settings
from app.db.catalog import DATABASE_ID, SCHEMA_NAME, load_foreign_keys, load_table_documents
from app.datasources.postgres_catalog import EXCLUDED_TABLES, load_public_catalog
from app.schema_registry.snapshot import SchemaSnapshot

# 向量索引与工具表不参与问数 Schema Graph。
SYSTEM_TABLES = frozenset({"schema_embedding", "tool_embedding"})


async def extract_fixed_ecommerce_snapshot(conn: AsyncConnection) -> SchemaSnapshot:
    documents = tuple(await load_table_documents(conn))
    edges = tuple(await load_foreign_keys(conn))
    return SchemaSnapshot.build(
        database_id=DATABASE_ID,
        schema_name=SCHEMA_NAME,
        documents=documents,
        edges=edges,
    )


async def extract_live_public_snapshot(
    conn: AsyncConnection,
    database_id: str,
    *,
    schema_name: str = "public",
) -> SchemaSnapshot:
    excluded = EXCLUDED_TABLES | SYSTEM_TABLES
    documents, edges = await load_public_catalog(
        conn,
        database_id,
        schema_name=schema_name,
        excluded_tables=excluded,
    )
    return SchemaSnapshot.build(
        database_id=database_id,
        schema_name=schema_name,
        documents=tuple(documents),
        edges=tuple(edges),
    )


async def extract_snapshot(
    conn: AsyncConnection,
    settings: Settings,
    *,
    database_id: str | None = None,
) -> SchemaSnapshot:
    """按配置选择 fixed 12 表或 live public catalog。"""

    mode = settings.text_to_sql_catalog_mode
    if mode == "fixed_ecommerce":
        return await extract_fixed_ecommerce_snapshot(conn)
    target = database_id or settings.postgres_db
    return await extract_live_public_snapshot(conn, target)
