"""幂等初始化 pgvector 与 sandbox_readonly 角色。"""

from __future__ import annotations

import asyncio
import logging
import re

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_INIT_LOCK_KEY = "schemagraph.db_init"
_RETRYABLE_ERRORS = (ConnectionError, TimeoutError, OSError)
_QUOTED_LITERAL = re.compile(r"^(?:E)?'(?:''|\\.|[^'])*'$", re.DOTALL)


def is_retryable_database_error(exc: BaseException) -> bool:
    """仅对数据库尚未就绪的连接错误重试，认证和配置错误立即失败。"""

    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (asyncpg.InvalidPasswordError, asyncpg.InvalidCatalogNameError)):
            return False
        if isinstance(current, asyncpg.CannotConnectNowError):
            return True
        if isinstance(current, _RETRYABLE_ERRORS) and not isinstance(
            current, asyncpg.PostgresError
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


async def initialize_database(settings: Settings | None = None) -> None:
    """创建 pgvector 扩展和最小权限沙箱角色。"""

    current = settings or get_settings()
    engine = create_async_engine(
        current.admin_url(),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text("SELECT pg_advisory_lock(hashtext(:key)::bigint)"),
                {"key": _INIT_LOCK_KEY},
            )
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await _ensure_sandbox_role(conn, current)
                await _grant_sandbox_privileges(conn, current.postgres_db)
            finally:
                await conn.execute(
                    text("SELECT pg_advisory_unlock(hashtext(:key)::bigint)"),
                    {"key": _INIT_LOCK_KEY},
                )
    finally:
        await engine.dispose()


async def initialize_database_with_retry(settings: Settings | None = None) -> None:
    """在数据库容器启动窗口内重试初始化。"""

    current = settings or get_settings()
    for attempt in range(1, current.db_init_attempts + 1):
        try:
            await initialize_database(current)
            return
        except Exception as exc:
            if not is_retryable_database_error(exc) or attempt == current.db_init_attempts:
                raise
            logger.info(
                "database is not ready (attempt %s, %s)",
                attempt,
                type(exc).__name__,
            )
            await asyncio.sleep(current.db_init_delay_seconds)


async def _ensure_sandbox_role(conn: AsyncConnection, settings: Settings) -> None:
    quoted_password = _quoted_literal(
        await conn.scalar(
            text("SELECT quote_literal(:password)"),
            {"password": settings.sandbox_db_password.get_secret_value()},
        )
    )
    role_exists = await conn.scalar(
        text("SELECT 1 FROM pg_roles WHERE rolname = 'sandbox_readonly'")
    )
    statement = (
        f"ALTER ROLE sandbox_readonly WITH LOGIN PASSWORD {quoted_password}"
        if role_exists is not None
        else f"CREATE ROLE sandbox_readonly LOGIN PASSWORD {quoted_password}"
    )
    try:
        await conn.execute(text(statement))
    except Exception:
        raise RuntimeError("failed to configure sandbox role") from None
    for statement in (
        "ALTER ROLE sandbox_readonly SET default_transaction_read_only = on",
        "ALTER ROLE sandbox_readonly SET statement_timeout = '5s'",
        "ALTER ROLE sandbox_readonly SET lock_timeout = '1s'",
        "ALTER ROLE sandbox_readonly SET idle_in_transaction_session_timeout = '2s'",
    ):
        await conn.execute(text(statement))


def _quoted_literal(value: object) -> str:
    if not isinstance(value, str) or _QUOTED_LITERAL.fullmatch(value) is None:
        raise RuntimeError("database returned an invalid quoted literal")
    return value


async def _grant_sandbox_privileges(conn: AsyncConnection, database: str) -> None:
    statements = (
        f"GRANT CONNECT ON DATABASE {database} TO sandbox_readonly",
        "GRANT USAGE ON SCHEMA public TO sandbox_readonly",
        "GRANT SELECT ON ALL TABLES IN SCHEMA public TO sandbox_readonly",
        f"REVOKE TEMP ON DATABASE {database} FROM PUBLIC",
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
        "REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sandbox_readonly",
    )
    for statement in statements:
        await conn.execute(text(statement))


def main() -> None:
    """提供 `python -m app.db.initialize` 入口。"""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(initialize_database_with_retry())


if __name__ == "__main__":
    main()
