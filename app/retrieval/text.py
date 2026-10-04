"""Schema-RAG 与 Tool-RAG 的向量文本。"""

from __future__ import annotations

from app.schemas.catalog import TableDocument


def schema_document_text(document: TableDocument) -> str:
    """表名、表注释、列名和列注释，不加入额外字段。"""

    parts = [document.table_name]
    if document.table_comment:
        parts.append(document.table_comment)
    for column in document.columns:
        parts.append(column.name)
        if column.comment:
            parts.append(column.comment)
    return " ".join(parts)


def tool_document_text(name: str, description: str) -> str:
    """工具名加用途说明，供 Tool-RAG 编码。"""

    if name.strip() == "" or description.strip() == "":
        raise ValueError("tool embedding text requires a name and description")
    return f"{name} {description}"
