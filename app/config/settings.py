"""从环境变量加载配置，不在仓库中保存 Secret。"""

from __future__ import annotations

import re
from functools import lru_cache
from urllib.parse import urlsplit

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_PLACEHOLDER_PASSWORDS = frozenset(
    {
        "replace-with-local-password",
        "replace-with-local-sandbox-password",
    }
)
_PLACEHOLDER_API_KEY = "replace-with-deepseek-api-key"
_SANDBOX_ROLE = "sandbox_readonly"


class Settings(BaseSettings):
    """阶段 0 运行所需的数据库与 API 配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str = "text2sql_db"
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    sandbox_db_password: SecretStr
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    db_init_attempts: int = Field(default=30, ge=1, le=120)
    db_init_delay_seconds: float = Field(default=1.0, gt=0, le=30)
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    text_to_sql_catalog_mode: Literal["fixed_ecommerce", "live_public"] = "fixed_ecommerce"
    schema_registry_auto_activate: bool = True
    schema_registry_auto_index: bool = False
    schema_registry_require_embeddings: bool = False

    @field_validator("postgres_user", "postgres_db")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if _IDENTIFIER.fullmatch(value) is None:
            raise ValueError("database identifiers must match [A-Za-z_][A-Za-z0-9_]{0,62}")
        return value

    @field_validator("postgres_password", "sandbox_db_password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if password.strip() == "" or "\x00" in password:
            raise ValueError("password must be a non-empty string without NUL")
        if password in _PLACEHOLDER_PASSWORDS:
            raise ValueError("password still uses a placeholder from .env.example")
        return value

    @field_validator("deepseek_api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        secret = value.get_secret_value()
        if secret.strip() == "" or "\x00" in secret or secret == _PLACEHOLDER_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY must be a real non-empty key")
        return value

    @field_validator("deepseek_base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or parsed.netloc == "":
            raise ValueError("DEEPSEEK_BASE_URL must be an http(s) URL")
        return value.rstrip("/")

    @field_validator("deepseek_model")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        if value.strip() == "" or any(character.isspace() for character in value):
            raise ValueError("DEEPSEEK_MODEL must be a single token")
        return value

    @property
    def sandbox_role(self) -> str:
        return _SANDBOX_ROLE

    def admin_url(self) -> URL:
        return self._url(self.postgres_user, self.postgres_password)

    def sandbox_url(self) -> URL:
        return self._url(self.sandbox_role, self.sandbox_db_password)

    def _url(self, username: str, password: SecretStr) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=username,
            password=password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    """返回缓存的进程配置。"""

    return Settings()
