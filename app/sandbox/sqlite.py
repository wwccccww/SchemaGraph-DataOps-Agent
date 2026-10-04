"""受限 SQLite Adapter。Gold SQL 与 Agent SQL 都走这个执行器。

子进程使用只读 URI、Authorizer、Progress Handler、内存限制和父进程超时。
调用本模块不会把 Gold SQL 放进问数 Prompt。
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
_QUERY_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)
_FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.Attach,
    exp.Detach,
    exp.Pragma,
)


@dataclass(frozen=True)
class SqliteSuccess:
    """一次只读 SQLite 查询的结果。"""

    columns: list[str]
    rows: list[tuple[object, ...]]


@dataclass(frozen=True)
class SqliteFailure:
    """子进程拒绝或中止查询。消息不含路径和密钥。"""

    category: str
    message: str


def worker_environment() -> dict[str, str]:
    """子进程环境。不继承父进程里的密钥。"""

    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": _PROJECT_ROOT,
        "PYTHONNOUSERSITE": "1",
    }


def check_sqlite_read_only(sql: str) -> str | None:
    """静态拒绝多语句和写入。通过时返回去掉末尾分号的 SQL。"""

    statement = sql.strip().rstrip(";").strip()
    if statement == "" or ";" in statement:
        return None
    try:
        parsed = sqlglot.parse(statement, read="sqlite", error_level=sqlglot.ErrorLevel.RAISE)
    except SqlglotError:
        return None
    expressions = [item for item in parsed if item is not None]
    if len(expressions) != 1 or not isinstance(expressions[0], exp.Expression):
        return None
    expression = expressions[0]
    if not isinstance(expression, _QUERY_ROOTS):
        return None
    for node in expression.walk():
        if isinstance(node, _FORBIDDEN):
            return None
    return statement


def execute_sqlite_readonly(
    database: Path,
    sql: str,
    *,
    max_rows: int = 10_000,
    timeout_seconds: float = 5.0,
) -> SqliteSuccess | SqliteFailure:
    """在隔离子进程中执行。超时后杀死整个进程组。"""

    if not 1 <= max_rows <= 10_000:
        raise ValueError("max_rows is outside the sqlite adapter limit")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    statement = check_sqlite_read_only(sql)
    if statement is None:
        return SqliteFailure("not_read_only", "只允许单条只读 SQLite 查询")
    request = {
        "database": str(database),
        "sql": statement,
        "max_rows": max_rows,
        "timeout_seconds": timeout_seconds,
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "app.sandbox.sqlite_worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd="/tmp",
        env=worker_environment(),
        start_new_session=True,
    )
    try:
        stdout, _stderr = process.communicate(
            json.dumps(request),
            timeout=timeout_seconds + 2,
        )
    except subprocess.TimeoutExpired:
        _kill(process)
        return SqliteFailure("timeout", "查询超过时间限制")
    if process.returncode not in {0, None}:
        return SqliteFailure("worker_failed", "SQLite 子进程异常退出")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return SqliteFailure("worker_failed", "SQLite 子进程没有返回 JSON")
    if not isinstance(payload, dict):
        return SqliteFailure("worker_failed", "SQLite 子进程没有返回 JSON")
    if payload.get("status") == "ok":
        columns = payload.get("columns")
        rows = payload.get("rows")
        if not isinstance(columns, list) or not isinstance(rows, list):
            return SqliteFailure("worker_failed", "SQLite 子进程没有返回结果")
        return SqliteSuccess(
            columns=[str(name) for name in columns],
            rows=[tuple(row) for row in rows if isinstance(row, list)],
        )
    category = payload.get("category")
    message = payload.get("message")
    return SqliteFailure(
        category if isinstance(category, str) else "database_error",
        message if isinstance(message, str) else "SQLite 查询失败",
    )


def _kill(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.communicate()
