"""消融变体、召回、token 和不可覆盖的报告。不下载模型。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

from app.agents.text_to_sql.workflow import (
    ZERO_SHOT_SCHEMA,
    ServiceBundle,
    run_text_to_sql,
)
from app.evaluation.ablation import (
    TARGETS,
    CaseResult,
    baseline_schema_tokens,
    build_summary,
    evaluate_case,
    junction_recall_for_case,
    percentile,
    write_ablation_report,
)
from app.graph.expand import EstimatedTokenCounter
from app.sandbox.execute import ExecutionSuccess
from app.schemas.benchmark import BenchmarkCase
from app.schemas.catalog import ColumnDocument, SchemaEdge, TableDocument
from app.schemas.retrieval import SchemaSeed, ToolHit

_GOLD = "SELECT gold_marker_secret FROM t_user_level"


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


def _document(name: str, *, junction: bool) -> TableDocument:
    return TableDocument(
        database_id="ecommerce",
        schema_name="public",
        table_name=name,
        table_comment=name,
        columns=[ColumnDocument(name="id", data_type="bigint", nullable=False, comment=None)],
        is_junction=junction,
        content_hash=f"sha256:{name}",
    )


def _edge(source: str, target: str) -> SchemaEdge:
    return SchemaEdge(
        source_table=source,
        source_columns=["id"],
        target_table=target,
        target_columns=["id"],
        constraint_name=f"{source}_{target}_fkey",
        weight=1,
        inferred=False,
        confidence=1,
    )


def _bundle(
    model: ScriptedModel,
    executor: RecordingExecutor,
    *,
    seeds: Sequence[str],
    documents: Sequence[TableDocument],
    edges: Sequence[SchemaEdge],
    fail_retrieval: bool = False,
) -> ServiceBundle:
    async def select_tools(_question: str) -> list[ToolHit]:
        if fail_retrieval:
            raise AssertionError("zero_shot must not retrieve tools")
        return [
            ToolHit(
                name="get_table_schema",
                description="读取表结构",
                input_schema={"type": "object"},
                score=1.0,
            )
        ]

    async def select_seeds(_question: str) -> list[SchemaSeed]:
        if fail_retrieval:
            raise AssertionError("zero_shot must not retrieve seeds")
        return [
            SchemaSeed(
                database_id="ecommerce",
                schema_name="public",
                table_name=name,
                content_hash=f"sha256:{name}",
                embedding_model="test",
                embedding_version="v1",
                score=1.0,
            )
            for name in seeds
        ]

    async def load_catalog() -> tuple[list[TableDocument], list[SchemaEdge]]:
        if fail_retrieval:
            raise AssertionError("zero_shot must not load the catalog")
        return list(documents), list(edges)

    return ServiceBundle(
        model=model,
        select_tools=select_tools,
        select_seeds=select_seeds,
        load_catalog=load_catalog,
        execute=executor,
        token_counter=EstimatedTokenCounter(),
    )


def _case() -> BenchmarkCase:
    return BenchmarkCase(
        id="custom_basic_001",
        source="custom",
        source_version="ecommerce-v1",
        database_id="ecommerce",
        difficulty="basic",
        dialect="postgres",
        question="按等级编号升序查询全部会员等级",
        gold_sql=_GOLD,
        required_tables=["t_user_level"],
        required_junctions=["t_user_region_map"],
        order_sensitive=True,
        numeric_tolerance=None,
        expected_columns=["value"],
        anchor_date=date(2026, 10, 1),
        tags=["order"],
    )


def _result(case_id: str, variant: str, **overrides: object) -> CaseResult:
    payload: dict[str, object] = {
        "case_id": case_id,
        "variant": variant,
        "passed": False,
        "attempts": 1,
        "seed_tables": (),
        "expanded_tables": (),
        "junction_recall": None,
        "schema_tokens": 10,
        "latency_ms": 1,
        "error_category": None,
        "difficulty": "basic",
        "ex": 0,
        "leaked_junctions": (),
    }
    payload.update(overrides)
    return CaseResult(**payload)  # type: ignore[arg-type]


async def test_zero_shot_skips_retrieval_and_hides_gold() -> None:
    model = ScriptedModel(["SELECT 1"])
    case = _case()

    response = await run_text_to_sql(
        _bundle(
            model,
            RecordingExecutor(),
            seeds=("t_user_level",),
            documents=(_document("t_user_level", junction=False),),
            edges=(),
            fail_retrieval=True,
        ),
        question=case.question,
        database_id="ecommerce",
        variant="zero_shot",
    )

    assert response.status == "succeeded"
    assert response.schema_context is not None
    assert response.schema_context.seed_tables == []
    assert response.schema_context.expanded_tables == []
    assert ZERO_SHOT_SCHEMA in model.prompts[0]
    assert case.question in model.prompts[0]
    assert _GOLD not in model.prompts[0]
    assert "required_tables" not in model.prompts[0]
    assert "zero_shot" not in model.prompts[0]


async def test_schema_rag_does_not_expand_or_repair() -> None:
    documents = (
        _document("t_user", junction=False),
        _document("t_region", junction=False),
        _document("t_user_region_map", junction=True),
    )
    edges = (
        _edge("t_user_region_map", "t_user"),
        _edge("t_user_region_map", "t_region"),
    )
    model = ScriptedModel(["INSERT INTO t_user VALUES (1)", "SELECT 1"])
    executor = RecordingExecutor()

    response = await run_text_to_sql(
        _bundle(
            model,
            executor,
            seeds=("t_user", "t_region"),
            documents=documents,
            edges=edges,
        ),
        question="查询用户地区",
        database_id="ecommerce",
        variant="schema_rag",
    )

    assert response.status == "failed"
    assert response.attempts == 1
    assert executor.calls == []
    assert response.schema_context is not None
    assert response.schema_context.expanded_tables == []
    assert "t_user_region_map" not in model.prompts[0]
    assert "t_user" in model.prompts[0]


async def test_schema_graph_expands_without_repair() -> None:
    documents = (
        _document("t_user", junction=False),
        _document("t_region", junction=False),
        _document("t_user_region_map", junction=True),
    )
    edges = (
        _edge("t_user_region_map", "t_user"),
        _edge("t_user_region_map", "t_region"),
    )
    model = ScriptedModel(["NOT SQL AT ALL", "SELECT 1"])

    response = await run_text_to_sql(
        _bundle(
            model,
            RecordingExecutor(),
            seeds=("t_user", "t_region"),
            documents=documents,
            edges=edges,
        ),
        question="查询用户地区",
        database_id="ecommerce",
        variant="schema_graph",
    )

    assert response.status == "failed"
    assert response.attempts == 1
    assert response.schema_context is not None
    assert "t_user_region_map" in response.schema_context.expanded_tables


async def test_empty_schema_rag_seeds_fail_closed() -> None:
    response = await run_text_to_sql(
        _bundle(
            ScriptedModel(["SELECT 1"]),
            RecordingExecutor(),
            seeds=(),
            documents=(_document("t_user", junction=False),),
            edges=(),
        ),
        question="查询用户",
        database_id="ecommerce",
        variant="schema_rag",
    )

    assert response.status == "failed"
    assert response.error is not None
    assert response.error.category == "no_schema_seed"
    assert response.attempts == 0


async def test_junction_seed_is_a_leak_for_schema_rag() -> None:
    response = await run_text_to_sql(
        _bundle(
            ScriptedModel(["SELECT 1"]),
            RecordingExecutor(),
            seeds=("t_user_region_map",),
            documents=(_document("t_user_region_map", junction=True),),
            edges=(),
        ),
        question="查询地区映射",
        database_id="ecommerce",
        variant="schema_rag",
    )

    assert response.error is not None
    assert response.error.category == "junction_seed_leak"


def test_junction_recall_ignores_groups_without_expansion_and_leaks() -> None:
    case = _case()

    assert junction_recall_for_case(case, "zero_shot", (), ("t_user_region_map",)) == (None, ())
    assert junction_recall_for_case(case, "schema_rag", (), ("t_user_region_map",)) == (None, ())
    recall, leaked = junction_recall_for_case(
        case,
        "schema_graph",
        ("t_user_region_map",),
        (),
    )
    assert recall is None
    assert leaked == ("t_user_region_map",)
    assert junction_recall_for_case(case, "schema_graph", (), ("t_user_region_map",)) == (1.0, ())


def test_percentile_uses_linear_interpolation() -> None:
    assert percentile([1, 2, 3, 4, 5], 0.95) == 4.8
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([], 0.5) is None


def test_baseline_counts_only_non_junction_documents() -> None:
    counter = EstimatedTokenCounter()
    entity = _document("t_user", junction=False)
    junction = _document("t_user_region_map", junction=True)

    assert baseline_schema_tokens([entity, junction], counter) == baseline_schema_tokens(
        [entity],
        counter,
    )


def test_summary_keeps_targets_and_does_not_pad_a_partial_run() -> None:
    records = [
        _result(
            "custom_basic_001",
            "schema_graph",
            passed=True,
            ex=1,
            difficulty="basic",
            junction_recall=1.0,
            schema_tokens=100,
        ),
        _result(
            "custom_medium_001",
            "schema_graph",
            passed=False,
            ex=0,
            difficulty="medium",
            junction_recall=None,
            leaked_junctions=("t_order_coupon_rel",),
            schema_tokens=4000,
        ),
        _result("custom_basic_001", "self_healing", passed=True, ex=1, attempts=1),
        _result("custom_medium_001", "self_healing", passed=True, ex=1, attempts=2),
        _result("custom_complex_001", "self_healing", passed=False, ex=0, attempts=4),
    ]

    summary = build_summary(
        records,
        case_ids=["custom_basic_001", "custom_medium_001", "custom_complex_001"],
        git_commit="abc1234",
        database_snapshot="digest",
        model="scripted",
        started_at="2026-10-04T15:12:00Z",
        baseline_tokens=1000,
    )
    measured = summary["measured"]
    assert isinstance(measured, dict)
    accuracy = measured["execution_accuracy"]
    assert isinstance(accuracy, dict)
    graph = accuracy["schema_graph"]
    assert isinstance(graph, dict)
    assert graph["overall"] == 0.5
    assert graph["basic"] == 1.0
    assert graph["medium"] == 0.0
    assert graph["denominator"] == 2
    assert measured["complete"] is False
    recall = measured["junction_recall"]
    assert isinstance(recall, dict)
    assert recall["rate"] == 1.0
    assert recall["denominator"] == 1
    assert recall["excluded_leaks"] == ["custom_medium_001"]
    recovery = measured["recovery_at_3"]
    assert isinstance(recovery, dict)
    assert recovery["excluded_first_attempt"] == 1
    assert recovery["recovered"] == 1
    assert recovery["failed"] == 1
    assert recovery["rate"] == 0.5
    tokens = measured["schema_tokens"]
    assert isinstance(tokens, dict)
    assert tokens["baseline"] == 1000
    assert tokens["over_3500"] == 1
    assert tokens["count"] == 2
    assert measured["planner_cost_drop"] is None
    assert summary["target"] == TARGETS
    summary_target = summary["target"]
    assert isinstance(summary_target, dict)
    summary_target["execution_accuracy"] = 1
    assert TARGETS["execution_accuracy"] == 0.83


def test_report_directory_is_immutable(tmp_path: Path) -> None:
    records = [_result("custom_basic_001", "zero_shot", passed=True, ex=1)]
    summary = build_summary(
        records,
        case_ids=["custom_basic_001"],
        git_commit="abc1234",
        database_snapshot="digest",
        model="scripted",
        started_at="2026-10-04T15:12:00Z",
        baseline_tokens=None,
    )
    first = write_ablation_report(
        tmp_path,
        stamp="20261004T151200Z",
        commit="abc1234",
        summary=summary,
        records=records,
    )
    original = (first / "summary.json").read_bytes()
    loaded = json.loads(original)
    assert loaded["target"] == TARGETS
    assert loaded["model"] == "scripted"
    assert loaded["case_files"] == ["cases/custom_basic_001__zero_shot.json"]
    assert (first / "cases" / "custom_basic_001__zero_shot.json").is_file()

    second = write_ablation_report(
        tmp_path,
        stamp="20261004T151201Z",
        commit="abc1234",
        summary=summary,
        records=records,
    )
    assert second != first
    assert (first / "summary.json").read_bytes() == original

    try:
        write_ablation_report(
            tmp_path,
            stamp="20261004T151200Z",
            commit="abc1234",
            summary=summary,
            records=records,
        )
    except FileExistsError:
        collided = True
    else:
        collided = False
    assert collided
    assert (first / "summary.json").read_bytes() == original


async def test_scripted_runner_scores_without_putting_gold_in_the_prompt() -> None:
    case = _case().model_copy(update={"required_junctions": []})
    model = ScriptedModel(["SELECT 1"])

    async def execute(sql: str, *, max_rows: int) -> ExecutionSuccess:
        del sql
        assert max_rows == 10_000
        return ExecutionSuccess(
            columns=(("value", "int4"),),
            rows=((1,),),
            row_count=1,
            truncated=False,
            execution_time_ms=0.1,
        )

    result = await evaluate_case(
        case,
        _bundle(
            model,
            RecordingExecutor(),
            seeds=(),
            documents=(),
            edges=(),
            fail_retrieval=True,
        ),
        variant="zero_shot",
        execute=execute,
    )

    assert result.ex == 1
    assert result.passed is True
    assert result.junction_recall is None
    assert result.prediction.sql == "SELECT 1"
    assert result.prediction.parse_error is None
    assert _GOLD not in model.prompts[0]
    assert case.question in model.prompts[0]
    assert _GOLD not in str(result.prediction.as_json())


async def test_rejected_prediction_is_recorded_without_changing_the_response() -> None:
    case = _case().model_copy(update={"required_junctions": []})
    sql = "INSERT INTO t_user VALUES (1)"

    result = await evaluate_case(
        case,
        _bundle(
            ScriptedModel([sql]),
            RecordingExecutor(),
            seeds=(),
            documents=(),
            edges=(),
            fail_retrieval=True,
        ),
        variant="zero_shot",
    )

    assert result.ex == 0
    assert result.error_category == "not_read_only"
    assert result.prediction.sql == sql
    assert result.prediction.referenced_tables == ("t_user",)
    assert result.prediction.parse_error == "不是只读查询"
