"""失败注入不能把问题、SQL 或凭据写进 Trace。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.agents.slow_sql.workflow import SlowSqlServices, run_slow_sql
from app.agents.text_to_sql.workflow import run_text_to_sql
from app.observability.tracing import attribute_map, clear_spans, finished_spans
from app.sandbox.errors import ExecutionError
from app.sandbox.execute import ExecutionSuccess
from tests.unit.test_text_to_sql_workflow import RecordingExecutor, ScriptedModel, _bundle

_SECRET = "planted-secret-value-9f3a"


def _rendered(attributes: Mapping[str, object]) -> str:
    return " ".join(str(value) for value in attributes.values())


async def test_repeated_writes_trip_the_breaker_without_leaking_into_the_trace() -> None:
    clear_spans()
    sql = f"INSERT INTO t_user_level VALUES (1) -- {_SECRET}"
    question = f"查询会员等级 {_SECRET} postgres://sandbox:{_SECRET}@db:5432/text2sql_db"
    response = await run_text_to_sql(
        _bundle(ScriptedModel([sql]), RecordingExecutor()),
        question=question,
        database_id="ecommerce",
    )

    assert response.status == "failed"
    assert response.attempts == 2
    assert response.error is not None
    assert response.error.category == "no_progress"
    spans = finished_spans()
    assert len(spans) == 1
    attributes = attribute_map(spans[0])
    assert attributes["circuit_breaker_triggered"] is True
    assert str(attributes["error_hash"]).startswith("sha256:")
    assert str(attributes["sql_hash"]).startswith("sha256:")
    assert attributes["sql_hash"] != sql
    rendered = _rendered(attributes)
    assert _SECRET not in rendered
    assert "postgres://" not in rendered
    assert "INSERT" not in rendered
    assert question not in rendered


async def test_slow_sql_write_is_rejected_before_the_database_and_hashed() -> None:
    clear_spans()
    sql = f"DELETE FROM t_order -- {_SECRET}"

    async def explain(statement: str, *, analyze: bool) -> ExecutionError:
        raise AssertionError(f"{statement} analyze={analyze}")

    async def execute(statement: str, *, max_rows: int) -> ExecutionSuccess:
        raise AssertionError(f"{statement} max_rows={max_rows}")

    class _Model:
        calls = 0

        async def complete(
            self,
            messages: Sequence[Mapping[str, str]],
            *,
            temperature: float,
        ) -> str:
            self.calls += 1
            assert temperature == 0.0
            assert messages
            return "SELECT 1"

    model = _Model()
    response = await run_slow_sql(
        SlowSqlServices(model=model, explain=explain, execute=execute),
        sql=sql,
        database_id="ecommerce",
    )

    assert response.status == "failed"
    assert response.error is not None
    assert response.error.category == "not_read_only"
    assert model.calls == 0
    spans = finished_spans()
    assert len(spans) == 1
    attributes = attribute_map(spans[0])
    assert str(attributes["sql_hash"]).startswith("sha256:")
    assert attributes["sql_hash"] != sql
    assert attributes["error_hash"] != ""
    assert str(attributes["error_hash"]).startswith("sha256:")
    assert attributes["circuit_breaker_triggered"] is False
    rendered = _rendered(attributes)
    assert _SECRET not in rendered
    assert "DELETE" not in rendered
    assert sql not in rendered
