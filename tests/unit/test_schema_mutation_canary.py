"""Schema mutation canary 契约。"""

from __future__ import annotations

from app.evaluation.schema_mutation import (
    agent_canary_cases,
    baseline_canary_cases,
    load_mutation_canary_cases,
    mutation_canary_cases,
)


def test_canary_file_loads_and_partitions_tags() -> None:
    cases = load_mutation_canary_cases()
    assert len(cases) >= 3
    baselines = baseline_canary_cases(cases)
    mutations = mutation_canary_cases(cases)
    assert len(baselines) >= 2
    assert len(mutations) >= 1
    assert len(agent_canary_cases(cases)) >= 1
    assert {item.id for item in baselines}.isdisjoint({item.id for item in mutations})
