"""消融变体、召回、token 和不可覆盖的报告。不下载模型。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import pytest
from app.agents.text_to_sql.workflow import (
    ZERO_SHOT_SCHEMA,
    ServiceBundle,
    run_text_to_sql,
)
from app.evaluation.ablation import (
    TARGETS,
    CaseResult,
    _paired_recovery,
    baseline_schema_tokens,
    build_summary,
    evaluate_case,
    junction_recall_for_case,
    percentile,
    required_table_recall_for_case,
    write_ablation_report,
)
from app.evaluation.badcase import classify_badcase
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
        "required_table_recall": None,
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
    assert "join t_user_region_map.id = t_user.id" in model.prompts[0]
    assert "join t_user_region_map.id = t_region.id" in model.prompts[0]


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


def test_required_table_recall_counts_seed_overlap_only() -> None:
    case = _case()

    assert required_table_recall_for_case(case, "zero_shot", ("t_user_level",)) is None
    assert required_table_recall_for_case(case, "schema_rag", ("t_user_level",)) == 1.0
    assert required_table_recall_for_case(case, "schema_graph", ("t_user",)) == 0.0
    assert required_table_recall_for_case(case, "self_healing", ("t_user_level", "t_coupon")) == 1.0


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
            required_table_recall=1.0,
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
            required_table_recall=0.0,
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
    table_recall = measured["required_table_recall"]
    assert isinstance(table_recall, dict)
    assert table_recall["variant"] == "schema_graph"
    assert table_recall["rate"] == 0.5
    assert table_recall["denominator"] == 2
    recovery = measured["recovery_at_3"]
    assert isinstance(recovery, dict)
    # §11.7 P2：Recovery@3 不把首轮即过的 case 算进分母
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


def test_ablation_report_json_includes_repair_trace_when_attempts_gt_one(tmp_path: Path) -> None:
    """§11.5 P2：自建 attempts>1 的 case JSON 须持久化 repair_trace 结构化数组。"""
    trace = (
        ("1", "not_read_only", "sha256:s1", "sha256:q1"),
        ("2", "accepted", "", "sha256:q2"),
    )
    records = [
        _result(
            "custom_basic_001",
            "self_healing",
            attempts=2,
            passed=True,
            ex=1,
            repair_trace=trace,
        )
    ]
    summary = build_summary(
        records,
        case_ids=["custom_basic_001"],
        git_commit="abc1234",
        database_snapshot="digest",
        model="scripted",
        started_at="2026-10-04T15:12:00Z",
        baseline_tokens=None,
    )
    run_dir = write_ablation_report(
        tmp_path,
        stamp="20261004T151200Z",
        commit="abc1234",
        summary=summary,
        records=records,
    )
    payload = json.loads(
        (run_dir / "cases" / "custom_basic_001__self_healing.json").read_text(encoding="utf-8")
    )
    assert payload["attempts"] == 2
    assert len(payload["repair_trace"]) == 2
    assert payload["repair_trace"][-1]["category"] == "accepted"


def test_write_ablation_report_rejects_self_healing_without_repair_trace(tmp_path: Path) -> None:
    records = [
        _result(
            "custom_basic_001",
            "self_healing",
            attempts=2,
            passed=False,
            ex=0,
            repair_trace=(),
        )
    ]
    summary = build_summary(
        records,
        case_ids=["custom_basic_001"],
        git_commit="abc1234",
        database_snapshot="digest",
        model="scripted",
        started_at="2026-10-04T15:12:00Z",
        baseline_tokens=None,
    )
    with pytest.raises(RuntimeError, match="repair_trace is empty"):
        write_ablation_report(
            tmp_path,
            stamp="20261004T151200Z",
            commit="abc1234",
            summary=summary,
            records=records,
        )


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
    assert result.required_table_recall is None
    assert result.as_json()["required_table_recall"] is None
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
    assert result.primary_class == "sql_error"
    assert result.repair_trace[0][1] == "not_read_only"


async def test_evaluate_case_self_healing_persists_repair_trace_when_attempts_gt_one() -> None:
    """§11.5 P2：evaluate_case 自愈多轮须写入 CaseResult.repair_trace（非仅手填 fixture）。"""
    case = _case().model_copy(update={"required_junctions": []})
    result = await evaluate_case(
        case,
        _bundle(
            ScriptedModel(["INSERT INTO t_user_level VALUES (1)"]),
            RecordingExecutor(),
            seeds=("t_user_level",),
            documents=(_document("t_user_level", junction=False),),
            edges=(),
        ),
        variant="self_healing",
    )

    assert result.attempts >= 2
    assert len(result.repair_trace) >= 1
    payload = result.as_json()
    assert payload["attempts"] >= 2
    assert len(payload["repair_trace"]) >= 1
    assert dict(result.symptoms).get("repair_trace", "")
    assert result.error_category == "no_progress"


def test_validate_p2_repair_traces_accepts_zero_shot_skeleton_for_all_custom_cases() -> None:
    """§11.5 P2：132 条自建用例 zero_shot/首轮 self_healing 须可通过 write 前校验。"""
    from app.evaluation.ablation import validate_p2_repair_traces
    from app.evaluation.custom_cases import load_custom_cases

    cases = load_custom_cases()
    assert len(cases) == 132
    records = [
        _result(
            case.id,
            "zero_shot",
            passed=True,
            ex=1,
            difficulty=case.difficulty,
        )
        for case in cases
    ]
    validate_p2_repair_traces(records)
    records.append(
        _result(
            "custom_basic_001",
            "self_healing",
            attempts=2,
            repair_trace=(("1", "not_read_only", "sha256:s1", "sha256:q1"),),
        )
    )
    validate_p2_repair_traces(records)


def test_write_ablation_report_accepts_132_custom_zero_shot_skeleton(tmp_path: Path) -> None:
    """§11.5 P2：132 条 zero_shot 骨架须能完整写入 ablation run（validate + 落盘）。"""
    from app.evaluation.custom_cases import load_custom_cases

    cases = load_custom_cases()
    assert len(cases) == 132
    records = [
        _result(
            case.id,
            "zero_shot",
            passed=True,
            ex=1,
            difficulty=case.difficulty,
        )
        for case in cases
    ]
    summary = build_summary(
        records,
        case_ids=[case.id for case in cases],
        git_commit="abc1234",
        database_snapshot="digest",
        model="scripted",
        started_at="2026-10-07T14:05:00Z",
        baseline_tokens=None,
    )
    run_dir = write_ablation_report(
        tmp_path,
        stamp="20261007T140500Z",
        commit="abc1234",
        summary=summary,
        records=records,
    )
    case_files = list((run_dir / "cases").glob("*.json"))
    assert len(case_files) == 132


def test_assert_p2_repair_trace_requires_trace_for_self_healing_multattempt() -> None:
    from app.evaluation.ablation import _assert_p2_repair_trace

    _assert_p2_repair_trace(
        variant="zero_shot",
        attempts=3,
        trace=(),
        case_id="custom_basic_001",
    )
    _assert_p2_repair_trace(
        variant="self_healing",
        attempts=1,
        trace=(),
        case_id="custom_basic_001",
    )
    with pytest.raises(RuntimeError, match="repair_trace is empty"):
        _assert_p2_repair_trace(
            variant="self_healing",
            attempts=2,
            trace=(),
            case_id="custom_medium_001",
        )


def test_badcase_classes_sum_to_the_denominator_and_keep_symptoms() -> None:
    gold = (
        "SELECT ul.level_name, COUNT(*) AS user_count "
        "FROM t_user AS u JOIN t_user_level AS ul ON u.user_level_id = ul.level_id "
        "GROUP BY ul.level_name"
    )
    predicted = "SELECT COUNT(*) AS user_count FROM t_user"
    primary, symptoms = classify_badcase(
        question="统计每个会员等级的用户数量",
        gold_sql=gold,
        predicted_sql=predicted,
        required_tables=("t_user", "t_user_level"),
        error_category=None,
        ex=0,
    )
    assert primary == "missing_required_table"
    values = dict(symptoms)
    assert "level_name" in values["missing_projections"]
    assert values["gold_group_by"]
    assert values["predicted_group_by"] == ""

    grain, grain_symptoms = classify_badcase(
        question="统计每个会员等级的用户数量",
        gold_sql=gold,
        predicted_sql=predicted,
        required_tables=(),
        error_category=None,
        ex=0,
        repair_trace=(("2", "aggregation_grain", "sha256:abc", "sha256:sql"),),
    )
    assert grain == "grouping_grain"
    ordered, order_symptoms = classify_badcase(
        question="按等级编号升序查询VIP2会员等级的名称和折扣率",
        gold_sql=(
            "SELECT level_id, level_name, discount_rate FROM t_user_level WHERE level_name = 'VIP2'"
        ),
        predicted_sql=(
            "SELECT level_name, discount_rate, level_id FROM t_user_level WHERE level_name = 'VIP2'"
        ),
        required_tables=(),
        error_category=None,
        ex=0,
    )
    assert ordered == "response_shape"
    assert "level_id" in dict(order_symptoms)["projection_order"]
    _plain_with, with_symptoms = classify_badcase(
        question="统计订单",
        gold_sql="SELECT order_id FROM t_order",
        predicted_sql="WITH paid AS (SELECT order_id FROM t_order) SELECT order_id FROM paid",
        required_tables=(),
        error_category=None,
        ex=0,
    )
    assert dict(with_symptoms)["recursive_cte"] == ""
    assert "level_name" in dict(grain_symptoms)["missing_projections"]
    assert "aggregation_grain" in dict(grain_symptoms)["repair_trace"]
    fact, fact_symptoms = classify_badcase(
        question="统计商品数量",
        gold_sql=(
            "SELECT DISTINCT od.detail_id, od.quantity FROM t_order_detail AS od "
            "JOIN t_user_region_map AS urm ON od.order_id = urm.user_id"
        ),
        predicted_sql=(
            "SELECT SUM(od.quantity) AS total_quantity FROM t_order_detail AS od "
            "JOIN t_user_region_map AS urm ON od.order_id = urm.user_id"
        ),
        required_tables=(),
        error_category=None,
        ex=0,
    )
    assert fact == "fact_grain"
    assert dict(fact_symptoms)["missing_dedup_key"]
    alias, alias_symptoms = classify_badcase(
        question="统计护肤品类的在售商品数量",
        gold_sql="SELECT category_name FROM t_category WHERE category_name = '护肤'",
        predicted_sql="SELECT category_name FROM t_category WHERE category_name = '护肤品'",
        required_tables=(),
        error_category=None,
        ex=0,
    )
    assert alias == "filter_scope"
    assert "护肤" in dict(alias_symptoms)["missing_filter_literals"]

    matched, _symptoms = classify_badcase(
        question="统计每个会员等级的用户数量",
        gold_sql=gold,
        predicted_sql=gold,
        required_tables=(),
        error_category=None,
        ex=1,
    )
    assert matched == "matched"


def test_paired_recovery_counts_repairs_of_the_shared_sql() -> None:
    def record(case_id: str, variant: str, ex: int, attempts: int) -> CaseResult:
        return CaseResult(
            case_id=case_id,
            variant=variant,
            passed=ex == 1,
            attempts=attempts,
            seed_tables=(),
            expanded_tables=(),
            junction_recall=None,
            required_table_recall=None,
            schema_tokens=0,
            latency_ms=0,
            error_category=None,
            difficulty="complex",
            ex=ex,
            leaked_junctions=(),
        )

    summary = _paired_recovery(
        [
            record("kept", "schema_graph", 1, 1),
            record("fixed", "schema_graph", 0, 1),
            record("open", "schema_graph", 0, 1),
        ],
        [
            record("kept", "self_healing", 1, 2),
            record("fixed", "self_healing", 1, 2),
            record("open", "self_healing", 0, 1),
        ],
    )
    assert summary["paired_initial_failures"] == 2
    assert summary["paired_recovered"] == 1
    assert summary["paired_unrecovered"] == 1
    assert summary["paired_recovery_rate"] == 0.5
    assert summary["unnecessary_repair_triggers"] == 1
    assert summary["repair_trigger_precision"] == 0.5


def test_badcase_summary_uses_primary_classes() -> None:
    records = [
        _result("custom_basic_001", "schema_graph", passed=True, ex=1),
        _result("custom_basic_002", "schema_graph", passed=False, ex=0),
    ]
    records[0] = _copy_class(records[0], "matched")
    records[1] = _copy_class(records[1], "grouping_grain")
    summary = build_summary(
        records,
        case_ids=["custom_basic_001", "custom_basic_002"],
        git_commit="abc1234",
        database_snapshot="digest",
        model="scripted",
        started_at="2026-10-05T00:00:00Z",
        baseline_tokens=10,
    )
    measured = summary["measured"]
    assert isinstance(measured, dict)
    badcase = measured["badcase"]
    assert isinstance(badcase, dict)
    graph = badcase["schema_graph"]
    assert isinstance(graph, dict)
    assert graph["primary_total"] == graph["denominator"]
    assert graph["denominator"] == 2
    matrix = measured["transition_matrix"]
    assert isinstance(matrix, dict)
    for item in matrix.values():
        assert isinstance(item, dict)
        assert item["total"] == item["denominator"]


def _copy_class(record: CaseResult, primary: str) -> CaseResult:
    return CaseResult(
        case_id=record.case_id,
        variant=record.variant,
        passed=record.passed,
        attempts=record.attempts,
        seed_tables=record.seed_tables,
        expanded_tables=record.expanded_tables,
        junction_recall=record.junction_recall,
        required_table_recall=record.required_table_recall,
        schema_tokens=record.schema_tokens,
        latency_ms=record.latency_ms,
        error_category=record.error_category,
        difficulty=record.difficulty,
        ex=record.ex,
        leaked_junctions=record.leaked_junctions,
        prediction=record.prediction,
        primary_class=primary,
    )
