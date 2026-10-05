"""外部 Gold 在真实数据库上的冒烟执行。需要显式环境变量。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.evaluation.bird import load_bird_cases, load_database_checksums
from app.evaluation.external_data import execute_bird_gold, execute_tpcds_gold, postgres_connection_kwargs
from app.evaluation.external_gold import BIRD_GOLD_SMOKE_IDS, TPCDS_GOLD_SMOKE_IDS
from app.evaluation.tpcds import load_tpcds_cases

pytestmark = pytest.mark.integration


def _external_gold_enabled() -> bool:
    return os.environ.get("EXTERNAL_GOLD_TESTS") == "1"


@pytest.mark.skipif(not _external_gold_enabled(), reason="set EXTERNAL_GOLD_TESTS=1 with databases")
async def test_tpcds_gold_smoke_executes(database_settings) -> None:
    del database_settings
    cases = [case for case in load_tpcds_cases() if case.id in TPCDS_GOLD_SMOKE_IDS]
    assert len(cases) == len(TPCDS_GOLD_SMOKE_IDS)
    traces = await execute_tpcds_gold(cases, timeout_seconds=180, **postgres_connection_kwargs())
    failed = [trace.case_id for trace in traces if trace.status != "ok" or not trace.row_count]
    assert failed == []


@pytest.mark.skipif(not _external_gold_enabled(), reason="set EXTERNAL_GOLD_TESTS=1 with databases")
def test_bird_gold_smoke_executes(database_settings, tmp_path: Path) -> None:
    del database_settings, tmp_path
    root = os.environ.get("BIRD_DATABASE_ROOT")
    if not root:
        pytest.skip("BIRD_DATABASE_ROOT is required")
    database_root = Path(root)
    cases = [case for case in load_bird_cases() if case.id in BIRD_GOLD_SMOKE_IDS]
    assert len(cases) == len(BIRD_GOLD_SMOKE_IDS)
    traces = execute_bird_gold(
        cases,
        database_root,
        load_database_checksums(),
        timeout_seconds=30,
    )
    failed = [trace.case_id for trace in traces if trace.status != "ok"]
    assert failed == []
