"""P1：无 LLM 的 Oracle + replay 基线（gateway 402 时仍可用）。"""

from __future__ import annotations

import subprocess
import sys

import pytest

from app.evaluation.external_release import release_ready
from app.evaluation.replay_amend import GOLD_OVERLAY_PROFILES, PATCH_AMEND_PROFILES
from tests.unit.bird_replay_fixtures import BIRD_DB_ROOT, BIRD_PEAK_RUN, TPCDS_PEAK_RUN


def test_release_gate_ready() -> None:
    assert release_ready() is True


def test_replay_profile_catalog() -> None:
    assert "coe_charter" in PATCH_AMEND_PROFILES
    assert GOLD_OVERLAY_PROFILES["bird_0006"] == "magnet_sat"


def test_p1_replay_bird_model_baseline_seven_of_fifty() -> None:
    if not BIRD_PEAK_RUN.is_dir() or not BIRD_DB_ROOT.is_dir():
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
    assert "matched 7 -> 7" in completed.stderr or "matched 7 -> 7" in completed.stdout


def test_p1_replay_tpcds_model_baseline_thirty_of_thirty() -> None:
    if not TPCDS_PEAK_RUN.is_dir():
        pytest.skip("tpcds replay fixture unavailable")
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
