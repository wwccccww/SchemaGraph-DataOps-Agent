"""问数状态机的成功、修复和熔断。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.agents.text_to_sql.workflow import (
    MAX_MODEL_CALLS,
    ServiceBundle,
    build_graph,
    run_text_to_sql,
)
from app.graph.expand import EstimatedTokenCounter
from app.mcp.definitions import TOOLS
from app.sandbox.execute import ExecutionSuccess
from app.schemas.catalog import ColumnDocument, TableDocument
from app.schemas.retrieval import SchemaSeed, ToolHit


class ScriptedModel:
    """按预定顺序返回 SQL，并留下实际 Prompt。"""

    def __init__(self, answers: Sequence[str]) -> None:
        self._answers = list(answers)
        self.prompts: list[str] = []

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float,
    ) -> str:
        assert temperature == 0.0
        self.prompts.append(messages[-1]["content"])
        index = min(len(self.prompts) - 1, len(self._answers) - 1)
        return self._answers[index]


class RecordingExecutor:
    """记录真正送到执行器的 SQL。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, sql: str, *, max_rows: int) -> ExecutionSuccess:
        assert max_rows == 1000
        self.calls.append(sql)
        return ExecutionSuccess(
            columns=(("value", "int4"),),
            rows=((1,),),
            row_count=1,
            truncated=False,
            execution_time_ms=0.1,
        )


def _bundle(model: ScriptedModel, executor: RecordingExecutor) -> ServiceBundle:
    tool = TOOLS[0]

    async def select_tools(_question: str) -> list[ToolHit]:
        return [
            ToolHit(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                score=1.0,
            )
        ]

    async def select_seeds(_question: str) -> list[SchemaSeed]:
        return [
            SchemaSeed(
                database_id="ecommerce",
                schema_name="public",
                table_name="t_user_level",
                content_hash="sha256:t_user_level",
                embedding_model="test",
                embedding_version="v1",
                score=1.0,
            )
        ]

    async def load_catalog() -> tuple[list[TableDocument], list[object]]:
        return [
            TableDocument(
                database_id="ecommerce",
                schema_name="public",
                table_name="t_user_level",
                table_comment="会员等级维表",
                columns=[
                    ColumnDocument(
                        name="level_id",
                        data_type="bigint",
                        nullable=False,
                        comment="等级编号",
                    )
                ],
                is_junction=False,
                content_hash="sha256:t_user_level",
            )
        ], []

    return ServiceBundle(
        model=model,
        select_tools=select_tools,
        select_seeds=select_seeds,
        load_catalog=load_catalog,
        execute=executor,
        token_counter=EstimatedTokenCounter(),
    )


def test_graph_uses_the_documented_node_names() -> None:
    graph = build_graph(_bundle(ScriptedModel(["SELECT 1"]), RecordingExecutor()))
    names = set(graph.get_graph().nodes) - {"__start__", "__end__"}  # type: ignore[attr-defined]

    assert names == {
        "route_tools",
        "retrieve_schema",
        "expand_schema_graph",
        "build_prompt",
        "generate_sql",
        "validate_sql",
        "execute_sql",
        "repair_sql",
        "finish",
    }


async def test_successful_generation_executes_once() -> None:
    model = ScriptedModel(["SELECT 1"])
    executor = RecordingExecutor()

    response = await run_text_to_sql(
        _bundle(model, executor),
        question="查询会员等级",
        database_id="ecommerce",
    )

    assert response.status == "succeeded"
    assert response.attempts == 1
    assert response.rows == [[1]]
    assert executor.calls == ["SELECT 1"]
    assert "GOLD_SENTINEL_SQL" not in model.prompts[0]
    assert "t_user_level" in model.prompts[0]
    assert "get_table_schema" in model.prompts[0]


async def test_syntax_error_is_repaired_without_touching_the_database() -> None:
    model = ScriptedModel(["INSERT INTO t_user_level VALUES (1)", "SELECT 1"])
    executor = RecordingExecutor()

    response = await run_text_to_sql(
        _bundle(model, executor),
        question="查询会员等级",
        database_id="ecommerce",
    )

    assert response.status == "succeeded"
    assert response.attempts == 2
    assert executor.calls == ["SELECT 1"]
    assert "上一次 SQL" in model.prompts[1]
    assert "INSERT" in model.prompts[1]
    assert "GOLD_SENTINEL_SQL" not in model.prompts[1]


async def test_identical_errors_trip_the_circuit_breaker() -> None:
    model = ScriptedModel(["INSERT INTO t_user_level VALUES (1)"])
    executor = RecordingExecutor()

    first = await run_text_to_sql(
        _bundle(model, executor),
        question="查询会员等级",
        database_id="ecommerce",
    )
    second = await run_text_to_sql(
        _bundle(model, executor),
        question="查询会员等级",
        database_id="ecommerce",
    )

    assert first.status == "failed"
    assert first.attempts == 3
    assert first.error is not None
    assert first.error.category == "circuit_breaker"
    assert first.error.retryable is False
    assert len(model.prompts) == 6
    assert executor.calls == []
    assert second.error is not None
    assert second.error.category == first.error.category
    assert second.attempts == first.attempts


async def test_alternating_errors_stop_at_the_iteration_limit() -> None:
    model = ScriptedModel(
        [
            "INSERT INTO t_user_level VALUES (1)",
            "SELECT pg_sleep(1)",
            "INSERT INTO t_user_level VALUES (1)",
            "SELECT pg_sleep(1)",
            "SELECT 1",
        ]
    )
    executor = RecordingExecutor()

    response = await run_text_to_sql(
        _bundle(model, executor),
        question="查询会员等级",
        database_id="ecommerce",
    )

    assert response.status == "failed"
    assert response.attempts == MAX_MODEL_CALLS
    assert response.error is not None
    assert response.error.category != "circuit_breaker"
    assert executor.calls == []
    assert len(model.prompts) == MAX_MODEL_CALLS


async def test_validation_only_does_not_execute() -> None:
    executor = RecordingExecutor()

    response = await run_text_to_sql(
        _bundle(ScriptedModel(["SELECT 1"]), executor),
        question="查询会员等级",
        database_id="ecommerce",
        execute=False,
    )

    assert response.status == "succeeded"
    assert response.sql == "SELECT 1"
    assert response.rows == []
    assert executor.calls == []


async def test_unknown_database_does_not_call_the_model() -> None:
    model = ScriptedModel(["SELECT 1"])

    response = await run_text_to_sql(
        _bundle(model, RecordingExecutor()),
        question="查询会员等级",
        database_id="other_db",
    )

    assert response.status == "failed"
    assert response.error is not None
    assert response.error.category == "unsupported_database"
    assert model.prompts == []
