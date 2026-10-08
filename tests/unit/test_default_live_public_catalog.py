"""默认问数走 live_public generic PG catalog。"""

from __future__ import annotations

from app.config.settings import get_settings


def test_settings_default_catalog_mode_is_live_public(monkeypatch) -> None:
    monkeypatch.delenv("TEXT_TO_SQL_CATALOG_MODE", raising=False)
    get_settings.cache_clear()
    assert get_settings().text_to_sql_catalog_mode == "live_public"


def test_ecommerce_alias_normalizes_to_postgres_db(monkeypatch) -> None:
    monkeypatch.delenv("TEXT_TO_SQL_CATALOG_MODE", raising=False)
    get_settings.cache_clear()
    from app.schema_registry.tenant import normalize_request_database_id

    settings = get_settings()
    assert normalize_request_database_id("ecommerce") == settings.postgres_db
