"""Error Hash 忽略位置和凭据，相同规范化错误保持稳定。"""

from __future__ import annotations

from app.sandbox.errors import error_hash, make_error, normalize_message


def test_same_normalized_error_has_the_same_hash() -> None:
    first = make_error(
        category="undefined_column",
        message='column "missing_column" does not exist\nLINE 1: SELECT missing_column',
        exception_type="UndefinedColumnError",
        sqlstate="42703",
        retryable=True,
    )
    second = make_error(
        category="undefined_column",
        message='column "missing_column" does not exist LINE 8: at character 12',
        exception_type="UndefinedColumnError",
        sqlstate="42703",
        retryable=True,
    )

    assert first.error_hash == second.error_hash
    assert first.error_hash.startswith("sha256:")
    assert "LINE" not in first.normalized_message or "LINE <n>" in first.normalized_message


def test_normalization_removes_secrets_and_literals() -> None:
    message = normalize_message(
        "password=super-secret failed at /var/lib/postgresql/data "
        "postgres://sandbox:super-secret@db:5432/text2sql_db value 'abc'"
    )

    assert "super-secret" not in message
    assert "postgres://" not in message
    assert "/var/lib" not in message
    assert "<literal>" in message


def test_different_errors_do_not_share_a_hash() -> None:
    column_error = error_hash("42703", "UndefinedColumnError", 'column "a" does not exist')
    table_error = error_hash("42P01", "UndefinedTableError", 'relation "a" does not exist')

    assert column_error != table_error
