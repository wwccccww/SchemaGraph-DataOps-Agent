"""验证 pgvector 初始化可以重复执行，并且健康检查通过。"""

from __future__ import annotations

import pytest
from app.db.engine import get_admin_engine
from app.db.initialize import initialize_database
from app.main import create_app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def test_initialize_database_is_idempotent(database_settings) -> None:
    await initialize_database(database_settings)

    async with get_admin_engine().connect() as conn:
        extension = await conn.scalar(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )

    assert extension == "vector"


async def test_health_endpoint_reports_ready_database(database_settings) -> None:
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "database": "ok",
            "pgvector": "ok",
            "sandbox_role": "ok",
        },
    }
