"""Peak BIRD run 预测 SQL 在当前 SQLite 适配器下的可执行性（P1 回归）。"""

from __future__ import annotations

import json

import pytest
from app.sandbox.sqlite import SqliteFailure, execute_sqlite_readonly
from tests.unit.bird_replay_fixtures import BIRD_DB_ROOT, BIRD_PEAK_RUN

_DB_BY_NAME = {
    "california_schools": BIRD_DB_ROOT / "california_schools/california_schools.sqlite",
    "financial": BIRD_DB_ROOT / "financial/financial.sqlite",
}


def test_peak_v15_saved_sql_readonly_failures_only_bird_0094() -> None:
    if not BIRD_PEAK_RUN.is_dir() or not BIRD_DB_ROOT.is_dir():
        pytest.skip("bird replay fixtures unavailable")
    failures: list[str] = []
    for case_file in sorted((BIRD_PEAK_RUN / "cases").glob("bird_*.json")):
        payload = json.loads(case_file.read_text())
        sql = payload.get("prediction", {}).get("sql") or ""
        if not sql.strip():
            failures.append(payload["case_id"])
            continue
        db_name = payload.get("database_id", "")
        db_path = _DB_BY_NAME.get(db_name)
        if db_path is None or not db_path.is_file():
            pytest.skip(f"missing sqlite for {db_name}")
        result = execute_sqlite_readonly(db_path, sql, timeout_seconds=30.0)
        if isinstance(result, SqliteFailure):
            failures.append(payload["case_id"])
    assert failures == ["bird_0094"], failures
