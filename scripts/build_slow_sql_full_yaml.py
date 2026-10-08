#!/usr/bin/env python3
"""从 slow_sql_catalog 生成 benchmarks/slow_sql/full.yaml。"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.evaluation.slow_sql_catalog import FULL_CASE_COUNT, full_slow_sql_case_payloads

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks" / "slow_sql" / "full.yaml"


def main() -> None:
    payload = {
        "contract_version": "1.0",
        "benchmark": "slow_sql_full",
        "case_count": FULL_CASE_COUNT,
        "cases": full_slow_sql_case_payloads(),
    }
    OUT.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({FULL_CASE_COUNT} cases)")


if __name__ == "__main__":
    main()
