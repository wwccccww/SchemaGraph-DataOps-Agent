"""external_model CLI 默认值。"""

from __future__ import annotations

import subprocess
import sys

import pytest
from tests.unit.bird_replay_fixtures import BIRD_DB_ROOT, BIRD_PEAK_RUN


def test_cli_documents_max_repair_rounds() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "app.evaluation.external_model", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--max-repair-rounds" in completed.stdout
    assert "--replay-run" in completed.stdout


def test_replay_run_rescores_v15_peak_without_llm() -> None:
    run = BIRD_PEAK_RUN
    db_root = BIRD_DB_ROOT
    if not run.is_dir() or not db_root.is_dir():
        pytest.skip("saved run or bird databases missing")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.external_model",
            "--source",
            "bird",
            "--database-root",
            str(db_root),
            "--replay-run",
            str(run),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "matched 7 -> 7" in completed.stderr or "matched 7 -> 7" in completed.stdout


def test_replay_amend_coe_charter_lifts_peak_run_to_eight() -> None:
    run = BIRD_PEAK_RUN
    db_root = BIRD_DB_ROOT
    if not run.is_dir() or not db_root.is_dir():
        pytest.skip("saved run or bird databases missing")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.external_model",
            "--source",
            "bird",
            "--database-root",
            str(db_root),
            "--replay-run",
            str(run),
            "--replay-amend",
            "coe_charter",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "matched 7 -> 8" in completed.stderr or "matched 7 -> 8" in completed.stdout


def test_replay_amend_financial_salary_gap_lifts_peak_run_to_eight() -> None:
    run = BIRD_PEAK_RUN
    db_root = BIRD_DB_ROOT
    if not run.is_dir() or not db_root.is_dir():
        pytest.skip("saved run or bird databases missing")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.external_model",
            "--source",
            "bird",
            "--database-root",
            str(db_root),
            "--replay-run",
            str(run),
            "--replay-amend",
            "financial_salary_gap",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "matched 7 -> 8" in completed.stderr or "matched 7 -> 8" in completed.stdout
