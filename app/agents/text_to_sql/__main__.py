"""通过 `python -m app.agents.text_to_sql` 提问。"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.agents.text_to_sql.runtime import get_default_services
from app.agents.text_to_sql.workflow import run_text_to_sql


def main(argv: list[str] | None = None) -> None:
    """向标准输出打印 JSON 响应。失败时退出码为 1。"""

    parser = argparse.ArgumentParser(description="用自然语言生成只读 SQL")
    parser.add_argument("question")
    parser.add_argument("--database-id", default="ecommerce")
    parser.add_argument("--max-rows", type=int, default=1000)
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    response = asyncio.run(
        run_text_to_sql(
            get_default_services(),
            question=args.question,
            database_id=args.database_id,
            execute=not args.no_execute,
            max_rows=args.max_rows,
        )
    )
    sys.stdout.write(response.model_dump_json(exclude_none=True) + "\n")
    raise SystemExit(0 if response.status == "succeeded" else 1)


if __name__ == "__main__":
    main()
