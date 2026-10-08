"""Schema 变更 canary：Gold SQL EX 回放（不调用 LLM）。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy.ext.asyncio import AsyncConnection

from app.agents.text_to_sql.workflow import ServiceBundle
from app.evaluation.smoke import execute_gold_sql, load_smoke_cases, single_statement
from app.evaluation.text_to_sql import ExecutionScore, score_case
from app.schemas.benchmark import BenchmarkCase

CANARY_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "schema_mutation" / "canary.yaml"


@dataclass(frozen=True)
class ReplayScore:
    case_id: str
    passed: bool
    detail: str


def load_mutation_canary_cases(path: Path | None = None) -> list[BenchmarkCase]:
    payload = yaml.safe_load((path or CANARY_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("contract_version") != "1.0":
        raise ValueError("schema mutation canary must declare contract_version 1.0")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("schema mutation canary must contain a cases list")
    return [BenchmarkCase.model_validate(item) for item in cases]


def baseline_canary_cases(cases: Sequence[BenchmarkCase]) -> tuple[BenchmarkCase, ...]:
    return tuple(case for case in cases if "baseline" in case.tags)


def mutation_canary_cases(cases: Sequence[BenchmarkCase]) -> tuple[BenchmarkCase, ...]:
    return tuple(case for case in cases if "mutation" in case.tags)


async def replay_canary_ex(
    cases: Sequence[BenchmarkCase],
    conn: AsyncConnection,
) -> list[ReplayScore]:
    """逐条执行 Gold SQL；失败表示 Schema/数据与 canary 不一致。"""

    scores: list[ReplayScore] = []
    for case in cases:
        try:
            single_statement(case.gold_sql)
            result = await execute_gold_sql(case, conn)
        except Exception as exc:
            scores.append(ReplayScore(case.id, False, str(exc)))
            continue
        if not result.rows and case.id.startswith("baseline"):
            scores.append(ReplayScore(case.id, False, "empty result"))
            continue
        scores.append(
            ReplayScore(
                case.id,
                True,
                f"rows={len(result.rows)} cols={len(result.columns)}",
            )
        )
    return scores


async def replay_smoke_subset_ex(
    case_ids: Sequence[str],
    conn: AsyncConnection,
) -> list[ReplayScore]:
    """对冒烟子集做 Gold EX 回放（Text-to-SQL 评测契约，无 Agent）。"""

    by_id = {case.id: case for case in load_smoke_cases()}
    missing = [item for item in case_ids if item not in by_id]
    if missing:
        raise KeyError(f"unknown smoke case ids: {missing}")
    return await replay_canary_ex([by_id[item] for item in case_ids], conn)


def assert_all_passed(scores: Sequence[ReplayScore]) -> None:
    failed = [item for item in scores if not item.passed]
    if failed:
        detail = "; ".join(f"{item.case_id}: {item.detail}" for item in failed)
        raise AssertionError(f"schema mutation replay failed: {detail}")


async def score_agent_ex_cases(
    case_ids: Sequence[str],
    services: ServiceBundle,
    *,
    database_id: str,
) -> list[ExecutionScore]:
    """Text-to-SQL Agent 路径 EX（Gold 仅注入测试模型，不进 Prompt）。"""

    by_id = {case.id: case for case in load_smoke_cases()}
    missing = [item for item in case_ids if item not in by_id]
    if missing:
        raise KeyError(f"unknown smoke case ids: {missing}")
    return [
        await score_case(by_id[case_id], services, database_id=database_id)
        for case_id in case_ids
    ]


def compare_replay_stable(
    before: Sequence[ReplayScore],
    after: Sequence[ReplayScore],
    *,
    case_ids: Sequence[str],
) -> bool:
    """baseline 用例在 mutation 前后都应 passed。"""

    before_map = {item.case_id: item.passed for item in before}
    after_map = {item.case_id: item.passed for item in after}
    return all(before_map.get(item, False) and after_map.get(item, False) for item in case_ids)
