"""Canonical paths for vendored peak replay snapshots (see benchmarks/replay_snapshots/)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

BIRD_PEAK_RUN_ID = "run_20261007T093506Z_65bcd64da44fbc066ac662c9d6695441f24edd19"
BIRD_V11_MEASURED_RUN_ID = "run_20261007T071120Z_d50210522e66ad6f6a1da08075574f0fa03ba1a0"
BIRD_V15_PATCH_AUTOFIX_RUN_ID = "run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
BIRD_E5482A4_MEASURED_RUN_ID = (
    "run_20261007T201201Z_e5482a49f6da08e09e0033a4c55ca9e2562d2032"
)
TPCDS_PEAK_RUN_ID = "run_20261007T070145Z_d50210522e66ad6f6a1da08075574f0fa03ba1a0"


def bird_peak_run_dir() -> Path:
    vendored = REPO_ROOT / "benchmarks/replay_snapshots/bird" / BIRD_PEAK_RUN_ID
    legacy = REPO_ROOT / "reports/bird" / BIRD_PEAK_RUN_ID
    return vendored if vendored.is_dir() else legacy


def bird_v11_measured_run_dir() -> Path:
    """Archived v11 measured peak (13/50) for frozen-contract regression on EX=0 SQL."""

    vendored = REPO_ROOT / "benchmarks/replay_snapshots/bird" / BIRD_V11_MEASURED_RUN_ID
    legacy = REPO_ROOT / "reports/bird" / BIRD_V11_MEASURED_RUN_ID
    return vendored if vendored.is_dir() else legacy


def bird_v15_patch_autofix_run_dir() -> Path:
    """Historical v15 peak traces for PATCH autofix regression (may be a partial vendored tree)."""

    vendored = REPO_ROOT / "benchmarks/replay_snapshots/bird" / BIRD_V15_PATCH_AUTOFIX_RUN_ID
    legacy = REPO_ROOT / "reports/bird" / BIRD_V15_PATCH_AUTOFIX_RUN_ID
    return vendored if vendored.is_dir() else legacy


def bird_e5482a4_measured_run_dir() -> Path:
    """BIRD measured 24/50×2 @ e5482a4 (HEAD catalog PATCH re-scores saved SQL to 50/50)."""

    vendored = REPO_ROOT / "benchmarks/replay_snapshots/bird" / BIRD_E5482A4_MEASURED_RUN_ID
    legacy = REPO_ROOT / "reports/bird" / BIRD_E5482A4_MEASURED_RUN_ID
    return vendored if vendored.is_dir() else legacy


def tpcds_peak_run_dir() -> Path:
    vendored = REPO_ROOT / "benchmarks/replay_snapshots/tpcds-derived" / TPCDS_PEAK_RUN_ID
    legacy = REPO_ROOT / "reports/tpcds-derived" / TPCDS_PEAK_RUN_ID
    return vendored if vendored.is_dir() else legacy
