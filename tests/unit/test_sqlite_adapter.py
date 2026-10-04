"""受限 SQLite Adapter 的只读、超时和进程隔离。"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.sandbox.sqlite import (
    SqliteFailure,
    SqliteSuccess,
    execute_sqlite_readonly,
    worker_environment,
)


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "sample.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT)")
    connection.execute("INSERT INTO item VALUES (1, 'alpha')")
    connection.commit()
    connection.close()
    return path


def test_select_returns_rows_without_mutating_the_file(tmp_path: Path) -> None:
    database = _database(tmp_path)
    before = database.read_bytes()

    result = execute_sqlite_readonly(database, "SELECT id, name FROM item")

    assert isinstance(result, SqliteSuccess)
    assert result.columns == ["id", "name"]
    assert result.rows == [(1, "alpha")]
    assert database.read_bytes() == before


def test_writes_attach_pragma_and_extension_are_rejected(tmp_path: Path) -> None:
    database = _database(tmp_path)
    statements = [
        "INSERT INTO item VALUES (2, 'beta')",
        "UPDATE item SET name = 'beta'",
        "DELETE FROM item",
        "ATTACH DATABASE ':memory:' AS extra",
        "PRAGMA journal_mode = DELETE",
        "SELECT load_extension('example')",
        "SELECT 1; SELECT 2",
    ]

    for statement in statements:
        result = execute_sqlite_readonly(database, statement)
        assert isinstance(result, SqliteFailure)
        assert result.category == "not_read_only"

    follow_up = execute_sqlite_readonly(database, "SELECT count(*) AS total FROM item")
    assert isinstance(follow_up, SqliteSuccess)
    assert follow_up.rows == [(1,)]


def test_progress_handler_stops_a_long_query(tmp_path: Path) -> None:
    database = _database(tmp_path)
    statement = """
        WITH RECURSIVE counter(value) AS (
            SELECT 1
            UNION ALL
            SELECT value + 1 FROM counter WHERE value < 100000000
        )
        SELECT sum(value) AS total FROM counter
    """

    result = execute_sqlite_readonly(database, statement, timeout_seconds=0.2)

    assert isinstance(result, SqliteFailure)
    assert result.category == "timeout"


def test_worker_environment_drops_the_api_key(tmp_path: Path) -> None:
    os.environ["DEEPSEEK_API_KEY"] = "not-for-the-worker"
    completed = subprocess.run(
        [sys.executable, "-m", "app.sandbox.sqlite_worker"],
        input=json.dumps({"debug_env": True}),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=worker_environment(),
        check=False,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert payload["env_has_api_key"] is False
    assert "not-for-the-worker" not in completed.stdout
