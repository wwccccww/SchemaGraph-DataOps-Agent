"""只读事务、流式上限和语句超时。"""

from __future__ import annotations

import time

import pytest
from app.db.engine import get_admin_engine
from app.sandbox.errors import ExecutionError
from app.sandbox.execute import execute_readonly
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def test_sandbox_transaction_is_read_only_and_bounded(database_settings) -> None:
    del database_settings
    settings_result = await execute_readonly(
        "SELECT current_setting('transaction_read_only'), current_setting('statement_timeout')"
    )
    assert not isinstance(settings_result, ExecutionError)
    assert settings_result.rows == [("on", "5s")]
    assert settings_result.truncated is False

    started = time.perf_counter()
    limited = await execute_readonly("SELECT generate_series(1, 5000000)", max_rows=1)
    assert isinstance(limited, ExecutionError)
    assert limited.category == "result_limit_exceeded"
    assert time.perf_counter() - started < 3

    started = time.perf_counter()
    slept = await execute_readonly("SELECT pg_sleep(30)")
    assert isinstance(slept, ExecutionError)
    assert slept.category == "query_canceled"
    assert slept.sqlstate == "57014"
    assert "postgres://" not in slept.normalized_message
    assert time.perf_counter() - started < 15

    async with get_admin_engine().begin() as conn:
        await conn.execute(text("CREATE TABLE phase4_probe (id INT)"))
        await conn.execute(text("INSERT INTO phase4_probe VALUES (1)"))
    try:
        updated = await execute_readonly("UPDATE phase4_probe SET id = 2")
        assert isinstance(updated, ExecutionError)
        async with get_admin_engine().connect() as conn:
            value = await conn.scalar(text("SELECT id FROM phase4_probe"))
        assert value == 1
    finally:
        async with get_admin_engine().begin() as conn:
            await conn.execute(text("DROP TABLE phase4_probe"))

    async with get_admin_engine().connect() as conn:
        idle = await conn.scalar(
            text(
                """
                SELECT count(*)
                FROM pg_stat_activity
                WHERE usename = 'sandbox_readonly'
                  AND state = 'idle in transaction'
                """
            )
        )
    assert idle == 0
