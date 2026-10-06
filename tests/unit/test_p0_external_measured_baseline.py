"""P0 外部模型实测基线回归（无 LLM replay，gateway 402 时仍可用）。

产品条：TPC-DS 30/30 可复分；BIRD 峰值 run 实测 7/50 可复分。提升实测 EX 需新全量 run，不在此断言。
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from app.evaluation.external_release import release_ready
from tests.unit.bird_replay_fixtures import BIRD_DB_ROOT, BIRD_PEAK_RUN, TPCDS_PEAK_RUN


def test_p0_oracle_release_gate() -> None:
    assert release_ready() is True


def test_p0_bird_measured_baseline_seven_of_fifty_on_peak_run() -> None:
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


def test_p0_tpcds_measured_baseline_thirty_of_thirty_on_peak_run() -> None:
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
