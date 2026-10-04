"""阶段 0 的就绪检查路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.db.health import check_health
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(
    report: Annotated[HealthResponse, Depends(check_health)],
) -> HealthResponse | JSONResponse:
    """数据库、pgvector 或沙箱角色未就绪时返回 503。"""

    if report.status != "ok":
        return JSONResponse(status_code=503, content=report.model_dump())
    return report
