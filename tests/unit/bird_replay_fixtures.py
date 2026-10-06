"""Optional local BIRD replay snapshots (reports/ is gitignored)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BIRD_PEAK_RUN = (
    REPO_ROOT
    / "reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
)
BIRD_DB_ROOT = Path("/tmp/bird_dev/minidev/MINIDEV/dev_databases")
CA_SCHOOLS_DB = BIRD_DB_ROOT / "california_schools/california_schools.sqlite"
FINANCIAL_DB = BIRD_DB_ROOT / "financial/financial.sqlite"
TPCDS_PEAK_RUN = (
    REPO_ROOT
    / "reports/tpcds-derived/run_20261005T230855Z_43c9faa4c0f6e9844809faa8d8fd781d9150cf74"
)


def peak_case_path(case_id: str) -> Path:
    return BIRD_PEAK_RUN / "cases" / f"{case_id}.json"
