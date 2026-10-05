"""LLM 配置与电商 Settings 解耦。"""

from __future__ import annotations

import os

import pytest
from app.config.llm_settings import get_llm_settings


def test_llm_settings_loads_without_sandbox_password(monkeypatch: pytest.MonkeyPatch) -> None:
    get_llm_settings.cache_clear()
    monkeypatch.delenv("SANDBOX_DB_PASSWORD", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-for-unit")
    settings = get_llm_settings()
    assert settings.deepseek_api_key is not None
    assert settings.deepseek_model == "deepseek-chat"
