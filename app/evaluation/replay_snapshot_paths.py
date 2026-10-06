"""Canonical paths for vendored peak replay snapshots (see benchmarks/replay_snapshots/)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

BIRD_PEAK_RUN_ID = "run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
TPCDS_PEAK_RUN_ID = "run_20261005T230855Z_43c9faa4c0f6e9844809faa8d8fd781d9150cf74"


def bird_peak_run_dir() -> Path:
    vendored = REPO_ROOT / "benchmarks/replay_snapshots/bird" / BIRD_PEAK_RUN_ID
    legacy = REPO_ROOT / "reports/bird" / BIRD_PEAK_RUN_ID
    return vendored if vendored.is_dir() else legacy


def tpcds_peak_run_dir() -> Path:
    vendored = REPO_ROOT / "benchmarks/replay_snapshots/tpcds-derived" / TPCDS_PEAK_RUN_ID
    legacy = REPO_ROOT / "reports/tpcds-derived" / TPCDS_PEAK_RUN_ID
    return vendored if vendored.is_dir() else legacy
