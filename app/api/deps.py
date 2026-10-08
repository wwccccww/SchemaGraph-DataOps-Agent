"""共享 API 依赖。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

TenantHeader = Annotated[
    str | None,
    Header(alias="X-Tenant-Database-Id", description="必须与请求体 database_id 一致"),
]
