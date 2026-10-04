"""加载并执行冒烟 Gold SQL。这些 SQL 不能进入 Agent Prompt。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.engine import get_sandbox_engine
from app.schemas.benchmark import BenchmarkCase

SMOKE_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "custom_ecommerce" / "smoke.yaml"


@dataclass(frozen=True)
class GoldResult:
    """一次 Gold SQL 执行结果。"""

    columns: list[str]
    rows: list[tuple[object, ...]]


def load_smoke_cases(path: Path | None = None) -> list[BenchmarkCase]:
    """读取经过人工审计的冒烟用例。"""

    payload = yaml.safe_load((path or SMOKE_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("contract_version") != "1.0":
        raise ValueError("smoke file must declare contract_version 1.0")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("smoke file must contain a cases list")
    return [BenchmarkCase.model_validate(case) for case in cases]


def single_statement(sql: str) -> str:
    """拒绝多语句 Gold SQL。"""

    statement = sql.strip().rstrip(";").strip()
    if statement == "" or ";" in statement:
        raise ValueError("gold SQL must be a single statement")
    return statement


async def execute_gold_sql(case: BenchmarkCase, conn: AsyncConnection | None = None) -> GoldResult:
    """用只读沙箱执行一条 Gold SQL。"""

    statement = single_statement(case.gold_sql)
    if conn is None:
        async with get_sandbox_engine().connect() as owned:
            return await _execute(owned, statement)
    return await _execute(conn, statement)


async def _execute(conn: AsyncConnection, statement: str) -> GoldResult:
    result = await conn.execute(text(statement))
    return GoldResult(
        columns=list(result.keys()),
        rows=[tuple(row) for row in result.all()],
    )


def canonical_rows(
    rows: Sequence[Sequence[object]],
    *,
    order_sensitive: bool,
) -> tuple[tuple[object, ...], ...]:
    """顺序敏感时保留行序，否则按多重集合比较。"""

    normalized = tuple(tuple(row) for row in rows)
    if order_sensitive:
        return normalized
    return tuple(sorted(normalized, key=lambda row: repr(row)))
