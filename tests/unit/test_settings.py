"""配置加载与 Secret 保护。"""

from __future__ import annotations

import pytest
from app.config.settings import Settings, get_settings
from pydantic import SecretStr, ValidationError


def _set_valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_USER", "text2sql_admin")
    monkeypatch.setenv("POSTGRES_PASSWORD", "local-admin-secret")
    monkeypatch.setenv("POSTGRES_DB", "text2sql_db")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("SANDBOX_DB_PASSWORD", "local-sandbox-secret")


def test_settings_hide_passwords(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_valid_env(monkeypatch)
    settings = get_settings()

    rendered = repr(settings)
    assert "local-admin-secret" not in rendered
    assert "local-sandbox-secret" not in rendered
    assert settings.admin_url().render_as_string(hide_password=True).count("***") == 1


@pytest.mark.parametrize("password", ["", "   ", "replace-with-local-password"])
def test_settings_reject_unsafe_passwords(
    monkeypatch: pytest.MonkeyPatch,
    password: str,
) -> None:
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_PASSWORD", password)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_reject_nul_password() -> None:
    with pytest.raises(ValidationError):
        Settings(
            postgres_user="text2sql_admin",
            postgres_password=SecretStr("bad\x00password"),
            sandbox_db_password=SecretStr("local-sandbox-secret"),
        )


def test_settings_reject_unsafe_identifiers(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_DB", "text2sql_db;drop")

    with pytest.raises(ValidationError):
        Settings()


def test_sandbox_url_uses_fixed_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_valid_env(monkeypatch)
    settings = Settings(
        postgres_user="text2sql_admin",
        postgres_password=SecretStr("local-admin-secret"),
        sandbox_db_password=SecretStr("local-sandbox-secret"),
    )

    assert settings.sandbox_url().username == "sandbox_readonly"
