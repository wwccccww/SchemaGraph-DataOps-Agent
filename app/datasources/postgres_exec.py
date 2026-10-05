"""在指定 PostgreSQL 库的只读事务里执行。拒绝连到电商库。"""

from __future__ import annotations

import time

import asyncpg

from app.sandbox.errors import ExecutionError, make_error
from app.sandbox.execute import MAX_ROWS_CEILING, ExecutionSuccess

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
ECOMMERCE_DATABASE = "text2sql_db"


async def execute_registered_postgres(
    sql: str,
    *,
    max_rows: int,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    timeout_seconds: float,
) -> ExecutionSuccess | ExecutionError:
    """每次查询单独连接，结束时回滚。密码不会进入错误文本。"""

    if database == ECOMMERCE_DATABASE:
        raise ValueError("refusing to execute external SQL on the ecommerce database")
    if not 1 <= max_rows <= MAX_ROWS_CEILING:
        raise ValueError("max_rows is outside the sandbox limit")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    timeout_ms = int(timeout_seconds * 1000)
    try:
        connection = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
    except Exception as exc:
        return _connection_error(exc, password)
    try:
        transaction = connection.transaction(readonly=True)
        await transaction.start()
        try:
            await connection.execute(
                "SELECT set_config('statement_timeout', $1, true)",
                str(timeout_ms),
            )
            started = time.perf_counter()
            statement = await connection.prepare(sql)
            attributes = statement.get_attributes()
            columns = tuple(
                (str(attribute.name), str(getattr(attribute.type, "name", "")))
                for attribute in attributes
            )
            rows: list[tuple[object, ...]] = []
            async for record in statement.cursor():
                if len(rows) >= max_rows:
                    return make_error(
                        category="result_limit_exceeded",
                        message=f"结果超过 {max_rows} 行",
                        exception_type="ResultLimitExceeded",
                        retryable=True,
                    )
                rows.append(tuple(record))
            elapsed_ms = (time.perf_counter() - started) * 1000
            return ExecutionSuccess(
                columns=columns,
                rows=tuple(rows),
                row_count=len(rows),
                truncated=False,
                execution_time_ms=elapsed_ms,
            )
        except asyncpg.PostgresError as exc:
            return _postgres_error(exc, password)
        finally:
            await transaction.rollback()
    finally:
        await connection.close()


def _connection_error(exc: Exception, password: str) -> ExecutionError:
    return make_error(
        category="database_error",
        message=_safe_text(exc, password),
        exception_type=type(exc).__name__,
        retryable=False,
    )


def _postgres_error(exc: asyncpg.PostgresError, password: str) -> ExecutionError:
    sqlstate = exc.sqlstate if isinstance(exc.sqlstate, str) else None
    category = _SQLSTATE_CATEGORY.get(sqlstate or "", "database_error")
    return make_error(
        category=category,
        message=_safe_text(exc, password),
        exception_type=type(exc).__name__,
        sqlstate=sqlstate,
        retryable=sqlstate in _RETRYABLE_SQLSTATES,
    )


def _safe_text(exc: BaseException, password: str) -> str:
    text = str(exc)
    if password and password in text:
        return "could not query the database"
    return text
