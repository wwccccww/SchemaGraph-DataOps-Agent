"""慢 SQL 路由保留 null 时间字段，并拒绝非法 database_id。"""

from __future__ import annotations

from app.agents.slow_sql.plan import PlanSummary
from app.agents.slow_sql.workflow import SlowSqlServices, run_slow_sql
from app.api.slow_sql import get_slow_sql_handler
from app.main import create_app
from app.sandbox.execute import ExecutionSuccess
from app.schemas.slow_sql import SlowSqlRequest, SlowSqlResponse
from httpx import ASGITransport, AsyncClient


def _services() -> SlowSqlServices:
    class Model:
        async def complete(self, messages: object, *, temperature: float) -> str:
            del messages, temperature
            return "SELECT order_id FROM t_order WHERE user_id = 1"

    async def explain(sql: str, *, analyze: bool) -> PlanSummary:
        del sql
        return PlanSummary(
            total_cost=12,
            execution_time_ms=8 if analyze else None,
            shared_hit_blocks=2 if analyze else None,
            shared_read_blocks=1 if analyze else None,
            nodes=(),
        )

    async def execute(sql: str, *, max_rows: int) -> ExecutionSuccess:
        del sql, max_rows
        return ExecutionSuccess(
            columns=(("order_id", "int8"),),
            rows=((1,),),
            row_count=1,
            truncated=False,
            execution_time_ms=1,
        )

    return SlowSqlServices(model=Model(), explain=explain, execute=execute)


async def test_diagnose_route_preserves_null_runtime_fields() -> None:
    app = create_app(initialize=False)
    services = _services()

    async def handler(body: SlowSqlRequest) -> SlowSqlResponse:
        return await run_slow_sql(
            services,
            sql=body.sql,
            database_id=body.database_id,
            run_analyze=body.run_analyze,
            rewrite=body.rewrite,
        )

    app.dependency_overrides[get_slow_sql_handler] = lambda: handler
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        quiet = await client.post(
            "/v1/slow-sql/diagnose",
            json={
                "database_id": "ecommerce",
                "sql": "SELECT order_id FROM t_order WHERE (user_id + 0) = 1",
                "run_analyze": False,
                "rewrite": True,
            },
        )
        invalid = await client.post(
            "/v1/slow-sql/diagnose",
            json={"database_id": "bad id", "sql": "SELECT 1"},
        )
    assert quiet.status_code == 200
    body = quiet.json()
    assert body["status"] == "succeeded"
    assert body["original_plan"]["execution_time_ms"] is None
    assert body["original_plan"]["shared_hit_blocks"] is None
    assert body["original_plan"]["shared_read_blocks"] is None
    assert body["candidate"]["execution_time_drop"] is None
    assert invalid.status_code == 422
