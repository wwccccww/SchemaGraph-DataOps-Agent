"""外部发布门禁。"""

from __future__ import annotations

from app.evaluation.external_gold import load_attestation
from app.evaluation.external_release import evaluate_external_release, release_ready


def test_external_release_is_ready() -> None:
    findings = evaluate_external_release()
    assert not [item for item in findings if item.level == "error"], findings
    assert release_ready() is True


def test_bird_attestation_is_gold_matched() -> None:
    document = load_attestation("bird")
    assert document["status"] == "gold_matched"
    assert isinstance(document.get("database_snapshot"), str)
    cases = document.get("cases")
    assert isinstance(cases, dict)
    assert len(cases) == 50
    assert all(
        isinstance(item, dict) and item.get("status") == "gold_matched"
        for item in cases.values()
    )


def test_tpcds_attestation_is_gold_matched() -> None:
    document = load_attestation("tpcds-derived")
    assert document["status"] == "gold_matched"
    cases = document.get("cases")
    assert isinstance(cases, dict)
    assert len(cases) == 30
