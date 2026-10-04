"""健康检查响应契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["ok", "unavailable"]


class HealthChecks(BaseModel):
    """阶段 0 的三项就绪检查。"""

    database: CheckStatus
    pgvector: CheckStatus
    sandbox_role: CheckStatus


class HealthResponse(BaseModel):
    """空 API 的就绪状态。"""

    status: CheckStatus
    checks: HealthChecks = Field(description="数据库、pgvector 和沙箱角色的独立状态")


def build_health_response(
    *,
    database_ok: bool,
    pgvector_ok: bool,
    sandbox_ok: bool,
) -> HealthResponse:
    """把布尔检查结果转换为稳定响应。"""

    checks = HealthChecks(
        database="ok" if database_ok else "unavailable",
        pgvector="ok" if pgvector_ok else "unavailable",
        sandbox_role="ok" if sandbox_ok else "unavailable",
    )
    ready = database_ok and pgvector_ok and sandbox_ok
    return HealthResponse(status="ok" if ready else "unavailable", checks=checks)
