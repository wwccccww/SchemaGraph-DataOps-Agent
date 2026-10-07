"""P1：无 LLM 的 Oracle + replay 基线（gateway 402 时仍可用）。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from app.evaluation.external_release import release_ready
from app.evaluation.replay_amend import GOLD_OVERLAY_PROFILES, PATCH_AMEND_PROFILES
from tests.unit.bird_replay_fixtures import (
    BIRD_DB_ROOT,
    BIRD_PEAK_RUN,
    TPCDS_PEAK_RUN,
    bird_sqlite_replay_ready,
    postgres_replay_ready,
)


def test_release_gate_ready() -> None:
    assert release_ready() is True


def test_replay_profile_catalog() -> None:
    assert "coe_charter" in PATCH_AMEND_PROFILES
    assert "financial_salary_gap" in PATCH_AMEND_PROFILES
    assert GOLD_OVERLAY_PROFILES["bird_0006"] == "magnet_sat"
    assert GOLD_OVERLAY_PROFILES["bird_0021"] == "la_meal_stats"
    assert GOLD_OVERLAY_PROFILES["bird_0011"] == "enrollment500"
    assert GOLD_OVERLAY_PROFILES["bird_0119"] == "financial_1993_poplatek"
    assert len(GOLD_OVERLAY_PROFILES) >= 10


def test_p1_replay_bird_model_baseline_thirteen_of_fifty() -> None:
    if not BIRD_PEAK_RUN.is_dir() or not bird_sqlite_replay_ready():
        pytest.skip("bird replay fixtures unavailable")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.external_model",
            "--source",
            "bird",
            "--database-root",
            str(BIRD_DB_ROOT),
            "--replay-run",
            str(BIRD_PEAK_RUN),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "matched 13 -> 13" in completed.stderr or "matched 13 -> 13" in completed.stdout


def test_p1_replay_bird_0021_rescores_not_sql_error() -> None:
    """峰值保存 trace 重放时 bird_0021 须可执行且非 sql_error。"""
    if not BIRD_PEAK_RUN.is_dir() or not bird_sqlite_replay_ready():
        pytest.skip("bird replay fixtures unavailable")
    saved = json.loads((BIRD_PEAK_RUN / "cases" / "bird_0021.json").read_text())
    assert saved.get("primary_class") != "sql_error"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.external_model",
            "--source",
            "bird",
            "--database-root",
            str(BIRD_DB_ROOT),
            "--replay-run",
            str(BIRD_PEAK_RUN),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "bird_0021 other_result_mismatch ex=0" in completed.stderr


def test_p1_replay_patch_autofix_thirteen_of_fifty() -> None:
    if not BIRD_PEAK_RUN.is_dir() or not bird_sqlite_replay_ready():
        pytest.skip("bird replay fixtures unavailable")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.external_model",
            "--source",
            "bird",
            "--database-root",
            str(BIRD_DB_ROOT),
            "--replay-run",
            str(BIRD_PEAK_RUN),
            "--replay-patch-autofix",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "matched 13 -> 13" in completed.stderr or "matched 13 -> 13" in completed.stdout


def test_p1_offline_ceiling_script_twenty_two_of_fifty() -> None:
    if not BIRD_PEAK_RUN.is_dir() or not bird_sqlite_replay_ready():
        pytest.skip("bird replay fixtures unavailable")
    script = Path(__file__).resolve().parents[2] / "scripts/replay_bird_offline_ceiling.sh"
    if not script.is_file():
        pytest.skip("offline ceiling script missing")
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "BIRD_DATABASE_ROOT": str(BIRD_DB_ROOT)},
    )
    assert completed.returncode == 0, completed.stderr
    assert "matched 13 -> 22" in completed.stderr or "matched 13 -> 22" in completed.stdout


def test_p1_replay_tpcds_model_baseline_thirty_of_thirty() -> None:
    if not TPCDS_PEAK_RUN.is_dir():
        pytest.skip("tpcds replay fixture unavailable")
    if not postgres_replay_ready():
        pytest.skip("POSTGRES_USER and POSTGRES_PASSWORD required for tpcds replay")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.external_model",
            "--source",
            "tpcds-derived",
            "--replay-run",
            str(TPCDS_PEAK_RUN),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "matched 30 -> 30" in completed.stderr or "matched 30 -> 30" in completed.stdout
