"""从只读 SQLite 文件提取表、列和外键。不执行问数 SQL。"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from urllib.parse import quote

from app.db.catalog import is_junction_comment, table_content_hash
from app.schemas.catalog import ColumnDocument, SchemaEdge, TableDocument

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def load_sqlite_catalog(
    database: Path,
    database_id: str,
) -> tuple[list[TableDocument], list[SchemaEdge]]:
    """读取 main 中的普通表。sqlite_ 前缀的内部表不进入目录。"""

    if not database.is_file():
        raise FileNotFoundError("sqlite database is missing")
    uri = "file:" + quote(str(database.resolve())) + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.row_factory = sqlite3.Row
        names = [
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        ]
        documents = [_table_document(connection, database_id, name) for name in names]
        present = {document.table_name for document in documents}
        edges: list[SchemaEdge] = []
        for name in names:
            edges.extend(_foreign_keys(connection, name, present))
        return documents, edges
    finally:
        connection.close()


def _table_document(
    connection: sqlite3.Connection,
    database_id: str,
    table_name: str,
) -> TableDocument:
    columns: list[ColumnDocument] = []
    for info in connection.execute(f"PRAGMA table_info({_quote(table_name)})"):
        data_type = str(info["type"] or "TEXT")
        columns.append(
            ColumnDocument(
                name=str(info["name"]),
                data_type=data_type,
                nullable=not bool(info["notnull"]),
                comment=None,
            )
        )
    comment = None
    return TableDocument(
        database_id=database_id,
        schema_name="main",
        table_name=table_name,
        table_comment=comment,
        columns=columns,
        is_junction=is_junction_comment(comment),
        content_hash=table_content_hash(table_name, comment, columns),
    )


def _foreign_keys(
    connection: sqlite3.Connection,
    table_name: str,
    present: set[str],
) -> list[SchemaEdge]:
    grouped: dict[int, list[sqlite3.Row]] = {}
    for row in connection.execute(f"PRAGMA foreign_key_list({_quote(table_name)})"):
        grouped.setdefault(int(row["id"]), []).append(row)
    edges: list[SchemaEdge] = []
    for key_id, parts in sorted(grouped.items()):
        ordered = sorted(parts, key=lambda item: int(item["seq"]))
        target = str(ordered[0]["table"])
        if target not in present:
            continue
        edges.append(
            SchemaEdge(
                source_table=table_name,
                source_columns=[str(item["from"]) for item in ordered],
                target_table=target,
                target_columns=[str(item["to"]) for item in ordered],
                constraint_name=f"fk_{table_name}_{key_id}",
                weight=1.0,
                inferred=False,
                confidence=1.0,
            )
        )
    return edges


def _quote(identifier: str) -> str:
    if _IDENTIFIER.fullmatch(identifier) is None:
        raise ValueError(f"unexpected sqlite identifier: {identifier}")
    return '"' + identifier + '"'
