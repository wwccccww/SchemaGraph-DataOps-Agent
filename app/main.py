"""FastAPI 应用入口。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.health import router as health_router
from app.api.text_to_sql import router as text_to_sql_router
from app.db.engine import dispose_engines
from app.db.initialize import initialize_database_with_retry


def create_app(*, initialize: bool = True) -> FastAPI:
    """创建空 API。测试可以关闭启动时的数据库初始化。"""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if initialize:
            await initialize_database_with_retry()
        yield
        await dispose_engines()

    app = FastAPI(
        title="SchemaGraph-DataOps-Agent",
        version=__version__,
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(text_to_sql_router)
    return app


app = create_app()
