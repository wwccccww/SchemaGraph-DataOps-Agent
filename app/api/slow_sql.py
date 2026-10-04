"""慢 SQL HTTP 入口。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.slow_sql.runtime import get_default_services
from app.agents.slow_sql.workflow import run_slow_sql
from app.schemas.slow_sql import SlowSqlRequest, SlowSqlResponse

router = APIRouter(prefix="/v1", tags=["slow-sql"])
SlowSqlHandler = Callable[[SlowSqlRequest], Awaitable[SlowSqlResponse]]


async def handle_slow_sql(body: SlowSqlRequest) -> SlowSqlResponse:
    """用默认模型网关诊断一条 SQL。"""

    return await run_slow_sql(
        get_default_services(),
        sql=body.sql,
        database_id=body.database_id,
        run_analyze=body.run_analyze,
        rewrite=body.rewrite,
    )


def get_slow_sql_handler() -> SlowSqlHandler:
    """测试可以替换这个依赖。"""

    return handle_slow_sql


@router.post("/slow-sql/diagnose", response_model=SlowSqlResponse)
async def diagnose_slow_sql(
    body: SlowSqlRequest,
    handler: Annotated[SlowSqlHandler, Depends(get_slow_sql_handler)],
) -> SlowSqlResponse:
    """返回规则、计划摘要和可选改写。未知的运行时指标保持 null。"""

    return await handler(body)
