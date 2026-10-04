"""不连接数据库的健康检查契约测试。"""

from __future__ import annotations

import pytest
from app.api.health import check_health
from app.main import create_app
from app.schemas.health import HealthResponse, build_health_response
from httpx import ASGITransport, AsyncClient


def test_build_health_response_requires_every_check() -> None:
    partial = build_health_response(database_ok=True, pgvector_ok=True, sandbox_ok=False)

    assert partial.status == "unavailable"
    assert partial.checks.database == "ok"
    assert partial.checks.sandbox_role == "unavailable"


@pytest.mark.parametrize("ready", [True, False])
async def test_health_route(ready: bool) -> None:
    app = create_app(initialize=False)

    def fake_check() -> HealthResponse:
        return build_health_response(
            database_ok=ready,
            pgvector_ok=ready,
            sandbox_ok=ready,
        )

    app.dependency_overrides[check_health] = fake_check
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == (200 if ready else 503)
    assert response.json()["status"] == ("ok" if ready else "unavailable")


def test_create_app_does_not_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called() -> None:
        raise AssertionError("database initialization should not run at import")

    monkeypatch.setattr("app.main.initialize_database_with_retry", fail_if_called)
    create_app(initialize=False)
