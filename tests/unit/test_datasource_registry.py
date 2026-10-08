"""动态 PostgreSQL datasource 登记。"""

from __future__ import annotations

from app.datasources.registry import (
    register_postgres_catalog_source,
    reset_dynamic_data_sources,
    resolve_data_source,
)


def test_register_postgres_catalog_source() -> None:
    reset_dynamic_data_sources()
    source = register_postgres_catalog_source("tenant_a")
    assert source.profile == "generic"
    assert resolve_data_source("tenant_a") is source
    assert resolve_data_source("ecommerce") is not None
    reset_dynamic_data_sources()
    assert resolve_data_source("tenant_a") is None
