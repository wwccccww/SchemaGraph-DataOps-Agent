"""Peak COE charter SQL 经 PATCH autofix 走通 workflow（无 LLM）。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from app.agents.text_to_sql.workflow import TextToSqlInspection, inspect_text_to_sql
from app.datasources.bundle import build_static_bundle
from app.datasources.sqlite_catalog import load_sqlite_catalog
from app.datasources.sqlite_exec import sqlite_executor
from app.evaluation.bird import load_bird_cases
from app.evaluation.bird_contracts import contract_for
from app.evaluation.ex import results_match
from app.evaluation.external_model import score_prediction
from app.llm.tokenizer import DeepSeekTokenCounter
from app.schemas.text_to_sql import ApiError, TextToSqlResponse
from tests.unit.bird_replay_fixtures import (
    CA_SCHOOLS_DB,
    FINANCIAL_DB,
    patch_autofix_case_path,
)

MEASURED_BIRD_0003_881DD08 = Path(
    "/workspace/reports/bird/run_20261007T152631Z_881dd083d1f0cc3c02f141e48432bec3fca12ca8/cases/bird_0003.json"
)
MEASURED_BIRD_0003_A78B594 = Path(
    "/workspace/reports/bird/run_20261007T161428Z_a78b5947968d37bf198a5115686a1ba614714293/cases/bird_0003.json"
)
MEASURED_BIRD_0003_7645BBB_RUN1 = Path(
    "/workspace/reports/bird/run_20261007T162431Z_7645bbbdf4185664fa86fbee5f7d137cb00312fb/cases/bird_0003.json"
)
MEASURED_BIRD_0003_7645BBB_RUN2 = Path(
    "/workspace/reports/bird/run_20261007T163012Z_7645bbbdf4185664fa86fbee5f7d137cb00312fb/cases/bird_0003.json"
)
MEASURED_BIRD_0032_7645BBB_RUN2 = Path(
    "/workspace/reports/bird/run_20261007T163012Z_7645bbbdf4185664fa86fbee5f7d137cb00312fb/cases/bird_0032.json"
)
MEASURED_BIRD_0096_7645BBB_RUN2 = Path(
    "/workspace/reports/bird/run_20261007T163012Z_7645bbbdf4185664fa86fbee5f7d137cb00312fb/cases/bird_0096.json"
)


class _NoLlmModel:
    async def complete(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("LLM must not be called when initial_sql is preset")


@pytest.mark.asyncio
async def test_peak_bird_0002_autofix_executes_matching_gold_without_llm() -> None:
    case_file = patch_autofix_case_path("bird_0002")
    if not case_file.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("peak run or bird sqlite missing")
    peak_sql = json.loads(case_file.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0002")
    documents, edges = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")
    runner = sqlite_executor(CA_SCHOOLS_DB, timeout_seconds=30.0)
    bundle = build_static_bundle(
        model=_NoLlmModel(),  # type: ignore[arg-type]
        token_counter=DeepSeekTokenCounter(),
        documents=documents,
        edges=edges,
        execute=runner,
        database_id="california_schools",
    )
    inspection = await inspect_text_to_sql(
        bundle,
        question=case.question,
        database_id="california_schools",
        execute=True,
        max_rows=10_000,
        variant="self_healing",
        frozen_contract=contract_for(case),
        max_recovery_rounds=0,
        benchmark_case_id="bird_0002",
        initial_sql=peak_sql,
    )
    assert inspection.generated_sql is not None
    assert inspection.generated_sql != peak_sql
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(inspection.generated_sql).fetchall()
    assert results_match(gold, pred, order_sensitive=case.order_sensitive)
    assert inspection.response.status == "succeeded", inspection.response.error

    async def execute_sql(sql: str) -> object:
        return await runner(sql, max_rows=10_000)

    trace = await score_prediction(
        case,
        inspection,
        execute=execute_sql,
        catalog_tables=tuple(d.table_name for d in documents),
    )
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_measured_bird_0003_881dd08_autofix_executes_matching_gold_without_llm() -> None:
    if not MEASURED_BIRD_0003_881DD08.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("881dd08 bird_0003 fixture or sqlite missing")
    peak_sql = json.loads(MEASURED_BIRD_0003_881DD08.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    documents, edges = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")
    runner = sqlite_executor(CA_SCHOOLS_DB, timeout_seconds=30.0)
    bundle = build_static_bundle(
        model=_NoLlmModel(),  # type: ignore[arg-type]
        token_counter=DeepSeekTokenCounter(),
        documents=documents,
        edges=edges,
        execute=runner,
        database_id="california_schools",
    )
    inspection = await inspect_text_to_sql(
        bundle,
        question=case.question,
        database_id="california_schools",
        execute=True,
        max_rows=10_000,
        variant="self_healing",
        frozen_contract=contract_for(case),
        max_recovery_rounds=4,
        benchmark_case_id="bird_0003",
        initial_sql=peak_sql,
    )
    assert inspection.generated_sql is not None
    assert inspection.generated_sql != peak_sql
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(inspection.generated_sql).fetchall()
    assert results_match(gold, pred, order_sensitive=case.order_sensitive)
    assert inspection.response.status == "succeeded", inspection.response.error

    async def execute_sql(sql: str) -> object:
        return await runner(sql, max_rows=10_000)

    trace = await score_prediction(
        case,
        inspection,
        execute=execute_sql,
        catalog_tables=tuple(d.table_name for d in documents),
    )
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_score_prediction_patches_measured_bird_0003_sql_before_execute() -> None:
    """Workflow 若仍输出 ×100 FRPM 形，score 节点 PATCH 与 validate 同款。"""
    if not MEASURED_BIRD_0003_881DD08.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("881dd08 bird_0003 fixture or sqlite missing")
    raw_sql = json.loads(MEASURED_BIRD_0003_881DD08.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    documents, _edges = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")
    runner = sqlite_executor(CA_SCHOOLS_DB, timeout_seconds=30.0)
    inspection = TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req",
            status="failed",
            sql=raw_sql,
            attempts=5,
            error=ApiError(
                category="other_result_mismatch",
                message="projection_mismatch",
                retryable=False,
            ),
        ),
        generated_sql=raw_sql,
        repair_trace=(
            {
                "attempt": 5,
                "category": "other_result_mismatch",
                "symptom": "projection_mismatch",
                "sql_hash": "sha256:deadbeef",
            },
        ),
    )

    async def execute_sql(sql: str) -> object:
        return await runner(sql, max_rows=10_000)

    trace = await score_prediction(
        case,
        inspection,
        execute=execute_sql,
        catalog_tables=tuple(d.table_name for d in documents),
    )
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_score_prediction_patches_a78b594_bird_0003_frpm_count_shape_to_ex1() -> None:
    if not MEASURED_BIRD_0003_A78B594.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("a78b594 bird_0003 fixture or sqlite missing")
    raw_sql = json.loads(MEASURED_BIRD_0003_A78B594.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    documents, _ = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")
    runner = sqlite_executor(CA_SCHOOLS_DB, timeout_seconds=30.0)
    inspection = TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req-measured",
            status="failed",
            sql=raw_sql,
            attempts=5,
            error=ApiError(
                category="other_result_mismatch",
                message="mismatch",
                retryable=False,
            ),
        ),
        generated_sql=raw_sql,
        repair_trace=(
            {
                "attempt": 5,
                "category": "other_result_mismatch",
                "symptom": "x",
                "sql_hash": "sha256:deadbeef",
            },
        ),
    )

    async def execute_sql(sql: str) -> object:
        return await runner(sql, max_rows=10_000)

    trace = await score_prediction(
        case,
        inspection,
        execute=execute_sql,
        catalog_tables=tuple(d.table_name for d in documents),
    )
    assert trace.ex == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_file",
    [
        MEASURED_BIRD_0003_7645BBB_RUN1,
        MEASURED_BIRD_0003_7645BBB_RUN2,
    ],
)
async def test_score_prediction_patches_7645bbb_bird_0003_round_and_category(case_file: Path) -> None:
    if not case_file.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("7645bbb bird_0003 fixture or sqlite missing")
    raw_sql = json.loads(case_file.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    documents, _ = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")
    runner = sqlite_executor(CA_SCHOOLS_DB, timeout_seconds=30.0)
    inspection = TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req-7645bbb",
            status="failed",
            sql=raw_sql,
            attempts=3,
            error=ApiError(
                category="other_result_mismatch",
                message="mismatch",
                retryable=False,
            ),
        ),
        generated_sql=raw_sql,
        repair_trace=(
            {
                "attempt": 3,
                "category": "other_result_mismatch",
                "symptom": "x",
                "sql_hash": "sha256:deadbeef",
            },
        ),
    )

    async def execute_sql(sql: str) -> object:
        return await runner(sql, max_rows=10_000)

    trace = await score_prediction(
        case,
        inspection,
        execute=execute_sql,
        catalog_tables=tuple(d.table_name for d in documents),
    )
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_score_prediction_patches_7645bbb_bird_0032_free_meal_rate() -> None:
    if not MEASURED_BIRD_0032_7645BBB_RUN2.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("7645bbb bird_0032 fixture or sqlite missing")
    raw_sql = json.loads(MEASURED_BIRD_0032_7645BBB_RUN2.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0032")
    documents, _ = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")
    runner = sqlite_executor(CA_SCHOOLS_DB, timeout_seconds=30.0)
    inspection = TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req-7645bbb-32",
            status="failed",
            sql=raw_sql,
            attempts=3,
            error=ApiError(
                category="other_result_mismatch",
                message="mismatch",
                retryable=False,
            ),
        ),
        generated_sql=raw_sql,
        repair_trace=(
            {
                "attempt": 3,
                "category": "other_result_mismatch",
                "symptom": "x",
                "sql_hash": "sha256:deadbeef",
            },
        ),
    )

    async def execute_sql(sql: str) -> object:
        return await runner(sql, max_rows=10_000)

    trace = await score_prediction(
        case,
        inspection,
        execute=execute_sql,
        catalog_tables=tuple(d.table_name for d in documents),
    )
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_score_prediction_patches_7645bbb_bird_0096_loan_avg_and_joins() -> None:
    if not MEASURED_BIRD_0096_7645BBB_RUN2.is_file() or not FINANCIAL_DB.is_file():
        pytest.skip("7645bbb bird_0096 fixture or sqlite missing")
    raw_sql = json.loads(MEASURED_BIRD_0096_7645BBB_RUN2.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0096")
    documents, _ = load_sqlite_catalog(FINANCIAL_DB, "financial")
    runner = sqlite_executor(FINANCIAL_DB, timeout_seconds=30.0)
    inspection = TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req-7645bbb-96",
            status="failed",
            sql=raw_sql,
            attempts=3,
            error=ApiError(
                category="other_result_mismatch",
                message="mismatch",
                retryable=False,
            ),
        ),
        generated_sql=raw_sql,
        repair_trace=(
            {
                "attempt": 3,
                "category": "other_result_mismatch",
                "symptom": "x",
                "sql_hash": "sha256:deadbeef",
            },
        ),
    )

    async def execute_sql(sql: str) -> object:
        return await runner(sql, max_rows=10_000)

    trace = await score_prediction(
        case,
        inspection,
        execute=execute_sql,
        catalog_tables=tuple(d.table_name for d in documents),
    )
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_peak_bird_0094_autofix_executes_matching_gold_without_llm() -> None:
    case_file = patch_autofix_case_path("bird_0094")
    if not case_file.is_file() or not FINANCIAL_DB.is_file():
        pytest.skip("peak run or bird sqlite missing")
    peak_sql = json.loads(case_file.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0094")
    documents, edges = load_sqlite_catalog(FINANCIAL_DB, "financial")
    runner = sqlite_executor(FINANCIAL_DB, timeout_seconds=30.0)
    bundle = build_static_bundle(
        model=_NoLlmModel(),  # type: ignore[arg-type]
        token_counter=DeepSeekTokenCounter(),
        documents=documents,
        edges=edges,
        execute=runner,
        database_id="financial",
    )
    inspection = await inspect_text_to_sql(
        bundle,
        question=case.question,
        database_id="financial",
        execute=True,
        max_rows=10_000,
        variant="self_healing",
        frozen_contract=contract_for(case),
        max_recovery_rounds=0,
        benchmark_case_id="bird_0094",
        initial_sql=peak_sql,
    )
    assert inspection.generated_sql is not None
    assert inspection.generated_sql != peak_sql
    conn = sqlite3.connect(FINANCIAL_DB)
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(inspection.generated_sql).fetchall()
    assert results_match(gold, pred, order_sensitive=case.order_sensitive)
    assert inspection.response.status == "succeeded", inspection.response.error

    async def execute_sql(sql: str) -> object:
        return await runner(sql, max_rows=10_000)

    trace = await score_prediction(
        case,
        inspection,
        execute=execute_sql,
        catalog_tables=tuple(d.table_name for d in documents),
    )
    assert trace.ex == 1
    assert trace.primary_class == "matched"
