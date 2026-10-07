"""Optional local BIRD replay snapshots (reports/ is gitignored)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.evaluation.replay_snapshot_paths import (
    bird_peak_run_dir,
    bird_v15_patch_autofix_run_dir,
    tpcds_peak_run_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BIRD_PEAK_RUN = bird_peak_run_dir()
BIRD_V15_PATCH_AUTOFIX_RUN = bird_v15_patch_autofix_run_dir()
BIRD_DB_ROOT = Path("/tmp/bird_dev/minidev/MINIDEV/dev_databases")
CA_SCHOOLS_DB = BIRD_DB_ROOT / "california_schools/california_schools.sqlite"
FINANCIAL_DB = BIRD_DB_ROOT / "financial/financial.sqlite"
TPCDS_PEAK_RUN = tpcds_peak_run_dir()


def bird_sqlite_replay_ready() -> bool:
    """True when MINIDEV SQLite files exist (not merely an empty dev_databases dir)."""
    root = Path(os.environ.get("BIRD_DATABASE_ROOT", str(BIRD_DB_ROOT)))
    schools = root / "california_schools/california_schools.sqlite"
    financial = root / "financial/financial.sqlite"
    return schools.is_file() and financial.is_file()


def ensure_bird_database_root(env: dict[str, str], *, tmp_path: Path | None = None) -> str:
    """Ensure BIRD_DATABASE_ROOT exists (CI runners lack local minidev checkout)."""
    existing = env.get("BIRD_DATABASE_ROOT")
    if existing:
        path = Path(existing)
    elif tmp_path is not None:
        path = tmp_path / "dev_databases"
    else:
        path = Path(tempfile.mkdtemp(prefix="bird_dev_databases_"))
    path.mkdir(parents=True, exist_ok=True)
    env["BIRD_DATABASE_ROOT"] = str(path)
    return str(path)


def peak_case_path(case_id: str) -> Path:
    return BIRD_PEAK_RUN / "cases" / f"{case_id}.json"


def patch_autofix_case_path(case_id: str) -> Path:
    """v15 peak saved SQL where measured-path PATCH autofix is defined (not v11 measured peak)."""

    return BIRD_V15_PATCH_AUTOFIX_RUN / "cases" / f"{case_id}.json"


def postgres_replay_ready() -> bool:
    """TPC-DS `--replay-run` 需要 Postgres catalog（与 verify-tpcds 相同）。"""
    from app.evaluation.external_data import tpcds_postgres_catalog_reachable

    return tpcds_postgres_catalog_reachable()
