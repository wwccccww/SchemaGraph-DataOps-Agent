"""从 PostgreSQL Catalog 提取表文档和显式外键。"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.tables import TABLE_NAMES
from app.schemas.catalog import ColumnDocument, SchemaEdge, TableDocument

DATABASE_ID = "ecommerce"
SCHEMA_NAME = "public"
JUNCTION_MARKER = "[Junction Table]"


def is_junction_comment(comment: str | None) -> bool:
    """Junction Table 只通过表注释中的标记识别。"""

    return comment is not None and JUNCTION_MARKER in comment


def table_content_hash(
    table_name: str,
    table_comment: str | None,
    columns: list[ColumnDocument],
) -> str:
    """生成与向量版本无关的表文档摘要。"""

    payload = {
        "columns": [
            {
                "comment": column.comment,
                "data_type": column.data_type,
                "name": column.name,
                "nullable": column.nullable,
            }
            for column in columns
        ],
        "table_comment": table_comment,
        "table_name": table_name,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


async def load_table_documents(conn: AsyncConnection) -> list[TableDocument]:
    """读取 12 张表的注释和列。缺少任何一张表时失败。"""

    rows = (
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
                  AND cls.relname IN :table_names
                  AND attr.attnum > 0
                  AND NOT attr.attisdropped
                ORDER BY cls.relname, attr.attnum
                """
            ).bindparams(bindparam("table_names", expanding=True)),
            {"schema_name": SCHEMA_NAME, "table_names": list(TABLE_NAMES)},
        )
    ).all()

    grouped: dict[str, tuple[str | None, list[ColumnDocument]]] = {}
    for row in rows:
        comment, columns = grouped.setdefault(str(row.table_name), (row.table_comment, []))
        if comment != row.table_comment:
            raise RuntimeError(f"inconsistent comment for {row.table_name}")
        columns.append(
            ColumnDocument(
                name=str(row.column_name),
                data_type=str(row.data_type),
                nullable=bool(row.nullable),
                comment=None if row.column_comment is None else str(row.column_comment),
            )
        )
    missing = [name for name in TABLE_NAMES if name not in grouped]
    if missing:
        raise RuntimeError(f"ecommerce tables are missing: {', '.join(missing)}")

    documents: list[TableDocument] = []
    for name in TABLE_NAMES:
        table_comment, columns = grouped[name]
        comment = None if table_comment is None else str(table_comment)
        documents.append(
            TableDocument(
                database_id=DATABASE_ID,
                schema_name=SCHEMA_NAME,
                table_name=name,
                table_comment=comment,
                columns=columns,
                is_junction=is_junction_comment(comment),
                content_hash=table_content_hash(name, comment, columns),
                embedding_model=None,
                embedding_version=None,
            )
        )
    return documents


async def load_foreign_keys(conn: AsyncConnection) -> list[SchemaEdge]:
    """读取显式外键。隐式推断不在本阶段生成边。"""

    rows = (
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
                  AND src.relname IN :table_names
                ORDER BY con.conname
                """
            ).bindparams(bindparam("table_names", expanding=True)),
            {"schema_name": SCHEMA_NAME, "table_names": list(TABLE_NAMES)},
        )
    ).all()
    edges: list[SchemaEdge] = []
    for row in rows:
        source_columns = [str(column) for column in row.source_columns]
        target_columns = [str(column) for column in row.target_columns]
        if not source_columns or not target_columns:
            raise RuntimeError(f"foreign key {row.constraint_name} has no columns")
        edges.append(
            SchemaEdge(
                source_table=str(row.source_table),
                source_columns=source_columns,
                target_table=str(row.target_table),
                target_columns=target_columns,
                constraint_name=str(row.constraint_name),
                weight=1.0,
                inferred=False,
                confidence=1.0,
            )
        )
    return edges
