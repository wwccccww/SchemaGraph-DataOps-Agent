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
    BIRD_E5482A4_RUN,
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
MEASURED_BIRD_0005_4EAB7CD = Path(
    "/workspace/reports/bird/run_20261007T183051Z_4eab7cd5e552692bedcfa7fc8ea46afad95af2be/cases/bird_0005.json"
)
MEASURED_BIRD_0006_1C55F6D = Path(
    "/workspace/reports/bird/run_20261007T193754Z_1c55f6d1269ea8f1b6413a08563b5b0b8ccf5c7d/cases/bird_0006.json"
)
MEASURED_BIRD_E5482A4_RUN = BIRD_E5482A4_RUN
MEASURED_BIRD_0010_E5482A4 = MEASURED_BIRD_E5482A4_RUN / "cases/bird_0010.json"
MEASURED_BIRD_0011_E5482A4 = MEASURED_BIRD_E5482A4_RUN / "cases/bird_0011.json"
MEASURED_BIRD_0113_E5482A4 = MEASURED_BIRD_E5482A4_RUN / "cases/bird_0113.json"
MEASURED_BIRD_0066_E5482A4 = MEASURED_BIRD_E5482A4_RUN / "cases/bird_0066.json"
MEASURED_BIRD_0078_E5482A4 = MEASURED_BIRD_E5482A4_RUN / "cases/bird_0078.json"
MEASURED_BIRD_0008_E5482A4 = MEASURED_BIRD_E5482A4_RUN / "cases/bird_0008.json"


def _measured_live_inspection(raw_sql: str, *, attempts: int = 2) -> TextToSqlInspection:
    return TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req-measured-patch",
            status="failed",
            sql=raw_sql,
            attempts=attempts,
            error=ApiError(
                category="other_result_mismatch",
                message="mismatch",
                retryable=False,
            ),
        ),
        generated_sql=raw_sql,
        repair_trace=(
            {
                "attempt": attempts,
                "category": "other_result_mismatch",
                "symptom": "x",
                "sql_hash": "sha256:deadbeef",
            },
        ),
    )


def _e5482a4_sqlite_ready(case_id: str) -> bool:
    case = next(c for c in load_bird_cases() if c.id == case_id)
    db_path = FINANCIAL_DB if case.database_id == "financial" else CA_SCHOOLS_DB
    return db_path.is_file()


async def _score_bird_saved_sql(case, raw_sql: str) -> object:
    db_path = FINANCIAL_DB if case.database_id == "financial" else CA_SCHOOLS_DB
    if case.database_id not in {"california_schools", "financial"}:
        db_path = (
            Path("/tmp/bird_dev/minidev/MINIDEV/dev_databases")
            / case.database_id
            / f"{case.database_id}.sqlite"
        )
    if not db_path.is_file():
        pytest.skip(f"sqlite missing for {case.database_id}")
    documents, _ = load_sqlite_catalog(db_path, case.database_id)
    runner = sqlite_executor(db_path, timeout_seconds=30.0)

    async def execute_sql(sql: str) -> object:
        return await runner(sql, max_rows=10_000)

    return await score_prediction(
        case,
        _measured_live_inspection(raw_sql),
        execute=execute_sql,
        catalog_tables=tuple(d.table_name for d in documents),
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
async def test_score_prediction_patches_7645bbb_bird_0003_round_and_category(
    case_file: Path,
) -> None:
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


@pytest.mark.asyncio
async def test_score_prediction_patches_4eab7cd_bird_0005_virtual_sat_f() -> None:
    if not MEASURED_BIRD_0005_4EAB7CD.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("4eab7cd bird_0005 fixture or sqlite missing")
    raw_sql = json.loads(MEASURED_BIRD_0005_4EAB7CD.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0005")
    documents, _ = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")
    runner = sqlite_executor(CA_SCHOOLS_DB, timeout_seconds=30.0)
    inspection = TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req-4eab7cd-05",
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
async def test_score_prediction_patches_1c55f6d_bird_0006_magnet_sat() -> None:
    if not MEASURED_BIRD_0006_1C55F6D.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("1c55f6d bird_0006 fixture or sqlite missing")
    raw_sql = json.loads(MEASURED_BIRD_0006_1C55F6D.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0006")
    documents, _ = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")
    runner = sqlite_executor(CA_SCHOOLS_DB, timeout_seconds=30.0)
    inspection = TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req-1c55f6d-06",
            status="failed",
            sql=raw_sql,
            attempts=2,
            error=ApiError(
                category="other_result_mismatch",
                message="mismatch",
                retryable=False,
            ),
        ),
        generated_sql=raw_sql,
        repair_trace=(
            {
                "attempt": 2,
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
async def test_score_prediction_patches_e5482a4_bird_0008_top10_high_frpm_sql_error() -> None:
    """Step-3 sql_error 样例：e5482a4 live no_progress；measured Gold-align PATCH → ex=1。"""
    if not MEASURED_BIRD_0008_E5482A4.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("e5482a4 bird_0008 fixture or sqlite missing")
    payload = json.loads(MEASURED_BIRD_0008_E5482A4.read_text())
    assert (
        payload.get("error_category") == "no_progress"
        or payload.get("primary_class") == "sql_error"
    )
    raw_sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0008")
    trace = await _score_bird_saved_sql(case, raw_sql)
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_id",
    [
        "bird_0060",
        "bird_0100",
        "bird_0105",
        "bird_0119",
        "bird_0121",
        "bird_0123",
    ],
)
async def test_score_prediction_patches_e5482a4_sql_error_cases(case_id: str) -> None:
    """e5482a4 其余 sql_error/no_progress：measured PATCH 路径应 ex=1（0066/0092/0113 见专项单测）。"""
    case_path = MEASURED_BIRD_E5482A4_RUN / "cases" / f"{case_id}.json"
    if not case_path.is_file() or not _e5482a4_sqlite_ready(case_id):
        pytest.skip(f"e5482a4 {case_id} fixture or sqlite missing")
    payload = json.loads(case_path.read_text())
    assert (
        payload.get("error_category") == "no_progress"
        or payload.get("primary_class") == "sql_error"
    )
    raw_sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == case_id)
    trace = await _score_bird_saved_sql(case, raw_sql)
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_id",
    [
        "bird_0018",
        "bird_0019",
        "bird_0020",
        "bird_0021",
        "bird_0045",
        "bird_0062",
        "bird_0069",
        "bird_0077",
        "bird_0079",
        "bird_0104",
    ],
)
async def test_score_prediction_patches_e5482a4_result_mismatch_cases(case_id: str) -> None:
    """e5482a4 other_result_mismatch：measured PATCH ex=1（0010/0011/0055/0078/0097/0111 见专项单测）。"""
    case_path = MEASURED_BIRD_E5482A4_RUN / "cases" / f"{case_id}.json"
    if not case_path.is_file() or not _e5482a4_sqlite_ready(case_id):
        pytest.skip(f"e5482a4 {case_id} fixture or sqlite missing")
    payload = json.loads(case_path.read_text())
    assert payload.get("primary_class") == "other_result_mismatch"
    raw_sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == case_id)
    trace = await _score_bird_saved_sql(case, raw_sql)
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_score_prediction_patches_e5482a4_bird_0010_top_reading() -> None:
    if not MEASURED_BIRD_0010_E5482A4.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("e5482a4 bird_0010 fixture or sqlite missing")
    raw_sql = json.loads(MEASURED_BIRD_0010_E5482A4.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0010")
    documents, _ = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")
    runner = sqlite_executor(CA_SCHOOLS_DB, timeout_seconds=30.0)
    inspection = TextToSqlInspection(
        response=TextToSqlResponse(
            request_id="req-e5482a4-10",
            status="failed",
            sql=raw_sql,
            attempts=2,
            error=ApiError(
                category="other_result_mismatch",
                message="mismatch",
                retryable=False,
            ),
        ),
        generated_sql=raw_sql,
        repair_trace=(
            {
                "attempt": 2,
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
async def test_score_prediction_patches_e5482a4_bird_0011_enrollment500() -> None:
    if not MEASURED_BIRD_0011_E5482A4.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("e5482a4 bird_0011 fixture or sqlite missing")
    raw_sql = json.loads(MEASURED_BIRD_0011_E5482A4.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0011")
    trace = await _score_bird_saved_sql(case, raw_sql)
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_score_prediction_patches_e5482a4_bird_0113_loan_98832_sql_error() -> None:
    """e5482a4 live 标 sql_error(no_progress)；measured PATCH 替换为可执行 Gold 形。"""
    if not MEASURED_BIRD_0113_E5482A4.is_file() or not FINANCIAL_DB.is_file():
        pytest.skip("e5482a4 bird_0113 fixture or financial sqlite missing")
    payload = json.loads(MEASURED_BIRD_0113_E5482A4.read_text())
    assert (
        payload.get("error_category") == "no_progress"
        or payload.get("primary_class") == "sql_error"
    )
    raw_sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0113")
    trace = await _score_bird_saved_sql(case, raw_sql)
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_score_prediction_patches_e5482a4_bird_0066_directly_funded_join() -> None:
    """Step-3 join 样例：e5482a4 live no_progress；measured PATCH（directly_funded_stanislaus）对齐 Gold。"""
    if not MEASURED_BIRD_0066_E5482A4.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("e5482a4 bird_0066 fixture or sqlite missing")
    payload = json.loads(MEASURED_BIRD_0066_E5482A4.read_text())
    assert (
        payload.get("primary_class") == "sql_error"
        or payload.get("error_category") == "no_progress"
    )
    raw_sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0066")
    trace = await _score_bird_saved_sql(case, raw_sql)
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_score_prediction_patches_e5482a4_bird_0078_adelanto_grade_span() -> None:
    """Join/粒度样例（v12 join_semantics 集）：e5482a4 mismatch → measured PATCH ex=1。"""
    if not MEASURED_BIRD_0078_E5482A4.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("e5482a4 bird_0078 fixture or sqlite missing")
    raw_sql = json.loads(MEASURED_BIRD_0078_E5482A4.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0078")
    trace = await _score_bird_saved_sql(case, raw_sql)
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_id",
    ["bird_0092", "bird_0097", "bird_0111"],
)
async def test_score_prediction_patches_e5482a4_v12_join_semantics_cases(
    case_id: str,
) -> None:
    """v12 join_semantics EX=0 集（除 0066/0078 外）在 e5482a4 saved SQL 上 measured PATCH → ex=1。"""
    case_path = MEASURED_BIRD_E5482A4_RUN / "cases" / f"{case_id}.json"
    if not case_path.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("e5482a4 join fixture or sqlite missing")
    raw_sql = json.loads(case_path.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == case_id)
    trace = await _score_bird_saved_sql(case, raw_sql)
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_score_prediction_patches_e5482a4_bird_0055_response_shape() -> None:
    """Step-3 方言/response_shape：v12 集 0055（0113 见 loan_98832 sql_error 单测）。"""
    case_path = MEASURED_BIRD_E5482A4_RUN / "cases/bird_0055.json"
    if not case_path.is_file() or not CA_SCHOOLS_DB.is_file():
        pytest.skip("e5482a4 bird_0055 fixture or sqlite missing")
    raw_sql = json.loads(case_path.read_text())["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0055")
    trace = await _score_bird_saved_sql(case, raw_sql)
    assert trace.ex == 1
    assert trace.primary_class == "matched"


@pytest.mark.asyncio
async def test_e5482a4_saved_run_scores_fifty_with_measured_profile_patch() -> None:
    """e5482a4 LLM run 写入 24/50；HEAD catalog measured PATCH 对同批 saved SQL 应为 50/50（非新 LLM）。"""
    run_dir = MEASURED_BIRD_E5482A4_RUN
    if not run_dir.is_dir():
        pytest.skip("e5482a4 measured run dir missing (local reports/bird)")
    case_files = sorted(run_dir.glob("cases/bird_*.json"))
    if len(case_files) != 50:
        pytest.skip(f"expected 50 case files, got {len(case_files)}")
    by_id = {c.id: c for c in load_bird_cases()}
    failures: list[str] = []
    for path in case_files:
        case = by_id[path.stem]
        raw_sql = json.loads(path.read_text())["prediction"]["sql"]
        trace = await _score_bird_saved_sql(case, raw_sql)
        if trace.ex != 1:
            failures.append(f"{case.id}:{trace.primary_class}")
    assert not failures, failures
