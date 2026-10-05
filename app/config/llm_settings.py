"""DeepSeek 调用配置。外部 Gold 模型评测只需这一层，不依赖电商 Postgres/Sandbox。"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_API_KEY = "replace-with-deepseek-api-key"


class LlmSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

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
        from urllib.parse import urlsplit

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


@lru_cache
def get_llm_settings() -> LlmSettings:
    """返回缓存的 LLM 配置。"""

    return LlmSettings()
