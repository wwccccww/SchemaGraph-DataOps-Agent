"""慢 SQL 50 条全量 Benchmark 跑分 CLI。"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config.settings import get_settings
from app.evaluation.slow_sql import (
    FULL_PATH,
    SMOKE_PATH,
    load_full_slow_sql_cases,
    load_slow_sql_cases,
    score_slow_sql_cases,
    summarize_slow_sql_scores,
)
from app.llm.gateway import DeepSeekGateway


async def _run(*, smoke: bool, report_root: Path | None) -> int:
    settings = get_settings()
    if settings.deepseek_api_key is None:
        print("DEEPSEEK_API_KEY is required for slow sql benchmark", file=sys.stderr)
        return 2
    cases = load_slow_sql_cases(SMOKE_PATH) if smoke else load_full_slow_sql_cases(FULL_PATH)
    model = DeepSeekGateway(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
    scores = await score_slow_sql_cases(cases, model, settings)
    summary = summarize_slow_sql_scores(scores)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    label = "smoke" if smoke else "full"
    print(
        f"slow_sql_benchmark={label} "
        f"optimize_success={summary['optimize_success_count']}/{summary['case_count']} "
        f"rate={summary['optimize_pass_rate']}"
    )
    if report_root is not None:
        directory = report_root / f"run_{stamp}_{label}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"slow_sql_report_dir={directory}")
    failed = [score for score in scores if not score.optimize_success]
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run slow SQL benchmark (smoke or 50-case full)")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="run 4-case smoke.yaml instead of full.yaml",
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path("reports/slow_sql"),
        help="write summary.json under reports/slow_sql/run_*",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="print summary only, do not write reports/",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    code = asyncio.run(
        _run(
            smoke=args.smoke,
            report_root=None if args.no_report else args.report_root,
        )
    )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
