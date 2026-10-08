"""从 PostgreSQL 与 Schema 快照构建 OptimizerContext。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.agents.slow_sql.rule_catalog import (
    DEFAULT_RULE_CATALOG,
    RuleCatalog,
    TableStat,
    build_rule_catalog,
)
from app.schema_registry.snapshot import SchemaSnapshot


@dataclass(frozen=True)
class OptimizerContext:
    database_id: str
    schema_name: str
    catalog: RuleCatalog
    table_columns: dict[str, tuple[str, ...]]
    schema_fingerprint: str | None


async def load_table_stats(
    conn: AsyncConnection,
    *,
    schema_name: str = "public",
) -> dict[str, TableStat]:
    rows = (
        await conn.execute(
            text(
                """
                SELECT
                    cls.relname AS table_name,
                    GREATEST(cls.reltuples, 0) AS est_rows,
                    pg_total_relation_size(cls.oid) AS total_bytes
                FROM pg_class AS cls
                JOIN pg_namespace AS ns ON ns.oid = cls.relnamespace
                WHERE ns.nspname = :schema_name
                  AND cls.relkind = 'r'
                """
            ),
            {"schema_name": schema_name},
        )
    ).all()
    return {
        str(row.table_name): TableStat(
            est_rows=float(row.est_rows or 0),
            total_bytes=int(row.total_bytes or 0),
        )
        for row in rows
    }


async def load_indexed_columns(
    conn: AsyncConnection,
    *,
    schema_name: str = "public",
) -> frozenset[tuple[str, str]]:
    rows = (
        await conn.execute(
            text(
                """
                SELECT DISTINCT
                    tbl.relname AS table_name,
                    attr.attname AS column_name
                FROM pg_index AS idx
                JOIN pg_class AS tbl ON tbl.oid = idx.indrelid
                JOIN pg_namespace AS ns ON ns.oid = tbl.relnamespace
                JOIN LATERAL unnest(idx.indkey) AS key(attnum) ON TRUE
                JOIN pg_attribute AS attr
                  ON attr.attrelid = tbl.oid
                 AND attr.attnum = key.attnum
                WHERE ns.nspname = :schema_name
                  AND idx.indisvalid
                  AND idx.indisready
                  AND attr.attnum > 0
                """
            ),
            {"schema_name": schema_name},
        )
    ).all()
    return frozenset((str(row.table_name), str(row.column_name)) for row in rows)


async def load_optimizer_context(
    conn: AsyncConnection,
    snapshot: SchemaSnapshot | None,
) -> OptimizerContext:
    if snapshot is None:
        return OptimizerContext(
            database_id="ecommerce",
            schema_name="public",
            catalog=DEFAULT_RULE_CATALOG,
            table_columns={},
            schema_fingerprint=None,
        )
    stats = await load_table_stats(conn, schema_name=snapshot.schema_name)
    indexed = await load_indexed_columns(conn, schema_name=snapshot.schema_name)
    catalog = build_rule_catalog(snapshot.documents, stats, indexed)
    columns = {
        document.table_name: tuple(column.name for column in document.columns)
        for document in snapshot.documents
    }
    return OptimizerContext(
        database_id=snapshot.database_id,
        schema_name=snapshot.schema_name,
        catalog=catalog,
        table_columns=columns,
        schema_fingerprint=snapshot.fingerprint,
    )


def table_columns_from_documents(documents: Sequence) -> dict[str, tuple[str, ...]]:
    return {
        document.table_name: tuple(column.name for column in document.columns)
        for document in documents
    }
