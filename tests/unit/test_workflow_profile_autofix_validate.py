"""validate 节点对 peak COE charter SQL 的确定性补丁（无 LLM）。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from app.agents.text_to_sql.profile_autofix import autofix_sql_when_frozen_contract_clean
from app.agents.text_to_sql.workflow import (
    ServiceBundle,
    _repair_sql,
    _validate_sql,
    _validation_findings_for_sql,
)
from app.datasources.sqlite_catalog import load_sqlite_catalog
from app.evaluation.bird import load_bird_cases
from app.evaluation.bird_contracts import contract_for
from app.llm.tokenizer import DeepSeekTokenCounter
from tests.unit.bird_replay_fixtures import CA_SCHOOLS_DB, FINANCIAL_DB, patch_autofix_case_path

MEASURED_BIRD_0003_881DD08 = Path(
    "/workspace/reports/bird/run_20261007T152631Z_881dd083d1f0cc3c02f141e48432bec3fca12ca8/cases/bird_0003.json"
)


@pytest.mark.asyncio
async def test_validate_autofixes_peak_bird_0002_without_llm() -> None:
    case_file = patch_autofix_case_path("bird_0002")
    if not case_file.is_file():
        pytest.skip("v15 PATCH autofix fixture missing")
    payload = json.loads(case_file.read_text())
    case = next(c for c in load_bird_cases() if c.id == "bird_0002")
    sql = payload["prediction"]["sql"]

    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    documents, edges = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")

    async def load_catalog() -> tuple[tuple[()], tuple[()]]:
        return tuple(documents), tuple(edges)

    services = ServiceBundle(
        model=AsyncMock(),
        select_tools=AsyncMock(return_value=[]),
        select_seeds=AsyncMock(return_value=[]),
        load_catalog=load_catalog,
        execute=AsyncMock(),
        token_counter=DeepSeekTokenCounter(),
        database_id="california_schools",
    )
    state = {
        "request_id": "test",
        "question": case.question,
        "database_id": "california_schools",
        "variant": "self_healing",
        "execute": True,
        "max_rows": 100,
        "selected_tools": [],
        "seed_tables": [],
        "expanded_tables": [],
        "schema_context": "",
        "schema_token_count": 0,
        "truncated": False,
        "prompt": "",
        "generated_sql": sql,
        "attempt": 1,
        "consecutive_error_hash": None,
        "consecutive_error_count": 0,
        "status": "running",
        "columns": [],
        "rows": [],
        "error_category": None,
        "error_message": None,
        "error_retryable": False,
        "circuit_breaker_triggered": False,
        "db_execution_ms": None,
        "anchor_date": "2026-10-01",
        "dialect": "sqlite",
        "profile": "generic",
        "schema_name": "main",
        "contract_repairs": 0,
        "repair_trace": [],
        "join_paths": [],
        "frozen_contract": contract_for(case).model_dump(mode="json"),
        "max_model_calls": 5,
        "initial_sql": "",
        "candidate_sql": None,
        "candidate_columns": [],
        "candidate_rows": [],
        "candidate_score": 0,
        "candidate_execution_ms": None,
        "benchmark_case_id": "bird_0002",
    }
    pre = await _validation_findings_for_sql(services, state, sql)
    assert pre, "peak 0002 SQL should fail frozen contract before autofix"

    fixed_direct = autofix_sql_when_frozen_contract_clean(
        case_id="bird_0002",
        sql=sql,
        contract=contract_for(case),
        dialect="sqlite",
        frozen_contract_state=state,
    )
    assert fixed_direct is not None and fixed_direct != sql

    validate = _validate_sql(services)
    outcome = await validate(state)
    assert outcome.get("status") == "validated", outcome.get("error_message")
    fixed = outcome.get("generated_sql")
    assert isinstance(fixed, str) and fixed != sql
    from app.agents.text_to_sql.workflow import _frozen_contract_findings

    assert not _frozen_contract_findings(state, fixed)


@pytest.mark.asyncio
async def test_validate_autofixes_measured_bird_0003_881dd08_without_llm() -> None:
    """881dd08 实测 ×100 FRPM SQL：validate 节点 PATCH 后 frozen 清零且 EX=1。"""
    if not MEASURED_BIRD_0003_881DD08.is_file():
        pytest.skip("881dd08 measured bird_0003 fixture missing")
    payload = json.loads(MEASURED_BIRD_0003_881DD08.read_text())
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    sql = payload["prediction"]["sql"]

    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    documents, edges = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")

    async def load_catalog() -> tuple[tuple[()], tuple[()]]:
        return tuple(documents), tuple(edges)

    services = ServiceBundle(
        model=AsyncMock(),
        select_tools=AsyncMock(return_value=[]),
        select_seeds=AsyncMock(return_value=[]),
        load_catalog=load_catalog,
        execute=AsyncMock(),
        token_counter=DeepSeekTokenCounter(),
        database_id="california_schools",
    )
    state = {
        "request_id": "test",
        "question": case.question,
        "database_id": "california_schools",
        "variant": "self_healing",
        "execute": True,
        "max_rows": 100,
        "selected_tools": [],
        "seed_tables": [],
        "expanded_tables": [],
        "schema_context": "",
        "schema_token_count": 0,
        "truncated": False,
        "prompt": "",
        "generated_sql": sql,
        "attempt": 1,
        "consecutive_error_hash": None,
        "consecutive_error_count": 0,
        "status": "running",
        "columns": [],
        "rows": [],
        "error_category": None,
        "error_message": None,
        "error_retryable": False,
        "circuit_breaker_triggered": False,
        "db_execution_ms": None,
        "anchor_date": "2026-10-01",
        "dialect": "sqlite",
        "profile": "generic",
        "schema_name": "main",
        "contract_repairs": 0,
        "repair_trace": [],
        "join_paths": [],
        "frozen_contract": contract_for(case).model_dump(mode="json"),
        "max_model_calls": 5,
        "initial_sql": "",
        "candidate_sql": None,
        "candidate_columns": [],
        "candidate_rows": [],
        "candidate_score": 0,
        "candidate_execution_ms": None,
        "benchmark_case_id": "bird_0003",
    }
    pre = await _validation_findings_for_sql(services, state, sql)
    assert pre, "881dd08 bird_0003 SQL should fail frozen contract before autofix"

    fixed_direct = autofix_sql_when_frozen_contract_clean(
        case_id="bird_0003",
        sql=sql,
        contract=contract_for(case),
        dialect="sqlite",
        frozen_contract_state=state,
    )
    assert fixed_direct is not None and fixed_direct != sql

    validate = _validate_sql(services)
    outcome = await validate(state)
    assert outcome.get("status") == "validated", outcome.get("error_message")
    fixed = outcome.get("generated_sql")
    assert isinstance(fixed, str) and fixed != sql
    from app.agents.text_to_sql.workflow import _frozen_contract_findings

    assert not _frozen_contract_findings(state, fixed)

    import sqlite3

    from app.evaluation.ex import results_match

    conn = sqlite3.connect(CA_SCHOOLS_DB)
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(fixed).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


@pytest.mark.asyncio
async def test_validate_autofixes_peak_bird_0094_without_llm() -> None:
    case_file = patch_autofix_case_path("bird_0094")
    if not case_file.is_file():
        pytest.skip("v15 PATCH autofix fixture missing")
    payload = json.loads(case_file.read_text())
    case = next(c for c in load_bird_cases() if c.id == "bird_0094")
    sql = payload["prediction"]["sql"]

    if not FINANCIAL_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    documents, edges = load_sqlite_catalog(FINANCIAL_DB, "financial")

    async def load_catalog() -> tuple[tuple[()], tuple[()]]:
        return tuple(documents), tuple(edges)

    services = ServiceBundle(
        model=AsyncMock(),
        select_tools=AsyncMock(return_value=[]),
        select_seeds=AsyncMock(return_value=[]),
        load_catalog=load_catalog,
        execute=AsyncMock(),
        token_counter=DeepSeekTokenCounter(),
        database_id="financial",
    )
    state = {
        "request_id": "test",
        "question": case.question,
        "database_id": "financial",
        "variant": "self_healing",
        "execute": True,
        "max_rows": 100,
        "selected_tools": [],
        "seed_tables": [],
        "expanded_tables": [],
        "schema_context": "",
        "schema_token_count": 0,
        "truncated": False,
        "prompt": "",
        "generated_sql": sql,
        "attempt": 1,
        "consecutive_error_hash": None,
        "consecutive_error_count": 0,
        "status": "running",
        "columns": [],
        "rows": [],
        "error_category": None,
        "error_message": None,
        "error_retryable": False,
        "circuit_breaker_triggered": False,
        "db_execution_ms": None,
        "anchor_date": "2026-10-01",
        "dialect": "sqlite",
        "profile": "generic",
        "schema_name": "main",
        "contract_repairs": 0,
        "repair_trace": [],
        "join_paths": [],
        "frozen_contract": contract_for(case).model_dump(mode="json"),
        "max_model_calls": 5,
        "initial_sql": "",
        "candidate_sql": None,
        "candidate_columns": [],
        "candidate_rows": [],
        "candidate_score": 0,
        "candidate_execution_ms": None,
        "benchmark_case_id": "bird_0094",
    }
    pre = await _validation_findings_for_sql(services, state, sql)
    assert pre, "peak 0094 SQL should fail frozen contract before autofix"

    fixed_direct = autofix_sql_when_frozen_contract_clean(
        case_id="bird_0094",
        sql=sql,
        contract=contract_for(case),
        dialect="sqlite",
        frozen_contract_state=state,
    )
    assert fixed_direct is not None and fixed_direct != sql

    validate = _validate_sql(services)
    outcome = await validate(state)
    assert outcome.get("status") == "validated", outcome.get("error_message")
    fixed = outcome.get("generated_sql")
    assert isinstance(fixed, str) and fixed != sql
    from app.agents.text_to_sql.workflow import _frozen_contract_findings

    assert not _frozen_contract_findings(state, fixed)


@pytest.mark.asyncio
async def test_repair_sql_applies_profile_autofix_before_llm_on_measured_bird_0003() -> None:
    """validate 失败后 repair 节点先走 PATCH，避免无 LLM 时仍调模型。"""
    if not MEASURED_BIRD_0003_881DD08.is_file():
        pytest.skip("881dd08 measured bird_0003 fixture missing")
    payload = json.loads(MEASURED_BIRD_0003_881DD08.read_text())
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    sql = payload["prediction"]["sql"]

    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    documents, edges = load_sqlite_catalog(CA_SCHOOLS_DB, "california_schools")

    async def load_catalog() -> tuple[tuple[()], tuple[()]]:
        return tuple(documents), tuple(edges)

    model = AsyncMock()
    services = ServiceBundle(
        model=model,
        select_tools=AsyncMock(return_value=[]),
        select_seeds=AsyncMock(return_value=[]),
        load_catalog=load_catalog,
        execute=AsyncMock(),
        token_counter=DeepSeekTokenCounter(),
        database_id="california_schools",
    )
    state = {
        "request_id": "test",
        "question": case.question,
        "database_id": "california_schools",
        "variant": "self_healing",
        "execute": True,
        "max_rows": 100,
        "selected_tools": [],
        "seed_tables": [],
        "expanded_tables": [],
        "schema_context": "",
        "schema_token_count": 0,
        "truncated": False,
        "prompt": "",
        "generated_sql": sql,
        "attempt": 1,
        "consecutive_error_hash": None,
        "consecutive_error_count": 0,
        "status": "failed",
        "columns": [],
        "rows": [],
        "error_category": "contract_mismatch",
        "error_message": "frozen contract",
        "error_retryable": True,
        "circuit_breaker_triggered": False,
        "db_execution_ms": None,
        "anchor_date": "2026-10-01",
        "dialect": "sqlite",
        "profile": "generic",
        "schema_name": "main",
        "contract_repairs": 0,
        "repair_trace": [],
        "join_paths": [],
        "frozen_contract": contract_for(case).model_dump(mode="json"),
        "max_model_calls": 5,
        "initial_sql": "",
        "candidate_sql": None,
        "candidate_columns": [],
        "candidate_rows": [],
        "candidate_score": 0,
        "candidate_execution_ms": None,
        "benchmark_case_id": "bird_0003",
    }
    repair = _repair_sql(services)
    outcome = await repair(state)
    model.complete.assert_not_called()
    assert outcome.get("generated_sql") != sql
    assert outcome.get("status") == "running"
