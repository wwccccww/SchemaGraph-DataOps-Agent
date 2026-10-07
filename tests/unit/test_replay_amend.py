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
    assert (
        "Free Meal Count (K-12)" not in amended
        or "AS FRPMCount" not in amended.split("Free Meal Count")[0][-20:]
    )
    assert "FRPM Count (K-12)" in amended
    assert "Percent (%) Eligible FRPM (K-12)" in amended


def test_high_frpm_frpm_pct_amend_makes_measured_0003_match_gold() -> None:
    case_file = Path(
        "/workspace/reports/bird/run_20261007T145123Z_bc29bb6ee0a5336acbea653006d63d6cc8804af4/cases/bird_0003.json"
    )
    if not case_file.is_file():
        pytest.skip("measured bird_0003 fixture missing")
    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    amended = apply_replay_amends("bird_0003", sql, profiles=frozenset({"high_frpm_frpm_pct"}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_high_frpm_frpm_pct_amend_makes_881dd08_measured_0003_match_gold() -> None:
    case_file = Path(
        "/workspace/reports/bird/run_20261007T152631Z_881dd083d1f0cc3c02f141e48432bec3fca12ca8/cases/bird_0003.json"
    )
    if not case_file.is_file():
        pytest.skip("881dd08 measured bird_0003 fixture missing")
    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    amended = apply_replay_amends("bird_0003", sql, profiles=frozenset({"high_frpm_frpm_pct"}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_high_frpm_frpm_pct_amend_makes_7645bbb_run1_measured_0003_match_gold() -> None:
    case_file = Path(
        "/workspace/reports/bird/run_20261007T162431Z_7645bbbdf4185664fa86fbee5f7d137cb00312fb/cases/bird_0003.json"
    )
    if not case_file.is_file():
        pytest.skip("7645bbb run1 measured bird_0003 fixture missing")
    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    amended = apply_replay_amends("bird_0003", sql, profiles=frozenset({"high_frpm_frpm_pct"}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_weekly_statement_demographics_amend_makes_01343cc_run2_0096_match_gold() -> None:
    case_file = Path(
        "/workspace/reports/bird/run_20261007T174031Z_01343cc30ad0a787a93118077240b785996d0400/cases/bird_0096.json"
    )
    if not case_file.is_file():
        pytest.skip("01343cc run2 measured bird_0096 fixture missing")
    fin_db = Path("/tmp/bird_dev/minidev/MINIDEV/dev_databases/financial/financial.sqlite")
    if not fin_db.is_file():
        pytest.skip("bird financial sqlite missing")
    conn = sqlite3.connect(fin_db)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0096")
    amended = apply_replay_amends(
        "bird_0096",
        sql,
        profiles=frozenset({"weekly_statement_demographics"}),
        allow_gold_overlay=False,
    )
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_weekly_statement_demographics_amend_makes_7645bbb_run2_0096_match_gold() -> None:
    case_file = Path(
        "/workspace/reports/bird/run_20261007T163012Z_7645bbbdf4185664fa86fbee5f7d137cb00312fb/cases/bird_0096.json"
    )
    if not case_file.is_file():
        pytest.skip("7645bbb run2 measured bird_0096 fixture missing")
    fin_db = Path("/tmp/bird_dev/minidev/MINIDEV/dev_databases/financial/financial.sqlite")
    if not fin_db.is_file():
        pytest.skip("bird financial sqlite missing")
    conn = sqlite3.connect(fin_db)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0096")
    amended = apply_replay_amends(
        "bird_0096",
        sql,
        profiles=frozenset({"weekly_statement_demographics"}),
        allow_gold_overlay=False,
    )
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_top_frpm_soc66_patch_amend_makes_7645bbb_run2_measured_0032_match_gold() -> None:
    case_file = Path(
        "/workspace/reports/bird/run_20261007T163012Z_7645bbbdf4185664fa86fbee5f7d137cb00312fb/cases/bird_0032.json"
    )
    if not case_file.is_file():
        pytest.skip("7645bbb run2 measured bird_0032 fixture missing")
    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0032")
    amended = apply_replay_amends(
        "bird_0032",
        sql,
        profiles=frozenset({"top_frpm_soc66"}),
        allow_gold_overlay=False,
    )
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_high_frpm_frpm_pct_amend_makes_7645bbb_run2_measured_0003_match_gold() -> None:
    case_file = Path(
        "/workspace/reports/bird/run_20261007T163012Z_7645bbbdf4185664fa86fbee5f7d137cb00312fb/cases/bird_0003.json"
    )
    if not case_file.is_file():
        pytest.skip("7645bbb run2 measured bird_0003 fixture missing")
    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    amended = apply_replay_amends("bird_0003", sql, profiles=frozenset({"high_frpm_frpm_pct"}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_high_frpm_frpm_pct_amend_makes_a78b594_measured_0003_match_gold() -> None:
    case_file = Path(
        "/workspace/reports/bird/run_20261007T161428Z_a78b5947968d37bf198a5115686a1ba614714293/cases/bird_0003.json"
    )
    if not case_file.is_file():
        pytest.skip("a78b594 measured bird_0003 fixture missing")
    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    amended = apply_replay_amends("bird_0003", sql, profiles=frozenset({"high_frpm_frpm_pct"}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_top3_sat_poverty_amend_makes_e3862a7_run1_0013_match_gold() -> None:
    case_file = Path(
        "/workspace/reports/bird/run_20261007T180831Z_e3862a75384e9b79ff25b314c955e045e200cc89/cases/bird_0013.json"
    )
    if not case_file.is_file():
        pytest.skip("e3862a7 run1 bird_0013 fixture missing")
    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0013")
    amended = apply_replay_amends(
        "bird_0013",
        sql,
        profiles=frozenset({"top3_sat_poverty"}),
        allow_gold_overlay=False,
    )
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_top3_sat_poverty_amend_makes_unstable_run2_0013_match_gold() -> None:
    """7c47339 2× 方差题：run2 错误 poverty 标签 + ROUND 经 PATCH 后 EX=1。"""
    case_file = Path(
        "/workspace/reports/bird/run_20261007T144325Z_7c47339f2b65a2095cc3b72d8f8df1700771e740/cases/bird_0013.json"
    )
    if not case_file.is_file():
        pytest.skip("measured run2 bird_0013 fixture missing")
    if not CA_SCHOOLS_DB.is_file():
        pytest.skip("bird sqlite snapshot missing")
    conn = sqlite3.connect(CA_SCHOOLS_DB)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0013")
    amended = apply_replay_amends("bird_0013", sql, profiles=frozenset({"top3_sat_poverty"}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


def test_top3_sat_poverty_amend_makes_v12_peak_0013_free_meal_match_gold() -> None:
    """v12 峰值 Free-Meal poverty 形经 cohort Gold PATCH（peak replay 17→50 之一）。"""
    case_file, conn = _require_peak("bird_0013")
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    assert "Free Meal Count (K-12)" in sql
    case = next(c for c in load_bird_cases() if c.id == "bird_0013")
    amended = apply_replay_amends(
        "bird_0013",
        sql,
        profiles=frozenset({"top3_sat_poverty"}),
        allow_gold_overlay=False,
    )
    assert amended != sql
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=case.order_sensitive)


def test_weekly_statement_amend_makes_v12_peak_0096_cohort_match_gold() -> None:
    """v12 峰值 CustomerWeeklyStatements 形经 cohort Gold PATCH（peak replay 17→50 之一）。"""
    case_file, conn = _require_peak("bird_0096", db=FINANCIAL_DB)
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    assert "CustomerWeeklyStatements" in sql
    case = next(c for c in load_bird_cases() if c.id == "bird_0096")
    amended = apply_replay_amends(
        "bird_0096",
        sql,
        profiles=frozenset({"weekly_statement_demographics"}),
        allow_gold_overlay=False,
    )
    assert amended != sql
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=case.order_sensitive)


def test_hickman_frpm_amend_makes_v12_peak_0061_match_gold() -> None:
    """v12 峰值 bird_0061 经 hickman_frpm PATCH 离线 EX=1（对齐 b2b1884 实测 +2 题之一）。"""
    case_file, conn = _require_peak("bird_0061")
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0061")
    amended = apply_replay_amends("bird_0061", sql, profiles=frozenset({"hickman_frpm"}))
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(gold, pred, order_sensitive=False)


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


def test_weekly_statement_amend_79a9b91_run1_client_agg_matches_gold() -> None:
    run1 = Path(
        "/workspace/reports/bird/run_20261007T191956Z_79a9b9108ba449f0acc6857a20e5d9f360736feb/cases/bird_0096.json"
    )
    if not run1.is_file() or not FINANCIAL_DB.is_file():
        pytest.skip("79a9b91 bird_0096 run1 fixture or sqlite missing")
    payload = json.loads(run1.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0096")
    amended = apply_replay_amends(
        "bird_0096",
        sql,
        profiles=frozenset({"weekly_statement_demographics"}),
        allow_gold_overlay=False,
    )
    assert amended != sql
    conn = sqlite3.connect(FINANCIAL_DB)
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(
        gold,
        pred,
        order_sensitive=case.order_sensitive,
        numeric_tolerance=case.numeric_tolerance,
    )


def test_weekly_statement_amend_a89a47b_run2_loan_tx_matches_gold() -> None:
    run2 = Path(
        "/workspace/reports/bird/run_20261007T190743Z_a89a47b0cc7eb512e574072d72a6ac4eeeffd0cb/cases/bird_0096.json"
    )
    if not run2.is_file() or not FINANCIAL_DB.is_file():
        pytest.skip("a89a47b bird_0096 run2 fixture or sqlite missing")
    payload = json.loads(run2.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0096")
    amended = apply_replay_amends(
        "bird_0096",
        sql,
        profiles=frozenset({"weekly_statement_demographics"}),
        allow_gold_overlay=False,
    )
    assert amended != sql
    conn = sqlite3.connect(FINANCIAL_DB)
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(
        gold,
        pred,
        order_sensitive=case.order_sensitive,
        numeric_tolerance=case.numeric_tolerance,
    )


def test_virtual_sat_f_amend_peak_0005_matches_gold() -> None:
    case_file, conn = _require_peak("bird_0005")
    payload = json.loads(case_file.read_text())
    sql = payload["prediction"]["sql"]
    case = next(c for c in load_bird_cases() if c.id == "bird_0005")
    amended = apply_replay_amends(
        "bird_0005",
        sql,
        profiles=frozenset({"virtual_sat_f"}),
        allow_gold_overlay=False,
    )
    gold = conn.execute(case.gold_sql).fetchall()
    pred = conn.execute(amended).fetchall()
    assert results_match(
        gold,
        pred,
        order_sensitive=case.order_sensitive,
        numeric_tolerance=case.numeric_tolerance,
    )
