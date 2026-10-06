"""Peak COE charter SQL 经 PATCH autofix 走通 workflow（无 LLM）。"""

from __future__ import annotations

import json
import sqlite3

import pytest
from app.agents.text_to_sql.workflow import inspect_text_to_sql
from app.datasources.bundle import build_static_bundle
from app.datasources.sqlite_catalog import load_sqlite_catalog
from app.datasources.sqlite_exec import sqlite_executor
from app.evaluation.bird import load_bird_cases
from app.evaluation.bird_contracts import contract_for
from app.evaluation.ex import results_match
from app.llm.tokenizer import DeepSeekTokenCounter
from tests.unit.bird_replay_fixtures import BIRD_PEAK_RUN, CA_SCHOOLS_DB


class _NoLlmModel:
    async def complete(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("LLM must not be called when initial_sql is preset")


@pytest.mark.asyncio
async def test_peak_bird_0002_autofix_executes_matching_gold_without_llm() -> None:
    case_file = BIRD_PEAK_RUN / "cases" / "bird_0002.json"
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
    # Post-execute shape 仍可能判 failed，但 external_model 按 generated_sql 计 EX。
    if inspection.response.status != "succeeded":
        assert inspection.response.error is not None
