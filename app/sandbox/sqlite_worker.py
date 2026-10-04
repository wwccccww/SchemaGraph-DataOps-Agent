"""在受限子进程中执行一条 SQLite 查询。

本进程不打开网络连接。父进程只传入最小环境变量。
"""

from __future__ import annotations

import json
import os
import resource
import sqlite3
import sys
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

_MEMORY_BYTES = 1536 * 1024 * 1024
_BLOCKED_FUNCTIONS = frozenset({"load_extension", "readfile", "writefile", "edit"})
_ALLOWED_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_RECURSIVE,
    }
)


def main() -> None:
    """从标准输入读取一条请求，把 JSON 结果写到标准输出。"""

    request = json.loads(sys.stdin.read())
    if request.get("debug_env") is True:
        _emit({"status": "ok", "env_has_api_key": "DEEPSEEK_API_KEY" in os.environ})
        return
    _apply_limits()
    database = Path(str(request["database"])).resolve()
    sql = str(request["sql"])
    max_rows = int(request["max_rows"])
    timeout_seconds = float(request["timeout_seconds"])
    try:
        payload = _query(database, sql, max_rows=max_rows, timeout_seconds=timeout_seconds)
    except TimeoutError:
        payload = {"status": "error", "category": "timeout", "message": "查询超过时间限制"}
    except sqlite3.Error as exc:
        payload = _sqlite_error(exc)
    _emit(payload)


def _query(database: Path, sql: str, *, max_rows: int, timeout_seconds: float) -> dict[str, object]:
    if not database.is_file():
        return {"status": "error", "category": "database_error", "message": "数据库文件不存在"}
    uri = "file:" + quote(str(database)) + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    started = time.monotonic()
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.set_authorizer(_authorizer)
        connection.set_progress_handler(_progress(started, timeout_seconds), 1000)
        cursor = connection.execute(sql)
        columns = [str(item[0]) for item in cursor.description or ()]
        rows: list[list[object]] = []
        for record in cursor:
            if len(rows) >= max_rows:
                return {
                    "status": "error",
                    "category": "result_limit_exceeded",
                    "message": f"结果超过 {max_rows} 行",
                }
            rows.append([_cell(value) for value in record])
        return {"status": "ok", "columns": columns, "rows": rows}
    finally:
        connection.close()


def _authorizer(
    action: int,
    arg1: str | None,
    arg2: str | None,
    _db_name: str | None,
    _trigger: str | None,
) -> int:
    if action == sqlite3.SQLITE_FUNCTION:
        names = {value.lower() for value in (arg1, arg2) if isinstance(value, str)}
        if names & _BLOCKED_FUNCTIONS:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    if action in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def _progress(started: float, timeout_seconds: float) -> Callable[[], int]:
    def handler() -> int:
        if time.monotonic() - started > timeout_seconds:
            return 1
        return 0

    return handler


def _apply_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (_MEMORY_BYTES, _MEMORY_BYTES))


def _cell(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _sqlite_error(exc: sqlite3.Error) -> dict[str, object]:
    message = str(exc)
    lowered = message.lower()
    if "not authorized" in lowered or "access is denied" in lowered:
        category = "not_read_only"
    elif "interrupted" in lowered or "abort" in lowered:
        category = "timeout"
    else:
        category = "database_error"
    return {"status": "error", "category": category, "message": message[:500]}


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
