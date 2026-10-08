"""门禁失败不能触达数据库，改写 Prompt 也不能携带参考 SQL。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.agents.slow_sql.plan import PlanNode, PlanSummary
from app.agents.slow_sql.workflow import SlowSqlServices, run_slow_sql
from app.sandbox.errors import ExecutionError
from app.sandbox.execute import ExecutionSuccess

_ORIGINAL = "SELECT order_id FROM t_order WHERE (user_id + 0) = 1"
_REWRITE = "SELECT order_id FROM t_order WHERE user_id = 1"


class _RecordingModel:
    def __init__(self, content: str) -> None:
        self.content = content
        self.prompts: list[str] = []
        self.temperatures: list[float] = []
        self.calls = 0

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float,
    ) -> str:
        self.calls += 1
        self.prompts.append(messages[-1]["content"])
        self.temperatures.append(temperature)
        return self.content


def _success(rows: tuple[tuple[object, ...], ...]) -> ExecutionSuccess:
    return ExecutionSuccess(
        columns=(("order_id", "int8"),),
        rows=rows,
        row_count=len(rows),
        truncated=False,
        execution_time_ms=1,
    )


def _plan(*, analyze: bool) -> PlanSummary:
    return PlanSummary(
        total_cost=10,
        execution_time_ms=4 if analyze else None,
        shared_hit_blocks=3 if analyze else None,
        shared_read_blocks=1 if analyze else None,
        nodes=(PlanNode("Seq Scan", "t_order", 10),),
    )


def _services(
    model: _RecordingModel,
    *,
    rows: tuple[tuple[object, ...], ...] = ((1,),),
    calls: list[str] | None = None,
) -> SlowSqlServices:
    async def explain(sql: str, *, analyze: bool) -> PlanSummary | ExecutionError:
        if calls is not None:
            calls.append(sql)
        if "DELETE" in sql.upper():
            raise AssertionError(sql)
        return _plan(analyze=analyze)

    async def execute(sql: str, *, max_rows: int) -> ExecutionSuccess | ExecutionError:
        if calls is not None:
            calls.append(sql)
        if "DELETE" in sql.upper():
            raise AssertionError(sql)
        if "WHERE user_id = 1" in sql and " + 0" not in sql:
            return _success(((1,),))
        return _success(rows)

    return SlowSqlServices(model=model, explain=explain, execute=execute)


async def test_explain_delete_never_reaches_the_database() -> None:
    calls: list[str] = []
    model = _RecordingModel("SELECT 1")
    response = await run_slow_sql(
        _services(model, calls=calls),
        sql="DELETE FROM t_order",
        database_id="ecommerce",
        run_analyze=True,
        rewrite=True,
    )
    assert response.status == "failed"
    assert response.error is not None
    assert response.error.category == "not_read_only"
    assert calls == []
    assert model.calls == 0


async def test_prompt_does_not_contain_the_reference_rewrite() -> None:
    model = _RecordingModel(f"```sql\n{_REWRITE}\n```")
    response = await run_slow_sql(
        _services(model),
        sql=_ORIGINAL,
        database_id="ecommerce",
        run_analyze=False,
        rewrite=True,
    )
    assert model.calls == 0
    assert response.status == "succeeded"
    assert response.original_plan is not None
    assert response.original_plan.execution_time_ms is None
    assert response.original_plan.shared_hit_blocks is None
    assert response.original_plan.shared_read_blocks is None
    assert response.candidate is not None
    assert "user_id = 1" in response.candidate.sql
    assert response.candidate.equivalent is True
    assert response.candidate.execution_time_drop is None
    assert response.candidate.shared_buffer_access_drop is None


async def test_non_equivalent_rewrite_does_not_report_a_cost_drop() -> None:
    model = _RecordingModel("SELECT 1 AS other_value")

    async def execute(sql: str, *, max_rows: int) -> ExecutionSuccess:
        if "other_value" in sql:
            return _success(((2,),))
        return _success(((1,),))

    services = SlowSqlServices(
        model=model,
        explain=lambda sql, *, analyze: _explain_value(analyze),
        execute=execute,
    )
    response = await run_slow_sql(
        services,
        sql="SELECT order_id FROM t_order WHERE user_id = 2",
        database_id="ecommerce",
    )
    assert response.candidate is not None
    assert response.candidate.equivalent is False
    assert response.candidate.planner_cost_drop is None


async def _explain_value(analyze: bool) -> PlanSummary:
    return _plan(analyze=analyze)


async def test_rewrite_can_be_skipped() -> None:
    model = _RecordingModel("SELECT 1")
    response = await run_slow_sql(
        _services(model),
        sql="SELECT * FROM t_order",
        database_id="ecommerce",
        rewrite=False,
    )
    assert model.calls == 0
    assert response.candidate is None
    assert "select-star" in {item.rule_id for item in response.findings}
    assert "seq-scan-on-large-table" in {item.rule_id for item in response.findings}
