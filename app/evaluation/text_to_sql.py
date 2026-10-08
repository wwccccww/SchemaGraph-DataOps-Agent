"""对冒烟用例计算 EX。Gold SQL 只在评分时读取，不进入工作流。"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.text_to_sql.workflow import ServiceBundle, run_text_to_sql
from app.evaluation.ex import results_match
from app.evaluation.smoke import load_smoke_cases
from app.sandbox.errors import ExecutionError
from app.sandbox.execute import execute_readonly
from app.sandbox.gate import check_read_only_sql
from app.schemas.benchmark import BenchmarkCase

EVALUATION_MAX_ROWS = 10_000


@dataclass(frozen=True)
class ExecutionScore:
    """一条用例的 EX。失败、超时和熔断都记 0。"""

    case_id: str
    ex: int
    status: str
    attempts: int


async def score_smoke_cases(services: ServiceBundle) -> list[ExecutionScore]:
    """按文件顺序评分 10 条冒烟用例。"""

    return [await score_case(case, services) for case in load_smoke_cases()]


async def score_case(
    case: BenchmarkCase,
    services: ServiceBundle,
    *,
    database_id: str | None = None,
) -> ExecutionScore:
    """生成并执行 Agent SQL，再与 Gold 结果做语义比较。"""

    response = await run_text_to_sql(
        services,
        question=case.question,
        database_id=database_id or case.database_id,
        execute=True,
        max_rows=1000,
    )
    attempts = response.attempts or 0
    if response.status != "succeeded" or response.sql is None:
        return ExecutionScore(case.id, 0, response.status, attempts)
    decision = check_read_only_sql(case.gold_sql)
    if decision.error is not None:
        raise RuntimeError(f"gold SQL failed the read-only gate: {case.id}")
    agent = await execute_readonly(response.sql, max_rows=EVALUATION_MAX_ROWS)
    gold = await execute_readonly(decision.sql, max_rows=EVALUATION_MAX_ROWS)
    if isinstance(agent, ExecutionError) or isinstance(gold, ExecutionError):
        return ExecutionScore(case.id, 0, response.status, attempts)
    matched = results_match(
        agent.rows,
        gold.rows,
        order_sensitive=case.order_sensitive,
        numeric_tolerance=case.numeric_tolerance,
    )
    return ExecutionScore(case.id, 1 if matched else 0, response.status, attempts)
