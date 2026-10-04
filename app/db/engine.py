"""管理进程内的 SQLAlchemy 异步连接池。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config.settings import get_settings

_admin_engine: AsyncEngine | None = None
_sandbox_engine: AsyncEngine | None = None


def get_admin_engine() -> AsyncEngine:
    """返回管理角色连接池。"""

    global _admin_engine
    if _admin_engine is None:
        _admin_engine = create_async_engine(
            get_settings().admin_url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=0,
        )
    return _admin_engine


def get_sandbox_engine() -> AsyncEngine:
    """返回沙箱只读角色连接池。"""

    global _sandbox_engine
    if _sandbox_engine is None:
        _sandbox_engine = create_async_engine(
            get_settings().sandbox_url(),
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=0,
        )
    return _sandbox_engine


async def dispose_engines() -> None:
    """关闭并丢弃连接池，避免改密后复用旧会话。"""

    global _admin_engine, _sandbox_engine
    engines = (_admin_engine, _sandbox_engine)
    _admin_engine = None
    _sandbox_engine = None
    for engine in engines:
        if engine is not None:
            await engine.dispose()
