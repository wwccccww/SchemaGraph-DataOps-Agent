"""租户 database_id allowlist。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config.settings import get_settings
from app.schema_registry.tenant import ensure_tenant_database_id, tenant_database_ids


def test_default_allowlist_fixed_ecommerce(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEXT_TO_SQL_CATALOG_MODE", "fixed_ecommerce")
    monkeypatch.delenv("SCHEMA_REGISTRY_TENANT_ALLOWLIST", raising=False)
    get_settings.cache_clear()
    assert tenant_database_ids() == frozenset({"ecommerce"})
    ensure_tenant_database_id("ecommerce")
    with pytest.raises(HTTPException) as exc:
        ensure_tenant_database_id("other_db")
    assert exc.value.status_code == 403


def test_tenant_header_must_match(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        ensure_tenant_database_id("ecommerce", tenant_header="other_db")
    assert exc.value.status_code == 403


def test_explicit_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEMA_REGISTRY_TENANT_ALLOWLIST", "a,b")
    get_settings.cache_clear()
    assert tenant_database_ids() == frozenset({"a", "b"})
    ensure_tenant_database_id("a")
