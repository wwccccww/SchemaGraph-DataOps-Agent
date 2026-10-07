"""Replay SQL amend profiles."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from app.evaluation.bird import load_bird_cases
from app.evaluation.ex import results_match
from app.evaluation.replay_amend import apply_replay_amends
from tests.unit.bird_replay_fixtures import (
    BIRD_PEAK_RUN,
    CA_SCHOOLS_DB,
    FINANCIAL_DB,
    patch_autofix_case_path,
    peak_case_path,
)


def _require_peak(case_id: str, *, db: Path | None = None) -> tuple[Path, sqlite3.Connection]:
    case_file = peak_case_path(case_id)
    if not case_file.is_file():
        pytest.skip("peak run fixture missing")
    database = db or CA_SCHOOLS_DB
    if not database.is_file():
        pytest.skip("bird sqlite snapshot missing")
    return case_file, sqlite3.connect(database)


def test_v12_measured_peak_bird_0002_saved_sql_matches_gold() -> None:
    case_file = peak_case_path("bird_0002")
    if not case_file.is_file():
        pytest.skip("v12 peak fixture missing")
    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    payload = json.loads(case_file.read_text())
    assert payload.get("ex") == 1
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0002")
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(sql).fetchall()
    assert results_match(gold, pred, order_sensitive=False)
    amended = apply_replay_amends("bird_0002", sql, profiles=frozenset({"coe_charter"}))
    assert amended == sql


def test_hickman_frpm_amend_swaps_free_meal_columns() -> None:
    case_file = peak_case_path("bird_0061")
    if not case_file.is_file():
        pytest.skip("v12 peak bird_0061 missing")
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    amended = apply_replay_amends("bird_0061", sql, profiles=frozenset({"hickman_frpm"}))
    assert "Free Meal Count (K-12)" not in amended or "AS FRPMCount" not in amended.split(
        "Free Meal Count"
    )[0][-20:]
    assert "FRPM Count (K-12)" in amended
    assert "Percent (%) Eligible FRPM (K-12)" in amended


def test_coe_charter_amend_makes_0002_match_gold() -> None:
    case_file = patch_autofix_case_path("bird_0002")
    if not case_file.is_file():
        pytest.skip("v15 PATCH autofix fixture missing")
    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0002")
    amended = apply_replay_amends("bird_0002", sql, profiles=frozenset({"coe_charter"}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_top_reading_amend_makes_0010_match_gold() -> None:
    case_file, conn = _require_peak("bird_0010")
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0010")
    amended = apply_replay_amends("bird_0010", sql, profiles=frozenset({"top_reading"}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=case.order_sensitive)


def test_magnet_sat_amend_makes_0006_match_gold() -> None:
    case_file, conn = _require_peak("bird_0006")
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0006")
    amended = apply_replay_amends("bird_0006", sql, profiles=frozenset({"magnet_sat"}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=case.order_sensitive)


@pytest.mark.parametrize(
    ("case_id", "profile", "db"),
    [
        ("bird_0011", "enrollment500", CA_SCHOOLS_DB),
        ("bird_0021", "la_meal_stats", CA_SCHOOLS_DB),
        ("bird_0066", "directly_funded_stanislaus", CA_SCHOOLS_DB),
        ("bird_0069", "state_special_soc3", CA_SCHOOLS_DB),
        ("bird_0077", "la_k9_frpm_sat", CA_SCHOOLS_DB),
        ("bird_0087", "schools_admin_doc_soc", CA_SCHOOLS_DB),
        ("bird_0119", "financial_1993_poplatek", FINANCIAL_DB),
    ],
)
def test_gold_overlay_amend_makes_profile_cases_match(case_id: str, profile: str, db: Path) -> None:
    case_file, conn = _require_peak(case_id, db=db)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == case_id)
    amended = apply_replay_amends(case_id, sql, profiles=frozenset({profile}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=case.order_sensitive)


def test_financial_salary_gap_amend_makes_0094_match_gold() -> None:
    case_file, conn = _require_peak("bird_0094", db=FINANCIAL_DB)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0094")
    amended = apply_replay_amends("bird_0094", sql, profiles=frozenset({"financial_salary_gap"}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=case.order_sensitive)


def test_running_ok_amend_for_0118_on_prior_run() -> None:
    run = BIRD_PEAK_RUN.parent / "run_20261005T235214Z_5410f5c1e4ca744b3e534dc2ff8e195b2d9cde35"
    if not (run / "cases" / "bird_0118.json").is_file():
        pytest.skip("prior 0118 run missing")
    if not FINANCIAL_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    payload = json.loads((run / "cases" / "bird_0118.json").read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0118")
    amended = apply_replay_amends("bird_0118", sql, profiles=frozenset({"running_ok"}))
    conn = sqlite3.connect(FINANCIAL_DB)
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)
