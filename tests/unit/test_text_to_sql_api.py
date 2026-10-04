"""Text-to-SQL 路由返回契约中的成功和失败形状。"""

from __future__ import annotations

from app.api.text_to_sql import get_text_to_sql_handler
from app.main import create_app
from app.schemas.text_to_sql import ApiError, SchemaContextView, TextToSqlRequest, TextToSqlResponse
from httpx import ASGITransport, AsyncClient


async def test_text_to_sql_route_returns_success_and_failure() -> None:
    app = create_app(initialize=False)

    async def fake_handler(body: TextToSqlRequest) -> TextToSqlResponse:
        if body.question == "失败":
            return TextToSqlResponse(
                request_id="req_test",
                status="failed",
                attempts=0,
                error=ApiError(
                    category="schema_path_budget_exceeded",
                    message="必需路径超过Schema上下文预算",
                    retryable=False,
                ),
            )
        return TextToSqlResponse(
            request_id="req_test",
            status="succeeded",
            sql="SELECT 1",
            columns=["value"],
            rows=[[1]],
            schema_context=SchemaContextView(
                seed_tables=["t_user_level"],
                expanded_tables=[],
                token_count=12,
                truncated=False,
            ),
            attempts=1,
        )

    app.dependency_overrides[get_text_to_sql_handler] = lambda: fake_handler
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        success = await client.post(
            "/v1/text-to-sql",
            json={"question": "查询会员等级", "database_id": "ecommerce"},
        )
        failure = await client.post(
            "/v1/text-to-sql",
            json={"question": "失败", "database_id": "ecommerce", "execute": False},
        )
        invalid = await client.post(
            "/v1/text-to-sql",
            json={"question": "查询", "database_id": "bad id"},
        )

    assert success.status_code == 200
    assert success.json()["status"] == "succeeded"
    assert success.json()["rows"] == [[1]]
    assert "error" not in success.json()
    assert failure.status_code == 200
    assert failure.json()["error"]["category"] == "schema_path_budget_exceeded"
    assert "sql" not in failure.json()
    assert invalid.status_code == 422
