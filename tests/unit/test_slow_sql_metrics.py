"""降幅、优化成功和 OptimizePass@3 选择保持文档里的顺序。"""

from __future__ import annotations

from app.agents.slow_sql.metrics import (
    CandidateRank,
    choose_optimize_pass3,
    drop,
    is_optimize_success,
    macro_drop_all_eligible,
)
from app.agents.slow_sql.prompt import render_rewrite_prompt
from app.agents.slow_sql.rules import Finding
from app.evaluation.slow_sql import SMOKE_PATH, load_slow_sql_cases


def test_drop_is_empty_when_the_denominator_is_zero() -> None:
    assert drop(0, 0) is None
    assert drop(0, 5) is None
    assert drop(10, 12) == -0.2


def test_macro_drop_keeps_zero_and_negative_values_and_skips_empty_denominators() -> None:
    summary = macro_drop_all_eligible([0.5, None, 0, -0.2])
    assert summary.excluded == 1
    assert summary.value == (0.5 + 0 - 0.2) / 3


def test_non_equivalent_candidate_is_not_an_optimize_success() -> None:
    assert not is_optimize_success(
        read_only=True,
        equivalent=False,
        primary_drop=0.9,
        secondary_drops={"execution_time": 0.9},
        min_primary_drop=0.05,
        max_secondary_regression=0.1,
        breached_limits=False,
    )
    assert not is_optimize_success(
        read_only=True,
        equivalent=True,
        primary_drop=0.04,
        secondary_drops={},
        min_primary_drop=0.05,
        max_secondary_regression=0.1,
        breached_limits=False,
    )
    assert not is_optimize_success(
        read_only=True,
        equivalent=True,
        primary_drop=0.4,
        secondary_drops={"execution_time": -0.2},
        min_primary_drop=0.05,
        max_secondary_regression=0.1,
        breached_limits=False,
    )
    assert is_optimize_success(
        read_only=True,
        equivalent=True,
        primary_drop=0.4,
        secondary_drops={"execution_time": None},
        min_primary_drop=0.05,
        max_secondary_regression=0.1,
        breached_limits=False,
    )


def test_optimize_pass3_prefers_drop_then_time_then_index() -> None:
    chosen = choose_optimize_pass3(
        (
            CandidateRank(index=0, primary_drop=0.2, execution_time_ms=10, passed=True),
            CandidateRank(index=1, primary_drop=0.5, execution_time_ms=30, passed=True),
            CandidateRank(index=2, primary_drop=0.5, execution_time_ms=20, passed=True),
            CandidateRank(index=3, primary_drop=0.9, execution_time_ms=1, passed=False),
        )
    )
    assert chosen is not None
    assert chosen.index == 2
    tie = choose_optimize_pass3(
        (
            CandidateRank(index=0, primary_drop=0.4, execution_time_ms=5, passed=True),
            CandidateRank(index=1, primary_drop=0.4, execution_time_ms=5, passed=True),
        )
    )
    assert tie is not None
    assert tie.index == 0
    assert choose_optimize_pass3((CandidateRank(0, 0.2, 1, False),)) is None


def test_smoke_cases_cover_four_categories_without_a_reference_rewrite() -> None:
    source = SMOKE_PATH.read_text(encoding="utf-8")
    assert "reference" not in source.lower()
    assert "gold_sql" not in source
    cases = load_slow_sql_cases()
    assert [case.antipattern for case in cases] == [
        "seq-scan-on-large-table",
        "function-on-index-column",
        "implicit-cast-on-index-column",
        "aggregate-after-join",
    ]
    prompt = render_rewrite_prompt(
        sql=cases[0].sql,
        findings=(Finding("seq-scan-on-large-table", "high", "大表发生全表扫描"),),
        nodes=(),
    )
    assert cases[0].sql.strip() in prompt
    assert "line_count" not in prompt
