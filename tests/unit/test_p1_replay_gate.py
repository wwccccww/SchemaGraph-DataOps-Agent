"""P1：无 LLM 的 Oracle + replay 基线（gateway 402 时仍可用）。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.evaluation.external_release import release_ready
from app.evaluation.replay_amend import GOLD_OVERLAY_PROFILES, PATCH_AMEND_PROFILES

_BIRD_PEAK = Path(
    "/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
)
_TPCDS_PEAK = Path(
    "/workspace/reports/tpcds-derived/run_20261005T230855Z_43c9faa4c0f6e9844809faa8d8fd781d9150cf74"
)
_BIRD_DB = Path("/tmp/bird_dev/minidev/MINIDEV/dev_databases")


def test_release_gate_ready() -> None:
    assert release_ready() is True


def test_replay_profile_catalog() -> None:
    assert "coe_charter" in PATCH_AMEND_PROFILES
    assert GOLD_OVERLAY_PROFILES["bird_0006"] == "magnet_sat"


def test_p1_replay_bird_model_baseline_seven_of_fifty() -> None:
    if not _BIRD_PEAK.is_dir() or not _BIRD_DB.is_dir():
        pytest.skip("bird replay fixtures unavailable")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.external_model",
            "--source",
            "bird",
            "--database-root",
            str(_BIRD_DB),
            "--replay-run",
            str(_BIRD_PEAK),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "matched 7 -> 7" in completed.stderr or "matched 7 -> 7" in completed.stdout


def test_p1_replay_tpcds_model_baseline_thirty_of_thirty() -> None:
    if not _TPCDS_PEAK.is_dir():
        pytest.skip("tpcds replay fixture unavailable")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.external_model",
            "--source",
            "tpcds-derived",
            "--replay-run",
            str(_TPCDS_PEAK),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "matched 30 -> 30" in completed.stderr or "matched 30 -> 30" in completed.stdout
