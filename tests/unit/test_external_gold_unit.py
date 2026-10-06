"""外部 Gold 指纹与 attestation 契约。"""

from __future__ import annotations

from app.evaluation.bird import BIRD_SOURCE_VERSION, load_bird_cases
from app.evaluation.external_gold import (
    BIRD_GOLD_SMOKE_IDS,
    TPCDS_GOLD_SMOKE_IDS,
    ensure_fingerprints,
    ensure_gold_matched,
    load_attestation,
    wall_clock_sensitive,
)
from app.evaluation.tpcds import TPCDS_SOURCE_VERSION, load_tpcds_cases


def test_frozen_tpcds_attestation_covers_all_cases() -> None:
    cases = load_tpcds_cases()
    ensure_fingerprints(cases, "tpcds-derived")
    document = load_attestation("tpcds-derived")
    assert document["benchmark_version"] == TPCDS_SOURCE_VERSION
    assert document["status"] in {"fingerprint_verified", "gold_matched"}
    stored = document["cases"]
    assert isinstance(stored, dict)
    assert len(stored) == len(cases)


def test_frozen_bird_attestation_covers_all_cases() -> None:
    cases = load_bird_cases()
    ensure_fingerprints(cases, "bird")
    document = load_attestation("bird")
    assert document["benchmark_version"] == BIRD_SOURCE_VERSION
    stored = document["cases"]
    assert isinstance(stored, dict)
    assert len(stored) == len(cases)


def test_smoke_ids_are_subset_of_frozen_cases() -> None:
    tpcds_ids = {case.id for case in load_tpcds_cases()}
    bird_ids = {case.id for case in load_bird_cases()}
    assert set(TPCDS_GOLD_SMOKE_IDS) <= tpcds_ids
    assert set(BIRD_GOLD_SMOKE_IDS) <= bird_ids


def test_bird_attestation_wall_clock_flags_match_adapted_gold() -> None:
    cases = load_bird_cases()
    document = load_attestation("bird")
    stored = document["cases"]
    assert isinstance(stored, dict)
    flagged = {
        case_id
        for case_id, item in stored.items()
        if isinstance(item, dict) and item.get("wall_clock_sensitive") is True
    }
    expected = {case.id for case in cases if wall_clock_sensitive(case.gold_sql)}
    assert flagged == expected
    assert not expected, "adapted BIRD Gold SQL should not depend on runtime now"


def test_full_model_eval_accepts_gold_matched_attestation() -> None:
    cases = load_tpcds_cases()
    ensure_gold_matched(cases, "tpcds-derived")
