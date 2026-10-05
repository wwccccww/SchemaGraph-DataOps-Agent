"""问数状态机的成功、修复和熔断。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence

from app.agents.text_to_sql.workflow import (
    MAX_MODEL_CALLS,
    ZERO_SHOT_SCHEMA,
    ServiceBundle,
    build_graph,
    inspect_text_to_sql,
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

    def __init__(
        self,
        rows: tuple[tuple[object, ...], ...] = ((1,),),
        row_sequence: Sequence[tuple[tuple[object, ...], ...]] | None = None,
    ) -> None:
        self.calls: list[str] = []
        self._rows = rows
        self._sequence = row_sequence

    async def __call__(self, sql: str, *, max_rows: int) -> ExecutionSuccess:
        assert max_rows == 1000
        index = len(self.calls)
        self.calls.append(sql)
        rows = self._rows
        if self._sequence is not None:
            rows = self._sequence[min(index, len(self._sequence) - 1)]
        return ExecutionSuccess(
            columns=(("value", "int4"),),
            rows=rows,
            row_count=len(rows),
            truncated=False,
            execution_time_ms=0.1,
        )


def _bundle(
    model: ScriptedModel,
    executor: RecordingExecutor,
    *,
    estimate_plan_rows: Callable[[str], Awaitable[float | None]] | None = None,
) -> ServiceBundle:
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
        estimate_plan_rows=estimate_plan_rows,
    )


async def test_self_healing_starts_from_the_shared_sql_without_a_first_model_call() -> None:
    model = ScriptedModel(["SELECT 1"])
    shared = "SELECT level_id FROM t_user_level"

    inspection = await inspect_text_to_sql(
        _bundle(model, RecordingExecutor()),
        question="查询会员等级",
        database_id="ecommerce",
        initial_sql=shared,
    )

    assert inspection.response.status == "succeeded"
    assert inspection.response.attempts == 1
    assert inspection.response.sql == shared
    assert model.prompts == []


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
    model = ScriptedModel(["SELECT level_id FROM t_user_level"])
    executor = RecordingExecutor()

    response = await run_text_to_sql(
        _bundle(model, executor),
        question="查询会员等级",
        database_id="ecommerce",
    )

    assert response.status == "succeeded"
    assert response.attempts == 1
    assert response.rows == [[1]]
    assert executor.calls == ["SELECT level_id FROM t_user_level"]
    assert "GOLD_SENTINEL_SQL" not in model.prompts[0]
    assert "t_user_level" in model.prompts[0]
    assert "get_table_schema" in model.prompts[0]


async def test_syntax_error_is_repaired_without_touching_the_database() -> None:
    model = ScriptedModel(
        ["INSERT INTO t_user_level VALUES (1)", "SELECT level_id FROM t_user_level"]
    )
    executor = RecordingExecutor()

    response = await run_text_to_sql(
        _bundle(model, executor),
        question="查询会员等级",
        database_id="ecommerce",
    )

    assert response.status == "succeeded"
    assert response.attempts == 2
    assert executor.calls == ["SELECT level_id FROM t_user_level"]
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
    assert first.attempts == 2
    assert first.error is not None
    assert first.error.category == "no_progress"
    assert first.error.retryable is False
    assert len(model.prompts) == 4
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


_LEVEL_SQL = "SELECT level_id FROM t_user_level"


async def test_schema_graph_does_not_review_a_successful_execution() -> None:
    async def estimate(sql: str) -> float | None:
        raise AssertionError(sql)

    model = ScriptedModel(["SELECT 1"])
    response = await run_text_to_sql(
        _bundle(model, RecordingExecutor(), estimate_plan_rows=estimate),
        question="查询会员等级",
        database_id="ecommerce",
        variant="schema_graph",
    )

    assert response.status == "succeeded"
    assert response.attempts == 1
    assert len(model.prompts) == 1
    assert "missing_entity" not in model.prompts[0]


async def test_self_healing_reviews_sql_that_executed_with_the_wrong_shape() -> None:
    model = ScriptedModel(["SELECT 1", _LEVEL_SQL])
    executor = RecordingExecutor()

    response = await run_text_to_sql(
        _bundle(model, executor),
        question="查询会员等级",
        database_id="ecommerce",
    )

    assert response.status == "succeeded"
    assert response.attempts == 2
    assert len(executor.calls) == 2
    assert "missing_entity" in model.prompts[1]
    assert "上一次 SQL" in model.prompts[1]
    assert "required_tables" not in model.prompts[1]
    assert "difficulty" not in model.prompts[1]
    assert "GOLD" not in model.prompts[1]


async def test_empty_result_is_repaired_only_for_self_healing() -> None:
    healed = ScriptedModel([_LEVEL_SQL, _LEVEL_SQL])
    healed_executor = RecordingExecutor(row_sequence=((), ((1,),)))
    healed_response = await run_text_to_sql(
        _bundle(healed, healed_executor),
        question="查询会员等级",
        database_id="ecommerce",
    )
    assert healed_response.status == "succeeded"
    assert healed_response.attempts == 2
    assert "empty_result" in healed.prompts[1]

    graph_model = ScriptedModel([_LEVEL_SQL, _LEVEL_SQL])
    graph_response = await run_text_to_sql(
        _bundle(graph_model, RecordingExecutor(rows=())),
        question="查询会员等级",
        database_id="ecommerce",
        variant="schema_graph",
    )
    assert graph_response.status == "succeeded"
    assert graph_response.attempts == 1
    assert graph_response.rows == []
    assert len(graph_model.prompts) == 1


async def test_huge_plan_triggers_one_review_then_accepts_the_repair() -> None:
    seen: list[str] = []

    async def estimate(_sql: str) -> float | None:
        seen.append(_sql)
        return 100_000_000.0 if len(seen) == 1 else 1.0

    model = ScriptedModel([_LEVEL_SQL, _LEVEL_SQL])
    response = await run_text_to_sql(
        _bundle(model, RecordingExecutor(), estimate_plan_rows=estimate),
        question="查询会员等级",
        database_id="ecommerce",
    )

    assert response.status == "succeeded"
    assert response.attempts == 2
    assert "explain_cardinality" in model.prompts[1]
    assert "required_tables" not in model.prompts[1]


async def test_repeated_semantic_failures_keep_the_executed_sql() -> None:
    model = ScriptedModel(["SELECT 1"])
    response = await run_text_to_sql(
        _bundle(model, RecordingExecutor()),
        question="查询会员等级",
        database_id="ecommerce",
    )

    assert response.status == "succeeded"
    assert response.attempts == 2
    assert response.sql == "SELECT 1"
    assert response.rows == [[1]]
    assert "missing_entity" in model.prompts[1]
    assert "答案契约" in model.prompts[0]
    assert "查询计划" in model.prompts[0]
    assert model.prompts[0].index("答案契约") < model.prompts[0].index("查询计划")
    assert model.prompts[0].index("查询计划") < model.prompts[0].index("可用表")
    assert "required_tables" not in " ".join(model.prompts)
    assert "difficulty" not in " ".join(model.prompts)
    assert "GOLD" not in " ".join(model.prompts)


async def test_contract_repair_stops_when_the_symptom_does_not_clear() -> None:
    question = "统计上个月状态为已支付的订单数量"
    first_sql = (
        "SELECT COUNT(*) AS order_count FROM t_order "
        "WHERE order_status = 'PAID' AND created_at >= CURRENT_DATE"
    )
    second_sql = (
        "SELECT COUNT(*) AS order_count FROM t_order "
        "WHERE order_status = 'PAID' "
        "AND created_at >= TIMESTAMP '2026-09-01 00:00:00' "
        "AND created_at < TIMESTAMP '2026-10-01 00:00:00'"
    )
    model = ScriptedModel([first_sql, second_sql, first_sql])
    executor = RecordingExecutor()

    response = await run_text_to_sql(
        _bundle(model, executor),
        question=question,
        database_id="ecommerce",
    )

    assert response.status == "succeeded"
    assert response.attempts == 2
    assert response.sql == first_sql
    assert executor.calls == [first_sql]
    assert "期望" in model.prompts[1]
    assert "实际" in model.prompts[1]
    assert "GOLD" not in " ".join(model.prompts)
    assert "required_tables" not in " ".join(model.prompts)


def _schools_bundle(model: ScriptedModel, executor: RecordingExecutor) -> ServiceBundle:
    async def select_tools(_question: str) -> list[ToolHit]:
        return []

    async def select_seeds(_question: str) -> list[SchemaSeed]:
        return [
            SchemaSeed(
                database_id="california_schools",
                schema_name="main",
                table_name="schools",
                content_hash="sha256:schools",
                embedding_model="lexical",
                embedding_version="none",
                score=1.0,
            )
        ]

    async def load_catalog() -> tuple[list[TableDocument], list[object]]:
        return [
            TableDocument(
                database_id="california_schools",
                schema_name="main",
                table_name="schools",
                table_comment=None,
                columns=[
                    ColumnDocument(name="cds", data_type="TEXT", nullable=False, comment=None)
                ],
                is_junction=False,
                content_hash="sha256:schools",
            )
        ], []

    return ServiceBundle(
        model=model,
        select_tools=select_tools,
        select_seeds=select_seeds,
        load_catalog=load_catalog,
        execute=executor,
        token_counter=EstimatedTokenCounter(),
        database_id="california_schools",
    )


async def test_registered_sqlite_database_uses_a_generic_prompt() -> None:
    model = ScriptedModel(["SELECT COUNT(*) FROM schools"])
    response = await run_text_to_sql(
        _schools_bundle(model, RecordingExecutor()),
        question="How many schools are there?",
        database_id="california_schools",
        variant="schema_graph",
    )

    assert response.status == "succeeded"
    assert response.error is None
    prompt = model.prompts[0]
    assert "SQLite 数据库 california_schools" in prompt
    assert "答案契约" not in prompt
    assert "护肤品" not in prompt
    assert ZERO_SHOT_SCHEMA not in prompt


async def test_generic_zero_shot_names_the_sqlite_database() -> None:
    model = ScriptedModel(["SELECT 1"])
    response = await run_text_to_sql(
        _schools_bundle(model, RecordingExecutor()),
        question="How many schools are there?",
        database_id="california_schools",
        variant="zero_shot",
        execute=False,
    )

    assert response.status == "succeeded"
    assert "SQLite 数据库 california_schools" in model.prompts[0]
    assert ZERO_SHOT_SCHEMA not in model.prompts[0]
    assert "答案契约" not in model.prompts[0]


async def test_registered_database_with_the_ecommerce_bundle_does_not_call_the_model() -> None:
    model = ScriptedModel(["SELECT 1"])
    response = await run_text_to_sql(
        _bundle(model, RecordingExecutor()),
        question="How many schools are there?",
        database_id="california_schools",
        variant="schema_graph",
    )

    assert response.status == "failed"
    assert response.error is not None
    assert response.error.category == "cross_database_catalog"
    assert response.attempts == 0
    assert model.prompts == []


async def test_catalog_from_another_database_stops_before_the_model() -> None:
    model = ScriptedModel(["SELECT 1"])

    async def select_tools(_question: str) -> list[ToolHit]:
        return []

    async def select_seeds(_question: str) -> list[SchemaSeed]:
        return [
            SchemaSeed(
                database_id="california_schools",
                schema_name="main",
                table_name="schools",
                content_hash="sha256:schools",
                embedding_model="lexical",
                embedding_version="none",
                score=1.0,
            )
        ]

    async def load_catalog() -> tuple[list[TableDocument], list[object]]:
        return [
            TableDocument(
                database_id="ecommerce",
                schema_name="public",
                table_name="schools",
                table_comment=None,
                columns=[
                    ColumnDocument(name="cds", data_type="TEXT", nullable=False, comment=None)
                ],
                is_junction=False,
                content_hash="sha256:schools",
            )
        ], []

    response = await run_text_to_sql(
        ServiceBundle(
            model=model,
            select_tools=select_tools,
            select_seeds=select_seeds,
            load_catalog=load_catalog,
            execute=RecordingExecutor(),
            token_counter=EstimatedTokenCounter(),
            database_id="california_schools",
        ),
        question="How many schools are there?",
        database_id="california_schools",
        variant="schema_graph",
    )

    assert response.status == "failed"
    assert response.error is not None
    assert response.error.category == "cross_database_catalog"
    assert model.prompts == []
