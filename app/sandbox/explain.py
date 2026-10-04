"""对已经通过只读门禁的 SQL 加固定 EXPLAIN 前缀，并在只读事务中执行。"""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncConnection

from app.agents.slow_sql.plan import PlanSummary, parse_explain
from app.sandbox.errors import ExecutionError, make_error
from app.sandbox.execute import ExecutionSuccess, execute_readonly
from app.sandbox.gate import check_read_only_sql

_PLAN_PREFIX = "EXPLAIN (FORMAT JSON)"
_ANALYZE_PREFIX = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)"


async def explain_readonly(
    sql: str,
    *,
    analyze: bool,
    connection: AsyncConnection | None = None,
) -> PlanSummary | ExecutionError:
    """先门禁内层 SQL，再执行常量 EXPLAIN。ANALYZE 仍走只读事务。"""

    decision = check_read_only_sql(sql)
    if decision.error is not None:
        return decision.error
    prefix = _ANALYZE_PREFIX if analyze else _PLAN_PREFIX
    outcome = await execute_readonly(
        f"{prefix} {decision.sql}",
        max_rows=1,
        connection=connection,
    )
    if not isinstance(outcome, ExecutionSuccess):
        return outcome
    if len(outcome.rows) != 1 or len(outcome.rows[0]) != 1:
        return _plan_error("执行计划没有返回 JSON")
    try:
        return parse_explain(_load_json(outcome.rows[0][0]), analyzed=analyze)
    except ValueError:
        return _plan_error("执行计划 JSON 无法解析")


def _load_json(value: object) -> object:
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded
    if isinstance(value, bytes | bytearray):
        loaded = json.loads(value.decode())
        return loaded
    return value


def _plan_error(message: str) -> ExecutionError:
    return make_error(
        category="plan_parse",
        message=message,
        exception_type="PlanParseError",
        retryable=False,
    )
