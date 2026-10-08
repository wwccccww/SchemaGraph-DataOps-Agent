"""租户 database_id 隔离（进程内 allowlist + 可选请求头绑定）。"""

from __future__ import annotations

from fastapi import HTTPException

from app.config.settings import Settings, get_settings


def tenant_database_ids(settings: Settings | None = None) -> frozenset[str]:
    """当前实例允许访问的 database_id 集合。"""

    resolved = settings or get_settings()
    raw = resolved.schema_registry_tenant_allowlist.strip()
    if raw:
        return frozenset(
            item.strip()
            for item in raw.split(",")
            if item.strip()
        )
    if resolved.text_to_sql_catalog_mode == "live_public":
        return frozenset({resolved.postgres_db})
    return frozenset({"ecommerce"})


def default_schema_database_id(settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    allowed = tenant_database_ids(resolved)
    if resolved.text_to_sql_catalog_mode == "live_public":
        if resolved.postgres_db in allowed:
            return resolved.postgres_db
    if "ecommerce" in allowed:
        return "ecommerce"
    return next(iter(allowed))


def ensure_tenant_database_id(
    database_id: str,
    *,
    tenant_header: str | None = None,
    settings: Settings | None = None,
) -> str:
    """拒绝跨租户 database_id；可选 `X-Tenant-Database-Id` 必须与 body 一致。"""

    resolved = settings or get_settings()
    allowed = tenant_database_ids(resolved)
    if database_id not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "database_id not in tenant allowlist",
                "database_id": database_id,
                "allowed": sorted(allowed),
            },
        )
    if tenant_header is not None and tenant_header != database_id:
        raise HTTPException(
            status_code=403,
            detail="X-Tenant-Database-Id does not match database_id",
        )
    return database_id
