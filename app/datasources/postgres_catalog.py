"""读取通用 PostgreSQL public 目录。电商 12 张表仍走原来的 Catalog。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.datasources.infer import infer_reference_edges
from app.db.catalog import is_junction_comment, table_content_hash
from app.schemas.catalog import ColumnDocument, SchemaEdge, TableDocument

EXCLUDED_TABLES = frozenset({"dbgen_version"})


@dataclass(frozen=True)
class ColumnCatalogRow:
    """一张表的一列。"""

    table_name: str
    table_comment: str | None
    column_name: str
    data_type: str
    nullable: bool
    column_comment: str | None


@dataclass(frozen=True)
class ForeignKeyCatalogRow:
    """一条显式外键。"""

    source_table: str
    target_table: str
    constraint_name: str
    source_columns: tuple[str, ...]
    target_columns: tuple[str, ...]


def assemble_documents(
    rows: Sequence[ColumnCatalogRow],
    *,
    database_id: str,
    schema_name: str,
    excluded_tables: frozenset[str] = EXCLUDED_TABLES,
) -> list[TableDocument]:
    """按表名组装文档。被排除的表和 Junction 标记都在这里决定。"""

    grouped: dict[str, tuple[str | None, list[ColumnDocument]]] = {}
    for row in rows:
        if row.table_name in excluded_tables:
            continue
        comment, columns = grouped.setdefault(row.table_name, (row.table_comment, []))
        if comment != row.table_comment:
            raise RuntimeError(f"inconsistent comment for {row.table_name}")
        columns.append(
            ColumnDocument(
                name=row.column_name,
                data_type=row.data_type,
                nullable=row.nullable,
                comment=row.column_comment,
            )
        )
    documents: list[TableDocument] = []
    for name in sorted(grouped):
        table_comment, columns = grouped[name]
        documents.append(
            TableDocument(
                database_id=database_id,
                schema_name=schema_name,
                table_name=name,
                table_comment=table_comment,
                columns=columns,
                is_junction=is_junction_comment(table_comment),
                content_hash=table_content_hash(name, table_comment, columns),
            )
        )
    return documents


def assemble_foreign_keys(
    rows: Sequence[ForeignKeyCatalogRow],
    tables: set[str],
) -> list[SchemaEdge]:
    """只保留两端都在当前目录里的外键。"""

    edges: list[SchemaEdge] = []
    for row in rows:
        if row.source_table not in tables or row.target_table not in tables:
            continue
        if not row.source_columns or not row.target_columns:
            raise RuntimeError(f"foreign key {row.constraint_name} has no columns")
        edges.append(
            SchemaEdge(
                source_table=row.source_table,
                source_columns=list(row.source_columns),
                target_table=row.target_table,
                target_columns=list(row.target_columns),
                constraint_name=row.constraint_name,
                weight=1.0,
                inferred=False,
                confidence=1.0,
            )
        )
    return edges


async def load_public_catalog(
    conn: AsyncConnection,
    database_id: str,
    *,
    schema_name: str = "public",
    excluded_tables: frozenset[str] = EXCLUDED_TABLES,
) -> tuple[list[TableDocument], list[SchemaEdge]]:
    """读取 public 里的普通表。调用方要连到目标库，而不是电商库。"""

    column_rows = (
        await conn.execute(
            text(
                """
                SELECT
                    cls.relname AS table_name,
                    obj_description(cls.oid, 'pg_class') AS table_comment,
                    attr.attname AS column_name,
                    format_type(attr.atttypid, attr.atttypmod) AS data_type,
                    NOT attr.attnotnull AS nullable,
                    col_description(cls.oid, attr.attnum) AS column_comment
                FROM pg_class AS cls
                JOIN pg_namespace AS namespace
                  ON namespace.oid = cls.relnamespace
                JOIN pg_attribute AS attr
                  ON attr.attrelid = cls.oid
                WHERE namespace.nspname = :schema_name
                  AND cls.relkind = 'r'
                  AND cls.relname NOT IN :excluded_tables
                  AND attr.attnum > 0
                  AND NOT attr.attisdropped
                ORDER BY cls.relname, attr.attnum
                """
            ).bindparams(bindparam("excluded_tables", expanding=True)),
            {
                "schema_name": schema_name,
                "excluded_tables": sorted(excluded_tables) or ["__none__"],
            },
        )
    ).all()
    documents = assemble_documents(
        [
            ColumnCatalogRow(
                table_name=str(row.table_name),
                table_comment=None if row.table_comment is None else str(row.table_comment),
                column_name=str(row.column_name),
                data_type=str(row.data_type),
                nullable=bool(row.nullable),
                column_comment=None if row.column_comment is None else str(row.column_comment),
            )
            for row in column_rows
        ],
        database_id=database_id,
        schema_name=schema_name,
        excluded_tables=excluded_tables,
    )
    present = {document.table_name for document in documents}
    key_rows = (
        await conn.execute(
            text(
                """
                SELECT
                    src.relname AS source_table,
                    tgt.relname AS target_table,
                    con.conname AS constraint_name,
                    (
                        SELECT array_agg(attr.attname ORDER BY key.ordinality)
                        FROM unnest(con.conkey) WITH ORDINALITY AS key(attnum, ordinality)
                        JOIN pg_attribute AS attr
                          ON attr.attrelid = con.conrelid
                         AND attr.attnum = key.attnum
                    ) AS source_columns,
                    (
                        SELECT array_agg(attr.attname ORDER BY key.ordinality)
                        FROM unnest(con.confkey) WITH ORDINALITY AS key(attnum, ordinality)
                        JOIN pg_attribute AS attr
                          ON attr.attrelid = con.confrelid
                         AND attr.attnum = key.attnum
                    ) AS target_columns
                FROM pg_constraint AS con
                JOIN pg_class AS src ON src.oid = con.conrelid
                JOIN pg_class AS tgt ON tgt.oid = con.confrelid
                JOIN pg_namespace AS namespace ON namespace.oid = src.relnamespace
                WHERE con.contype = 'f'
                  AND namespace.nspname = :schema_name
                ORDER BY con.conname
                """
            ),
            {"schema_name": schema_name},
        )
    ).all()
    edges = assemble_foreign_keys(
        [
            ForeignKeyCatalogRow(
                source_table=str(row.source_table),
                target_table=str(row.target_table),
                constraint_name=str(row.constraint_name),
                source_columns=tuple(str(column) for column in row.source_columns or ()),
                target_columns=tuple(str(column) for column in row.target_columns or ()),
            )
            for row in key_rows
        ],
        present,
    )
    edges.extend(
        infer_reference_edges(
            documents,
            single_keys=await _single_keys(conn, schema_name, present),
            existing=edges,
        )
    )
    return documents, edges


async def _single_keys(
    conn: AsyncConnection,
    schema_name: str,
    tables: set[str],
) -> dict[str, set[str]]:
    rows = (
        await conn.execute(
            text(
                """
                SELECT
                    src.relname AS table_name,
                    (
                        SELECT array_agg(attr.attname ORDER BY key.ordinality)
                        FROM unnest(con.conkey) WITH ORDINALITY AS key(attnum, ordinality)
                        JOIN pg_attribute AS attr
                          ON attr.attrelid = con.conrelid
                         AND attr.attnum = key.attnum
                    ) AS columns
                FROM pg_constraint AS con
                JOIN pg_class AS src ON src.oid = con.conrelid
                JOIN pg_namespace AS namespace ON namespace.oid = src.relnamespace
                WHERE con.contype IN ('p', 'u')
                  AND namespace.nspname = :schema_name
                """
            ),
            {"schema_name": schema_name},
        )
    ).all()
    keys: dict[str, set[str]] = {table: set() for table in tables}
    for row in rows:
        table_name = str(row.table_name)
        columns = tuple(str(column) for column in row.columns or ())
        if table_name in keys and len(columns) == 1:
            keys[table_name].add(columns[0])
    return keys
