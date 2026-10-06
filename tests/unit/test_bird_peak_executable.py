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


def test_peak_circuit_breaker_cases_saved_sql_executable_except_0094() -> None:
    """熔断 8 题中 7 题保存 SQL 已可执行；失败主因冻结契约/repair 而非沙箱（P0 诊断）。"""
    if not BIRD_PEAK_RUN.is_dir() or not BIRD_DB_ROOT.is_dir():
        pytest.skip("bird replay fixtures unavailable")
    circuit_breaker = (
        "bird_0011",
        "bird_0021",
        "bird_0066",
        "bird_0069",
        "bird_0077",
        "bird_0087",
        "bird_0094",
        "bird_0119",
    )
    not_exec: list[str] = []
    for case_id in circuit_breaker:
        case_file = BIRD_PEAK_RUN / "cases" / f"{case_id}.json"
        payload = json.loads(case_file.read_text())
        sql = payload.get("prediction", {}).get("sql") or ""
        db_name = payload.get("database_id", "")
        db_path = _DB_BY_NAME.get(db_name)
        if db_path is None or not db_path.is_file():
            pytest.skip(f"missing sqlite for {db_name}")
        result = execute_sqlite_readonly(db_path, sql, timeout_seconds=30.0)
        if isinstance(result, SqliteFailure):
            not_exec.append(case_id)
    assert not_exec == ["bird_0094"], not_exec
