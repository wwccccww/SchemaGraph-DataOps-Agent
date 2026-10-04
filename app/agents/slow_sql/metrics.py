"""慢 SQL 降幅、优化成功条件和 OptimizePass@3 选择。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

PrimaryMetric = Literal["planner_cost", "execution_time", "shared_buffer_access"]
PRIMARY_METRICS: tuple[PrimaryMetric, ...] = (
    "planner_cost",
    "execution_time",
    "shared_buffer_access",
)


@dataclass(frozen=True)
class MacroDrop:
    """全量宏平均。excluded 是分母为零、未进入平均的用例数。"""

    value: float | None
    excluded: int


@dataclass(frozen=True)
class CandidateRank:
    """一个改写候选的排序键。index 从 0 开始。"""

    index: int
    primary_drop: float
    execution_time_ms: float | None
    passed: bool


def drop(raw: float, optimized: float) -> float | None:
    """分母为零时返回 None，不用 0 或 1 代替。"""

    if raw == 0:
        return None
    return (raw - optimized) / raw


def shared_buffer_access(shared_hit_blocks: int, shared_read_blocks: int) -> int:
    """共享缓冲区命中块与未命中后读取块之和。"""

    return shared_hit_blocks + shared_read_blocks


def macro_drop_all_eligible(drops: Sequence[float | None]) -> MacroDrop:
    """失败、不等价、超时或没有改善由调用方记为 0。负值保留，空降幅排除。"""

    applicable = [value for value in drops if value is not None]
    excluded = len(drops) - len(applicable)
    if not applicable:
        return MacroDrop(value=None, excluded=excluded)
    return MacroDrop(value=sum(applicable) / len(applicable), excluded=excluded)


def is_optimize_success(
    *,
    read_only: bool,
    equivalent: bool,
    primary_drop: float | None,
    secondary_drops: Mapping[str, float | None],
    min_primary_drop: float,
    max_secondary_regression: float,
    breached_limits: bool,
) -> bool:
    """五条条件同时成立才算优化成功。不等价候选不能靠 Cost 下降成功。"""

    if not read_only or not equivalent or breached_limits:
        return False
    if primary_drop is None or primary_drop < min_primary_drop:
        return False
    return all(
        value is None or value >= -max_secondary_regression for value in secondary_drops.values()
    )


def choose_optimize_pass3(candidates: Sequence[CandidateRank]) -> CandidateRank | None:
    """多个合格候选时，主指标降幅最高，其次执行时间更低，再取更小序号。"""

    passed = [candidate for candidate in candidates if candidate.passed]
    if not passed:
        return None

    def sort_key(candidate: CandidateRank) -> tuple[float, float, int]:
        elapsed = (
            candidate.execution_time_ms if candidate.execution_time_ms is not None else float("inf")
        )
        return (-candidate.primary_drop, elapsed, candidate.index)

    return min(passed, key=sort_key)
