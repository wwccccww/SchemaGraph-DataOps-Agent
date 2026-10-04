"""在只读事务中流式执行单条 SQL，并在任何结局下回滚。"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.engine import get_sandbox_engine
from app.sandbox.errors import ExecutionError, make_error

STREAM_PREFETCH = 100
MAX_RESULT_BYTES = 8 * 1024 * 1024
MAX_ROWS_CEILING = 10_000
_SQLSTATE_CATEGORY = {
    "22001": "string_data_right_truncation",
    "22003": "numeric_value_out_of_range",
    "22012": "division_by_zero",
    "25006": "read_only_sql_transaction",
    "42501": "insufficient_privilege",
    "42601": "syntax_error",
    "42702": "ambiguous_column",
    "42703": "undefined_column",
    "42804": "datatype_mismatch",
    "42883": "undefined_function",
    "42P01": "undefined_table",
    "42P10": "invalid_column_reference",
    "54000": "program_limit_exceeded",
    "57014": "query_canceled",
}
_RETRYABLE_SQLSTATES = frozenset(
    {"22003", "22012", "42601", "42702", "42703", "42804", "42883", "42P01", "42P10", "57014"}
)


class ResultLimitExceeded(Exception):
    """结果行数超过调用方上限。"""

    def __init__(self, max_rows: int) -> None:
        super().__init__(f"result exceeds {max_rows} rows")
        self.max_rows = max_rows


class ResultSizeExceeded(Exception):
    """结果体积超过固定上限。"""

    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"result exceeds {max_bytes} bytes")
        self.max_bytes = max_bytes


@dataclass(frozen=True)
class ExecutionSuccess:
    """一次只读查询的结果。行数未超过上限时 truncated 恒为 false。"""

    columns: tuple[tuple[str, str], ...]
    rows: tuple[tuple[object, ...], ...]
    row_count: int
    truncated: bool
    execution_time_ms: float


async def execute_readonly(
    sql: str,
    *,
    max_rows: int = 1000,
    connection: AsyncConnection | None = None,
) -> ExecutionSuccess | ExecutionError:
    """用沙箱连接执行。超时和角色名都是固定字面量，不接受外部拼接。"""

    if not 1 <= max_rows <= MAX_ROWS_CEILING:
        raise ValueError("max_rows is outside the sandbox limit")
    if connection is None:
        async with get_sandbox_engine().connect() as owned:
            return await _execute(owned, sql, max_rows=max_rows)
    return await _execute(connection, sql, max_rows=max_rows)


async def _execute(
    conn: AsyncConnection,
    sql: str,
    *,
    max_rows: int,
) -> ExecutionSuccess | ExecutionError:
    transaction = await conn.begin()
    try:
        await conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        await conn.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
        await conn.exec_driver_sql("SET LOCAL lock_timeout = '1s'")
        await conn.exec_driver_sql("SET LOCAL idle_in_transaction_session_timeout = '2s'")
        raw = await conn.get_raw_connection()
        driver = raw.driver_connection
        if driver is None:
            raise RuntimeError("sandbox connection is not backed by asyncpg")
        started = time.perf_counter()
        outcome = await _stream(driver, sql, max_rows=max_rows)
        elapsed_ms = (time.perf_counter() - started) * 1000
    except Exception as exc:
        mapped = _map_exception(exc)
        if mapped is None:
            raise
        return mapped
    else:
        return ExecutionSuccess(
            columns=outcome[0],
            rows=outcome[1],
            row_count=len(outcome[1]),
            truncated=False,
            execution_time_ms=elapsed_ms,
        )
    finally:
        await transaction.rollback()


async def _stream(
    driver: object,
    sql: str,
    *,
    max_rows: int,
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[object, ...], ...]]:
    prepare = getattr(driver, "prepare", None)
    if prepare is None:
        raise RuntimeError("sandbox driver cannot prepare statements")
    statement = await prepare(sql)
    attributes = statement.get_attributes()
    columns = tuple((str(attribute.name), str(attribute.type.name)) for attribute in attributes)
    rows: list[tuple[object, ...]] = []
    size = 0
    async for record in statement.cursor(prefetch=STREAM_PREFETCH):
        if len(rows) >= max_rows:
            raise ResultLimitExceeded(max_rows)
        row = tuple(record)
        size += _estimate_size(row)
        if size > MAX_RESULT_BYTES:
            raise ResultSizeExceeded(MAX_RESULT_BYTES)
        rows.append(row)
    return columns, tuple(rows)


def _estimate_size(row: Sequence[object]) -> int:
    total = 2
    for value in row:
        if value is None:
            total += 4
        elif isinstance(value, bytes | bytearray):
            total += len(value)
        else:
            total += len(str(value))
        total += 1
    return total


def _map_exception(exc: Exception) -> ExecutionError | None:
    if isinstance(exc, ResultLimitExceeded):
        return make_error(
            category="result_limit_exceeded",
            message=f"结果超过 {exc.max_rows} 行",
            exception_type="ResultLimitExceeded",
            retryable=True,
        )
    if isinstance(exc, ResultSizeExceeded):
        return make_error(
            category="result_size_exceeded",
            message=f"结果超过 {exc.max_bytes} 字节",
            exception_type="ResultSizeExceeded",
            retryable=True,
        )
    origin = _unwrap(exc)
    sqlstate = getattr(origin, "sqlstate", None)
    if not isinstance(sqlstate, str):
        return None
    category = _SQLSTATE_CATEGORY.get(sqlstate, "database_error")
    return make_error(
        category=category,
        message=str(origin),
        exception_type=type(origin).__name__,
        sqlstate=sqlstate,
        retryable=sqlstate in _RETRYABLE_SQLSTATES,
    )


def _unwrap(exc: BaseException) -> BaseException:
    current: BaseException = exc
    seen: set[int] = set()
    while id(current) not in seen:
        seen.add(id(current))
        origin = getattr(current, "orig", None)
        if not isinstance(origin, BaseException):
            return current
        current = origin
    return current
