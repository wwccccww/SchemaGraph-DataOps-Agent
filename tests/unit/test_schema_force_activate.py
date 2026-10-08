"""强制激活策略。"""

from __future__ import annotations

from app.config.settings import get_settings


def test_force_activate_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SCHEMA_REGISTRY_ALLOW_FORCE", raising=False)
    get_settings.cache_clear()
    assert get_settings().schema_registry_allow_force is False
