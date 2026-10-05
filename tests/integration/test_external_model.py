"""外部模型评测可选冒烟。需要 API Key 与 BIRD 数据库。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from app.config.llm_settings import get_llm_settings
from app.evaluation.external_model import _run

pytestmark = pytest.mark.integration


def _external_model_enabled() -> bool:
    if os.environ.get("EXTERNAL_MODEL_TESTS") != "1":
        return False
    get_llm_settings.cache_clear()
    try:
        llm = get_llm_settings()
    except Exception:
        return False
    return llm.deepseek_api_key is not None


@pytest.mark.skipif(not _external_model_enabled(), reason="set EXTERNAL_MODEL_TESTS=1 and DEEPSEEK_API_KEY")
def test_bird_external_model_smoke_one_case() -> None:
    root = os.environ.get("BIRD_DATABASE_ROOT")
    if not root:
        pytest.skip("BIRD_DATABASE_ROOT is required")
    database_root = Path(root)
    code = asyncio.run(
        _run(
            source="bird",
            database_root=database_root,
            per_database=None,
            limit=1,
            full=False,
            variant="self_healing",
            timeout_seconds=60,
            report_root=Path("/tmp/reports/bird-external-model-smoke"),
            max_recovery_rounds=4,
        )
    )
    assert code in {0, 2}
