"""问数和慢 SQL 各写一条 Trace，并且只包含约定字段。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

import pytest
from app.agents.slow_sql.plan import PlanNode, PlanSummary
from app.agents.slow_sql.workflow import SlowSqlServices, run_slow_sql
from app.agents.text_to_sql.workflow import run_text_to_sql
from app.observability.tracing import (
    TRACE_FIELDS,
    RequestTrace,
    attribute_map,
    clear_spans,
    finished_spans,
    request_span,
    set_request_attributes,
    sql_hash,
)
from app.sandbox.errors import ExecutionError
from tests.unit.test_text_to_sql_workflow import RecordingExecutor, ScriptedModel, _bundle


class _QuietModel:
    def __init__(self, content: str = "SELECT 1") -> None:
        self.content = content

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float,
    ) -> str:
        assert temperature == 0.0
        assert messages
        return self.content


def _slow_services() -> SlowSqlServices:
    async def explain(sql: str, *, analyze: bool) -> PlanSummary | ExecutionError:
        assert "DELETE" not in sql.upper()
        return PlanSummary(
            total_cost=10,
            execution_time_ms=4 if analyze else None,
            shared_hit_blocks=3 if analyze else None,
            shared_read_blocks=1 if analyze else None,
            nodes=(PlanNode("Seq Scan", "t_order", 10),),
        )

    async def execute(sql: str, *, max_rows: int) -> ExecutionError:
        raise AssertionError(f"{sql} max_rows={max_rows}")

    return SlowSqlServices(model=_QuietModel(), explain=explain, execute=execute)


def _text(attributes: Mapping[str, object]) -> str:
    return " ".join(str(value) for value in attributes.values())


async def test_success_span_records_only_the_required_fields() -> None:
    clear_spans()
    response = await run_text_to_sql(
        _bundle(ScriptedModel(["SELECT level_id FROM t_user_level"]), RecordingExecutor()),
        question="查询会员等级",
        database_id="ecommerce",
    )

    assert response.status == "succeeded"
    spans = finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "text_to_sql"
    attributes = attribute_map(spans[0])
    assert set(attributes) == set(TRACE_FIELDS)
    assert attributes["request_type"] == "text_to_sql"
    assert attributes["model_name"] == "unspecified"
    assert tuple(cast(Sequence[object], attributes["retrieved_seed_tables"])) == ("t_user_level",)
    assert tuple(cast(Sequence[object], attributes["expanded_tables"])) == ()
    assert int(cast(int, attributes["schema_context_tokens"])) > 0
    assert tuple(cast(Sequence[object], attributes["selected_tools"])) == ("get_table_schema",)
    assert attributes["generation_attempt"] == 1
    assert response.sql is not None
    assert attributes["sql_hash"] == sql_hash(response.sql)
    assert attributes["error_hash"] == ""
    assert attributes["db_execution_ms"] == 0.1
    assert attributes["planner_total_cost"] == 0.0
    assert attributes["result_row_count"] == 1
    assert attributes["circuit_breaker_triggered"] is False
    rendered = _text(attributes)
    assert "查询会员等级" not in rendered
    assert response.sql not in rendered
    assert "level_id" not in rendered


async def test_unsupported_database_still_emits_one_span() -> None:
    clear_spans()
    response = await run_text_to_sql(
        _bundle(ScriptedModel(["SELECT 1"]), RecordingExecutor()),
        question="查询会员等级",
        database_id="warehouse",
    )

    assert response.status == "failed"
    assert response.attempts == 0
    spans = finished_spans()
    assert len(spans) == 1
    attributes = attribute_map(spans[0])
    assert attributes["generation_attempt"] == 0
    assert tuple(cast(Sequence[object], attributes["selected_tools"])) == ()
    assert attributes["sql_hash"] == ""
    assert attributes["circuit_breaker_triggered"] is False


async def test_slow_sql_span_records_plan_cost_without_rows() -> None:
    clear_spans()
    response = await run_slow_sql(
        _slow_services(),
        sql="SELECT order_id FROM t_order",
        database_id="ecommerce",
        run_analyze=True,
        rewrite=False,
    )

    assert response.status == "succeeded"
    spans = finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "slow_sql"
    attributes = attribute_map(spans[0])
    assert set(attributes) == set(TRACE_FIELDS)
    assert attributes["planner_total_cost"] == 10
    assert attributes["db_execution_ms"] == 4
    assert attributes["result_row_count"] == 0
    assert attributes["generation_attempt"] == 0
    assert attributes["circuit_breaker_triggered"] is False
    assert str(attributes["sql_hash"]).startswith("sha256:")
    assert "SELECT" not in _text(attributes)


def test_trace_rejects_fields_outside_the_contract() -> None:
    clear_spans()
    payload: dict[str, object] = {
        "request_type": "text_to_sql",
        "model_name": "unspecified",
        "retrieved_seed_tables": (),
        "expanded_tables": (),
        "schema_context_tokens": 0,
        "selected_tools": (),
        "generation_attempt": 0,
        "sql_hash": "",
        "error_hash": "",
        "db_execution_ms": 0.0,
        "planner_total_cost": 0.0,
        "result_row_count": 0,
        "circuit_breaker_triggered": False,
        "question": "不能进入 Trace 的问题",
    }
    with request_span("text_to_sql") as span, pytest.raises(ValueError, match="architecture"):
        set_request_attributes(span, cast(RequestTrace, cast(Any, payload)))
    spans = finished_spans()
    assert len(spans) == 1
    assert "question" not in attribute_map(spans[0])
    assert "不能进入 Trace" not in _text(attribute_map(spans[0]))
