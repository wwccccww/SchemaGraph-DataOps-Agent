"""外部发布门禁。"""

from __future__ import annotations

from app.evaluation.external_release import evaluate_external_release, release_ready


def test_release_is_not_ready_until_gold_matched() -> None:
    findings = evaluate_external_release()
    assert any(item.level == "error" for item in findings)
    assert release_ready() is False
