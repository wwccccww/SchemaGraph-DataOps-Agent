"""BIRD 按题 profile 覆盖（P0 自愈口径 inventory）。"""

from __future__ import annotations

from app.evaluation.bird import BIRD_CASE_COUNT, load_bird_cases
from app.evaluation.bird_contracts import contract_for


def test_bird_cases_have_semantic_contract_and_profile_tags() -> None:
    cases = load_bird_cases()
    assert len(cases) == BIRD_CASE_COUNT
    with_profile = 0
    for case in cases:
        contract = contract_for(case)
        assert case.semantic_contract == contract
        profiles = [item for item in contract.filters if item.endswith("_profile=true")]
        if profiles:
            with_profile += 1
    # 21 条显式 profile（其余依赖 generic shape + 投影列契约）
    assert with_profile >= 21
