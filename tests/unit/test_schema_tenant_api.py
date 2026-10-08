"""Schema API 租户拒绝。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_active_schema_rejects_unknown_database_id(monkeypatch) -> None:
    monkeypatch.setenv("TEXT_TO_SQL_CATALOG_MODE", "fixed_ecommerce")
    from app.config.settings import get_settings

    get_settings.cache_clear()
    client = TestClient(create_app(initialize=False))
    response = client.get("/v1/schema/active", params={"database_id": "not_allowed"})
    assert response.status_code == 403
