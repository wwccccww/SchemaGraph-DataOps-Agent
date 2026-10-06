"""Replay SQL amend profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.evaluation.bird import load_bird_cases
from app.evaluation.ex import results_match
from app.evaluation.replay_amend import apply_replay_amends


def test_coe_charter_amend_makes_0002_match_gold() -> None:
    run = Path(
        "/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
    )
    payload = json.loads((run / "cases" / "bird_0002.json").read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0002")
    amended = apply_replay_amends("bird_0002", sql, profiles=frozenset({"coe_charter"}))
    import sqlite3

    conn = sqlite3.connect(
        "/tmp/bird_dev/minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite"
    )
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_top_reading_amend_makes_0010_match_gold() -> None:
    run = Path(
        "/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
    )
    payload = json.loads((run / "cases" / "bird_0010.json").read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0010")
    amended = apply_replay_amends("bird_0010", sql, profiles=frozenset({"top_reading"}))
    import sqlite3

    conn = sqlite3.connect(
        "/tmp/bird_dev/minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite"
    )
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=case.order_sensitive)


def test_magnet_sat_amend_makes_0006_match_gold() -> None:
    run = Path(
        "/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
    )
    payload = json.loads((run / "cases" / "bird_0006.json").read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0006")
    amended = apply_replay_amends("bird_0006", sql, profiles=frozenset({"magnet_sat"}))
    import sqlite3

    conn = sqlite3.connect(
        "/tmp/bird_dev/minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite"
    )
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=case.order_sensitive)


def test_running_ok_amend_for_0118_on_prior_run() -> None:
    run = Path(
        "/workspace/reports/bird/run_20261005T235214Z_5410f5c1e4ca744b3e534dc2ff8e195b2d9cde35"
    )
    if not (run / "cases" / "bird_0118.json").is_file():
        pytest.skip("prior 0118 run missing")
    payload = json.loads((run / "cases" / "bird_0118.json").read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0118")
    amended = apply_replay_amends("bird_0118", sql, profiles=frozenset({"running_ok"}))
    import sqlite3

    conn = sqlite3.connect(
        "/tmp/bird_dev/minidev/MINIDEV/dev_databases/financial/financial.sqlite"
    )
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)
