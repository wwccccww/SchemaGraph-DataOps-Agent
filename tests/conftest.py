"""测试公共夹具。"""

from __future__ import annotations

import os

import pytest
from app.config.settings import get_settings
from app.db.engine import dispose_engines
from app.db.initialize import initialize_database
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def clear_cached_settings():
    """每个测试都从当前环境重新读取配置。"""

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def database_settings():
    """初始化真实数据库；本地缺少数据库时跳过，CI 中失败。"""

    get_settings.cache_clear()
    try:
        settings = get_settings()
    except ValidationError:
        if os.environ.get("INTEGRATION_TESTS") == "1":
            raise
        pytest.skip("database settings are not configured")

    try:
        await initialize_database(settings)
    except Exception as exc:
        await dispose_engines()
        if os.environ.get("INTEGRATION_TESTS") == "1":
            raise
        pytest.skip(f"PostgreSQL is unavailable ({type(exc).__name__})")

    yield settings
    await dispose_engines()
    get_settings.cache_clear()
