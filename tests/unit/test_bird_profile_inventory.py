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
    # 26 条显式 profile（其余依赖 generic shape + 投影列契约）
    assert with_profile >= 34


def test_bird_explicit_profile_case_ids() -> None:
    """按题 profile 清单（新增 profile 时同步更新）。"""
    expected = frozenset(
        {
            "bird_0002",
            "bird_0003",
            "bird_0005",
            "bird_0006",
            "bird_0008",
            "bird_0010",
            "bird_0011",
            "bird_0012",
            "bird_0013",
            "bird_0018",
            "bird_0019",
            "bird_0020",
            "bird_0021",
            "bird_0031",
            "bird_0032",
            "bird_0045",
            "bird_0055",
            "bird_0060",
            "bird_0061",
            "bird_0062",
            "bird_0066",
            "bird_0069",
            "bird_0077",
            "bird_0078",
            "bird_0079",
            "bird_0087",
            "bird_0092",
            "bird_0094",
            "bird_0100",
            "bird_0103",
            "bird_0105",
            "bird_0106",
            "bird_0118",
            "bird_0119",
        }
    )
    cases = load_bird_cases()
    actual = frozenset(
        case.id
        for case in cases
        if any(item.endswith("_profile=true") for item in contract_for(case).filters)
    )
    assert actual == expected
