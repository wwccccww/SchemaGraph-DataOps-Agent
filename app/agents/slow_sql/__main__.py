"""通过 `python -m app.agents.slow_sql` 诊断一条 SQL。"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.agents.slow_sql.runtime import get_default_services
from app.agents.slow_sql.workflow import run_slow_sql


def main(argv: list[str] | None = None) -> None:
    """向标准输出打印 JSON 响应。诊断失败时退出码为 1。"""

    parser = argparse.ArgumentParser(description="诊断一条只读慢 SQL")
    parser.add_argument("--sql", required=True)
    parser.add_argument("--database-id", default="ecommerce")
    parser.add_argument("--no-analyze", action="store_true")
    parser.add_argument("--no-rewrite", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    response = asyncio.run(
        run_slow_sql(
            get_default_services(),
            sql=args.sql,
            database_id=args.database_id,
            run_analyze=not args.no_analyze,
            rewrite=not args.no_rewrite,
        )
    )
    sys.stdout.write(response.model_dump_json() + "\n")
    raise SystemExit(0 if response.status == "succeeded" else 1)


if __name__ == "__main__":
    main()
