"""数据库初始化只重试连接尚未就绪的错误。"""

from __future__ import annotations

import asyncpg
import pytest
from app.db.initialize import _quoted_literal, is_retryable_database_error


def test_connection_refused_is_retryable() -> None:
    assert is_retryable_database_error(ConnectionRefusedError("refused"))


def test_database_starting_is_retryable() -> None:
    error = asyncpg.CannotConnectNowError("the database system is starting up")
    wrapped = RuntimeError("startup")
    wrapped.__cause__ = error

    assert is_retryable_database_error(wrapped)


@pytest.mark.parametrize(
    "value",
    [
        "'; DROP ROLE sandbox_readonly; --",
        "E'quote'; DROP ROLE sandbox_readonly; --",
    ],
)
def test_quoted_literal_rejects_raw_sql(value: str) -> None:
    with pytest.raises(RuntimeError):
        _quoted_literal(value)


def test_quoted_literal_accepts_postgres_literal() -> None:
    standard = "'quote''s'"
    escaped = "E'quote''\"\\\\;-- \npassword'"

    assert _quoted_literal(standard) == standard
    assert _quoted_literal(escaped) == escaped


def test_invalid_password_is_not_retryable() -> None:
    error = asyncpg.InvalidPasswordError("authentication failed")
    wrapped = RuntimeError("startup")
    wrapped.__cause__ = error

    assert not is_retryable_database_error(wrapped)
