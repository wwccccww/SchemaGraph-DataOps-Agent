"""Text-to-SQL HTTP 入口。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.text_to_sql.runtime import get_default_services
from app.api.deps import TenantHeader
from app.schema_registry.tenant import ensure_tenant_database_id, normalize_request_database_id
from app.agents.text_to_sql.workflow import run_text_to_sql
from app.schemas.text_to_sql import TextToSqlRequest, TextToSqlResponse

router = APIRouter(prefix="/v1", tags=["text-to-sql"])
TextToSqlHandler = Callable[[TextToSqlRequest], Awaitable[TextToSqlResponse]]


async def handle_text_to_sql(body: TextToSqlRequest) -> TextToSqlResponse:
    """用默认模型网关回答一个问题。"""

    return await run_text_to_sql(
        get_default_services(),
        question=body.question,
        database_id=body.database_id,
        execute=body.execute,
        max_rows=body.max_rows,
    )


def get_text_to_sql_handler() -> TextToSqlHandler:
    """测试可以替换这个依赖。"""

    return handle_text_to_sql


@router.post("/text-to-sql", response_model=TextToSqlResponse, response_model_exclude_none=True)
async def text_to_sql(
    body: TextToSqlRequest,
    handler: Annotated[TextToSqlHandler, Depends(get_text_to_sql_handler)],
    tenant_header: TenantHeader = None,
) -> TextToSqlResponse:
    """生成只读 SQL，并在请求要求时放到沙箱执行。"""

    normalized = ensure_tenant_database_id(body.database_id, tenant_header=tenant_header)
    if normalized != body.database_id:
        body = body.model_copy(update={"database_id": normalized})
    return await handler(body)
