"""应用或删除电商 12 表。DDL 文本与设计文档保持一致。"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.tables import TABLE_NAMES

_SQL_PATH = Path(__file__).with_name("sql") / "ecommerce.sql"
_SANDBOX_ROLE = "sandbox_readonly"


def ecommerce_sql() -> str:
    """返回基准 DDL 原文。"""

    return _SQL_PATH.read_text(encoding="utf-8")


def split_ecommerce_sql(sql: str | None = None) -> tuple[list[str], list[str]]:
    """拆成表定义和索引语句。造数时先装载数据再创建索引。"""

    statements: list[str] = []
    for chunk in (sql if sql is not None else ecommerce_sql()).split(";"):
        statement = chunk.strip()
        if statement and re.search(r"[A-Za-z0-9_]", statement):
            statements.append(statement)
    indexes = [item for item in statements if item.upper().startswith("CREATE INDEX")]
    tables = [item for item in statements if item not in indexes]
    return tables, indexes


async def drop_ecommerce_schema(conn: AsyncConnection) -> None:
    """删除 12 张业务表，不触碰扩展和其他对象。"""

    for name in reversed(TABLE_NAMES):
        await conn.execute(text(f"DROP TABLE IF EXISTS {name} CASCADE"))


async def apply_ecommerce_schema(conn: AsyncConnection, *, indexes: bool = True) -> None:
    """重建 12 张表，并把现有及后续表的 SELECT 授予沙箱角色。"""

    await drop_ecommerce_schema(conn)
    tables, index_statements = split_ecommerce_sql()
    for statement in tables:
        await conn.execute(text(statement))
    if indexes:
        await _create_indexes(conn, index_statements)
    await conn.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {_SANDBOX_ROLE}"))


async def create_ecommerce_indexes(conn: AsyncConnection) -> None:
    """在数据装载之后创建基准索引。"""

    _, index_statements = split_ecommerce_sql()
    await _create_indexes(conn, index_statements)


async def _create_indexes(conn: AsyncConnection, statements: list[str]) -> None:
    for statement in statements:
        await conn.execute(text(statement))
