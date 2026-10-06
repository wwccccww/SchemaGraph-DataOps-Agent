"""validate 节点对 peak COE charter SQL 的确定性补丁（无 LLM）。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from app.agents.text_to_sql.profile_autofix import autofix_sql_when_frozen_contract_clean
from app.agents.text_to_sql.workflow import (
    ServiceBundle,
    _validate_sql,
    _validation_findings_for_sql,
)
from app.datasources.sqlite_catalog import load_sqlite_catalog
from app.evaluation.bird import load_bird_cases
from app.evaluation.bird_contracts import contract_for
from app.llm.tokenizer import DeepSeekTokenCounter
from tests.unit.bird_replay_fixtures import CA_SCHOOLS_DB


@pytest.mark.asyncio
async def test_validate_autofixes_peak_bird_0002_without_llm() -> None:
    run = Path(
        "/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
    )
    case_file = run / "cases" / "bird_0002.json"
    if not case_file.is_file():
        pytest.skip("peak run fixture missing")
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
