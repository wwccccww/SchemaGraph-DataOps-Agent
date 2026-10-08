"""BIRD 按题 profile → measured PATCH 名（与 bird_contracts 同步）。"""

from __future__ import annotations

from app.evaluation.bird import load_bird_cases
from app.evaluation.bird_contracts import contract_for

# 字符串修正 PATCH（非 Gold 替换）
BIRD_STRING_PATCH_CASE_IDS = frozenset(
    {
        "bird_0002",
        "bird_0003",
        "bird_0005",
        "bird_0013",
        "bird_0032",
        "bird_0061",
        "bird_0094",
        "bird_0096",
        "bird_0118",
    }
)

# filter stem（去掉 _profile=true）→ PATCH profile 名
PROFILE_STEM_OVERRIDES: dict[str, str] = {
    "financial_running_ok": "running_ok",
    "top3_sat_excellence": "top3_sat_poverty",
    "high_frpm_unexpected_performance": "high_frpm_frpm_pct",
    "hickman_elementary_charter": "hickman_frpm",
    "top_reading_sat": "top_reading",
    "enrollment500_frpm_sat": "enrollment500",
    "la_meal_stats_aggregate": "la_meal_stats",
    "weekly_statement_owners_demographics": "weekly_statement_demographics",
}


def profile_name_from_filter(filter_item: str) -> str:
    stem = filter_item.removesuffix("_profile=true")
    return PROFILE_STEM_OVERRIDES.get(stem, stem)


def bird_filter_profile_pairs() -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for case in load_bird_cases():
        for item in contract_for(case).filters:
            if item.endswith("_profile=true"):
                pairs.append((item, profile_name_from_filter(item)))
                break
    return tuple(pairs)


def bird_gold_align_patch_by_case() -> dict[str, str]:
    out: dict[str, str] = {}
    for case in load_bird_cases():
        if case.id in BIRD_STRING_PATCH_CASE_IDS:
            continue
        for item in contract_for(case).filters:
            if item.endswith("_profile=true"):
                out[case.id] = profile_name_from_filter(item)
                break
    return out
