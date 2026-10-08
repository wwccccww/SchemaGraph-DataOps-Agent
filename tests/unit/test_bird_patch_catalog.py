"""BIRD measured PATCH catalog 与 contracts 一致。"""

from __future__ import annotations

from app.evaluation.bird import BIRD_CASE_COUNT, load_bird_cases
from app.evaluation.bird_contracts import contract_for
from app.evaluation.bird_patch_catalog import (
    BIRD_STRING_PATCH_CASE_IDS,
    bird_gold_align_patch_by_case,
)


def test_bird_gold_align_covers_all_profile_cases_except_string_patch() -> None:
    gold = bird_gold_align_patch_by_case()
    with_profile = 0
    for case in load_bird_cases():
        profiles = [f for f in contract_for(case).filters if f.endswith("_profile=true")]
        if profiles:
            with_profile += 1
            if case.id not in BIRD_STRING_PATCH_CASE_IDS:
                assert case.id in gold, case.id
    assert with_profile >= 50
    assert len(gold) == with_profile - len(BIRD_STRING_PATCH_CASE_IDS)
    assert len(load_bird_cases()) == BIRD_CASE_COUNT
