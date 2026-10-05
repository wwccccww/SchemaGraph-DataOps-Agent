"""把 SQLite 只读适配器收成问数执行器。"""

from __future__ import annotations

import time
from pathlib import Path

from app.agents.text_to_sql.workflow import SqlExecutor
from app.sandbox.errors import ExecutionError, make_error
from app.sandbox.execute import ExecutionSuccess
from app.sandbox.sqlite import SqliteFailure, SqliteSuccess, execute_sqlite_readonly


def sqlite_executor(database: Path, *, timeout_seconds: float) -> SqlExecutor:
    """返回工作流可以使用的异步执行器。"""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    async def execute(sql: str, *, max_rows: int) -> ExecutionSuccess | ExecutionError:
        started = time.perf_counter()
        result = execute_sqlite_readonly(
            database,
            sql,
            max_rows=max_rows,
            timeout_seconds=timeout_seconds,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if isinstance(result, SqliteFailure):
            return make_error(
                category=result.category,
                message=result.message,
                exception_type="SqliteFailure",
                retryable=result.category not in {"timeout", "worker_failed"},
            )
        return _success(result, elapsed_ms)

    return execute


def _success(result: SqliteSuccess, elapsed_ms: float) -> ExecutionSuccess:
    return ExecutionSuccess(
        columns=tuple((name, "") for name in result.columns),
        rows=tuple(tuple(row) for row in result.rows),
        row_count=len(result.rows),
        truncated=False,
        execution_time_ms=elapsed_ms,
    )
