"""Vendored peak replay snapshots ship in-repo for P1 CI replay-gate."""

from __future__ import annotations

from pathlib import Path

from app.evaluation.replay_snapshot_paths import (
    BIRD_PEAK_RUN_ID,
    BIRD_V15_PATCH_AUTOFIX_RUN_ID,
    TPCDS_PEAK_RUN_ID,
    bird_peak_run_dir,
    bird_v15_patch_autofix_run_dir,
    tpcds_peak_run_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_vendored_bird_peak_snapshot_in_repo() -> None:
    vendored = REPO_ROOT / "benchmarks/replay_snapshots/bird" / BIRD_PEAK_RUN_ID
    assert vendored.is_dir(), "commit bird peak under benchmarks/replay_snapshots/"
    cases = list((vendored / "cases").glob("bird_*.json"))
    assert len(cases) == 50
    assert bird_peak_run_dir() == vendored


def test_vendored_bird_v15_patch_autofix_cases_in_repo() -> None:
    vendored = REPO_ROOT / "benchmarks/replay_snapshots/bird" / BIRD_V15_PATCH_AUTOFIX_RUN_ID
    assert vendored.is_dir()
    for case_id in ("bird_0002", "bird_0094"):
        assert (vendored / "cases" / f"{case_id}.json").is_file()
    assert bird_v15_patch_autofix_run_dir() == vendored


def test_vendored_tpcds_peak_snapshot_in_repo() -> None:
    vendored = REPO_ROOT / "benchmarks/replay_snapshots/tpcds-derived" / TPCDS_PEAK_RUN_ID
    assert vendored.is_dir(), "commit tpcds peak under benchmarks/replay_snapshots/"
    cases = list((vendored / "cases").glob("tpcds_complex_*.json"))
    assert len(cases) == 30
    assert tpcds_peak_run_dir() == vendored
