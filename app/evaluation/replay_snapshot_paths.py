"""Canonical paths for vendored peak replay snapshots (see benchmarks/replay_snapshots/)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

BIRD_PEAK_RUN_ID = "run_20261007T071120Z_d50210522e66ad6f6a1da08075574f0fa03ba1a0"
TPCDS_PEAK_RUN_ID = "run_20261007T070145Z_d50210522e66ad6f6a1da08075574f0fa03ba1a0"


def bird_peak_run_dir() -> Path:
    vendored = REPO_ROOT / "benchmarks/replay_snapshots/bird" / BIRD_PEAK_RUN_ID
    legacy = REPO_ROOT / "reports/bird" / BIRD_PEAK_RUN_ID
    return vendored if vendored.is_dir() else legacy


def tpcds_peak_run_dir() -> Path:
    vendored = REPO_ROOT / "benchmarks/replay_snapshots/tpcds-derived" / TPCDS_PEAK_RUN_ID
    legacy = REPO_ROOT / "reports/tpcds-derived" / TPCDS_PEAK_RUN_ID
    return vendored if vendored.is_dir() else legacy
