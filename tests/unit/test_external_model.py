"""外部模型评测先生成，再单独执行 Gold。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from app.agents.text_to_sql.workflow import TextToSqlInspection
from app.evaluation.external_model import (
    ecommerce_rule_hits,
    evaluate_predictions,
    render_model_diagnosis,
    score_prediction,
    select_sample,
    write_model_diagnosis,
)
from app.evaluation.external_report import (
    ModelCaseTrace,
    build_external_model_summary,
    write_external_model_report,
    write_external_report,
)
from app.evaluation.sql_shape import describe_sql
from app.sandbox.errors import ExecutionError
from app.sandbox.execute import ExecutionSuccess
from app.schemas.benchmark import BenchmarkCase
from app.schemas.text_to_sql import ApiError, SchemaContextView, TextToSqlResponse


def test_sample_limits_each_database_without_taking_the_whole_file() -> None:
    cases = [
        _case("bird_0001", "california_schools"),
        _case("bird_0002", "california_schools"),
        _case("bird_0003", "financial"),
    ]

    chosen = select_sample(cases, per_database=1, limit=None)

    assert [case.id for case in chosen] == ["bird_0001", "bird_0003"]
    with pytest.raises(ValueError, match="limit or per_database"):
        select_sample(cases, per_database=None, limit=None)


def test_ecommerce_markers_ignore_words_inside_the_question() -> None:
    hits = ecommerce_rule_hits(
        prompt="问题：\n答案契约出现在问句里\n\nSQLite 数据库 california_schools",
        question="答案契约出现在问句里",
        categories=(),
    )
    assert hits == ()
    triggered = ecommerce_rule_hits(
        prompt="问题：\nHow many\n\n答案契约：\nfact_key: detail_id",
        question="How many",
        categories=("missing_fact_dedup",),
    )
    assert "答案契约" in triggered
    assert "missing_fact_dedup" in triggered


async def test_scoring_executes_gold_only_after_the_prediction() -> None:
    case = _case("bird_0001", "california_schools")
    calls: list[str] = []

    async def execute(sql: str) -> ExecutionSuccess:
        calls.append(sql)
        return ExecutionSuccess(
            columns=(("total", "integer"),),
            rows=((1,),),
            row_count=1,
            truncated=False,
            execution_time_ms=1,
        )

    trace = await score_prediction(
        case,
        _inspection("SELECT 1 AS total", seeds=("schools",)),
        execute=execute,
        catalog_tables=("schools",),
    )

    assert calls == ["SELECT 1 AS total", case.gold_sql]
    assert trace.primary_class == "matched"
    assert trace.ex == 1
    assert trace.ecommerce_rule_hits == ()
    assert trace.leaked_tables == ()


async def test_scoring_matches_ex_when_sql_runs_despite_failed_workflow_status() -> None:
    case = _case("bird_0001", "california_schools")

    async def execute(sql: str) -> ExecutionSuccess:
        return ExecutionSuccess(
            columns=(("total", "integer"),),
            rows=((1,),),
            row_count=1,
            truncated=False,
            execution_time_ms=1,
        )

    inspection = TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req",
            status="failed",
            sql="SELECT 1 AS total",
            columns=[],
            rows=[],
            attempts=2,
            error=ApiError(category="no_progress", message="熔断", retryable=False),
            schema_context=SchemaContextView(
                seed_tables=["schools"],
                expanded_tables=[],
                token_count=8,
                truncated=False,
            ),
        ),
        generated_sql="SELECT 1 AS total",
        prompt="generic",
    )
    trace = await score_prediction(
        case,
        inspection,
        execute=execute,
        catalog_tables=("schools",),
    )
    assert trace.ex == 1
    assert trace.primary_class == "matched"


async def test_scoring_flags_a_seed_from_another_database_without_executing() -> None:
    case = _case("bird_0001", "california_schools")
    calls: list[str] = []

    async def execute(sql: str) -> ExecutionSuccess:
        calls.append(sql)
        raise AssertionError(sql)

    trace = await score_prediction(
        case,
        _inspection("SELECT 1", seeds=("t_order",)),
        execute=execute,
        catalog_tables=("schools",),
    )

    assert calls == []
    assert trace.leaked_tables == ("t_order",)
    assert trace.ex == 0
    assert trace.primary_class == "sql_error"


async def test_result_mismatch_is_not_called_a_sql_error() -> None:
    case = _case("bird_0001", "california_schools")

    async def execute(sql: str) -> ExecutionSuccess:
        rows = ((1,),) if sql == "SELECT 1 AS total" else ((2,),)
        return ExecutionSuccess(
            columns=(("total", "integer"),),
            rows=rows,
            row_count=1,
            truncated=False,
            execution_time_ms=1,
        )

    trace = await score_prediction(
        case,
        _inspection("SELECT 1 AS total", seeds=("schools",)),
        execute=execute,
        catalog_tables=("schools",),
    )

    assert trace.primary_class == "other_result_mismatch"
    assert trace.ex == 0
    assert trace.prediction["referenced_tables"] == []


async def test_failed_generation_does_not_execute_gold() -> None:
    case = _case("bird_0001", "california_schools")

    async def execute(sql: str) -> ExecutionSuccess | ExecutionError:
        if sql == case.gold_sql:
            raise AssertionError("gold must not execute when prediction fails")
        return ExecutionError(
            category="syntax_error",
            sqlstate=None,
            exception_type="ParseError",
            normalized_message="bad sql",
            retryable=True,
            error_hash="syntax",
        )

    inspection = TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req",
            status="failed",
            attempts=1,
            error=ApiError(category="syntax_error", message="SQL 无法解析", retryable=True),
        ),
        generated_sql="SELEC 1",
        prompt="SQLite 数据库 california_schools",
    )
    trace = await score_prediction(
        case,
        inspection,
        execute=execute,
        catalog_tables=("schools",),
    )

    assert trace.primary_class == "sql_error"
    assert trace.error_category == "syntax_error"
    assert trace.prediction["parse_error"] is not None


async def test_generic_evaluation_rejects_the_ecommerce_database() -> None:
    case = _case("bird_0001", "ecommerce")

    async def inspect_case(current: BenchmarkCase) -> TextToSqlInspection:
        raise AssertionError(current.gold_sql)

    async def execute_sql(current: BenchmarkCase, sql: str) -> ExecutionError:
        raise AssertionError((current.id, sql))

    with pytest.raises(ValueError, match="generic"):
        await evaluate_predictions(
            [case],
            inspect_case=inspect_case,
            execute_sql=execute_sql,
            catalog_for=lambda _database_id: (),
        )


def test_model_report_records_accuracy_and_diagnosis(tmp_path: Path) -> None:
    matched = _trace("bird_0001", "matched", 1)
    missed = _trace("bird_0002", "other_result_mismatch", 0)
    summary = build_external_model_summary(
        [matched, missed],
        source="bird",
        benchmark_version="bird-test",
        git_commit="abc1234",
        database_snapshot="snapshot",
        started_at="2026-10-05T00:00:00Z",
        model="deepseek-chat",
        prompt_version="text-to-sql-generic-v1",
        environment={"variant": "schema_graph", "sample": True},
    )
    directory = write_external_model_report(
        tmp_path,
        stamp="20261005T000000Z",
        commit="abc1234",
        summary=summary,
        traces=[matched, missed],
    )
    text = render_model_diagnosis(
        summary,
        [matched.as_json(), missed.as_json()],
    )
    diagnosis = write_model_diagnosis(directory)

    execution = summary["model_execution"]
    assert isinstance(execution, dict)
    assert execution["executable_rate"] == 1.0
    assert execution["dialect_error_rate"] == 0.0
    assert summary["measured"] == {"execution_accuracy": 0.5}
    assert summary["model"] == "deepseek-chat"
    assert summary["official_tpcds_result"] is False
    assert "bird_0002" in text
    assert "other_result_mismatch" in diagnosis.read_text(encoding="utf-8")
    assert json.loads((directory / "summary.json").read_text(encoding="utf-8"))["model"] == (
        "deepseek-chat"
    )


def test_diagnosis_truncates_a_very_long_prediction() -> None:
    text = render_model_diagnosis(
        {
            "benchmark_source": "bird",
            "model": "deepseek-chat",
            "prompt_version": "text-to-sql-generic-v1",
            "measured": {"execution_accuracy": 0.0},
            "model_execution": {
                "matched": 0,
                "sql_error": 1,
                "other_result_mismatch": 0,
                "ecommerce_rule_cases": 0,
                "cross_database_leaks": 0,
            },
        },
        [
            {
                "case_id": "bird_0001",
                "database_id": "california_schools",
                "primary_class": "sql_error",
                "error_category": "syntax_error",
                "seed_tables": ["schools"],
                "ecommerce_rule_hits": [],
                "leaked_tables": [],
                "prediction": {"sql": "A" * 3000, "referenced_tables": []},
            }
        ],
    )

    assert "-- truncated" in text
    assert "A" * 3000 not in text


def test_model_report_rejects_an_empty_model_and_custom_targets(tmp_path: Path) -> None:
    trace = _trace("bird_0001", "matched", 1)
    summary = build_external_model_summary(
        [trace],
        source="bird",
        benchmark_version="bird-test",
        git_commit="abc1234",
        database_snapshot="snapshot",
        started_at="2026-10-05T00:00:00Z",
        model="deepseek-chat",
        prompt_version="text-to-sql-generic-v1",
        environment={},
    )
    summary["model"] = None
    with pytest.raises(ValueError, match="model"):
        write_external_model_report(
            tmp_path,
            stamp="20261005T000100Z",
            commit="abc1234",
            summary=summary,
            traces=[trace],
        )
    summary["model"] = "deepseek-chat"
    execution = summary["model_execution"]
    assert isinstance(execution, dict)
    execution["executable_rate"] = 0.86
    write_external_model_report(
        tmp_path,
        stamp="20261005T000150Z",
        commit="abc1234",
        summary=summary,
        traces=[trace],
    )
    summary["environment"] = {"note": "0.83"}
    with pytest.raises(ValueError, match="custom target"):
        write_external_model_report(
            tmp_path,
            stamp="20261005T000200Z",
            commit="abc1234",
            summary=summary,
            traces=[trace],
        )


def test_gold_report_still_rejects_a_measured_accuracy(tmp_path: Path) -> None:
    from app.evaluation.external_report import GoldTrace, build_external_summary

    case = _case("bird_0001", "california_schools")
    trace = GoldTrace(case.id, "ok", 1, "abc", None)
    summary = build_external_summary(
        [case],
        [trace],
        source="bird",
        benchmark_version="bird-test",
        git_commit="abc1234",
        database_snapshot="snapshot",
        started_at="2026-10-05T00:00:00Z",
        environment={},
    )
    measured = summary["measured"]
    assert isinstance(measured, dict)
    measured["execution_accuracy"] = 1.0
    with pytest.raises(ValueError, match="empty"):
        write_external_report(
            tmp_path,
            stamp="20261005T000300Z",
            commit="abc1234",
            summary=summary,
            traces=[trace],
        )


def _case(case_id: str, database_id: str) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        source="bird",
        source_version="v1",
        database_id=database_id,
        difficulty="complex",
        dialect="sqlite",
        question="How many schools are there?",
        gold_sql="SELECT COUNT(*) AS total FROM schools",
        required_tables=["schools"],
        required_junctions=[],
        order_sensitive=False,
        numeric_tolerance=None,
        expected_columns=["total"],
        anchor_date=date(2026, 10, 1),
        tags=["aggregation"],
    )


def _inspection(sql: str, *, seeds: tuple[str, ...]) -> TextToSqlInspection:
    return TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req",
            status="succeeded",
            sql=sql,
            columns=["total"],
            rows=[[1]],
            attempts=1,
            schema_context=SchemaContextView(
                seed_tables=list(seeds),
                expanded_tables=[],
                token_count=8,
                truncated=False,
            ),
        ),
        generated_sql=sql,
        prompt="问题：\nHow many schools are there?\n\nSQLite 数据库 california_schools",
    )


def _trace(case_id: str, primary_class: str, ex: int) -> ModelCaseTrace:
    return ModelCaseTrace(
        case_id=case_id,
        database_id="california_schools",
        primary_class=primary_class,
        ex=ex,
        error_category=None,
        attempts=1,
        seed_tables=("schools",),
        expanded_tables=(),
        leaked_tables=(),
        ecommerce_rule_hits=(),
        prediction=describe_sql("SELECT 1 AS total", dialect="sqlite").as_json(),
    )
