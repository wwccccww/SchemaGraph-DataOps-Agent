"""检查管理连接、pgvector 和沙箱角色是否可用。"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.engine import get_admin_engine, get_sandbox_engine
from app.schemas.health import HealthResponse, build_health_response

logger = logging.getLogger(__name__)


async def check_health() -> HealthResponse:
    """执行就绪检查；失败时只记录异常类型，不记录连接串或密码。"""

    database_ok = False
    pgvector_ok = False
    role_exists = False
    try:
        async with get_admin_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
            database_ok = True
            pgvector_ok = (
                await conn.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
                is not None
            )
            role_exists = (
                await conn.scalar(
                    text(
                        """
                        SELECT 1
                        FROM pg_roles
                        WHERE rolname = 'sandbox_readonly' AND rolcanlogin
                        """
                    )
                )
                is not None
            )
    except Exception as exc:
        logger.error("admin health check failed: %s", type(exc).__name__)
        return build_health_response(
            database_ok=False,
            pgvector_ok=False,
            sandbox_ok=False,
        )

    return build_health_response(
        database_ok=database_ok,
        pgvector_ok=pgvector_ok,
        sandbox_ok=role_exists and await _sandbox_can_query(),
    )


async def _sandbox_can_query() -> bool:
    try:
        async with get_sandbox_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("sandbox health check failed: %s", type(exc).__name__)
        return False
