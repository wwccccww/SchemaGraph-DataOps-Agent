"""慢 SQL 冒烟用例的隔离测量。参考改写不在用例文件里。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.agents.slow_sql.metrics import (
    PrimaryMetric,
    drop,
    is_optimize_success,
    shared_buffer_access,
)
from app.agents.slow_sql.plan import PlanSummary
from app.agents.slow_sql.runtime import build_slow_sql_services_with_context
from app.agents.slow_sql.snapshot import (
    create_case_database,
    create_loaded_snapshot,
    drop_database,
    index_exists,
    validate_index_precondition,
)
from app.agents.slow_sql.workflow import run_slow_sql
from app.config.settings import Settings
from app.db.catalog import DATABASE_ID
from app.llm.gateway import ChatModel
from app.sandbox.errors import ExecutionError
from app.sandbox.explain import explain_readonly

SMOKE_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "slow_sql" / "smoke.yaml"
MEASUREMENT_RUNS = 5
_SNAPSHOT_VERSION = "ecommerce-v1"


class SlowSqlCase(BaseModel):
    """一条慢 SQL 冒烟用例。字段里没有参考改写。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
    snapshot_version: str
    database_id: str
    antipattern: str
    sql: str = Field(min_length=1)
    index_preconditions: list[str] = Field(default_factory=list)
    primary_metric: PrimaryMetric = "planner_cost"
    min_primary_drop: float = Field(ge=0)
    max_secondary_regression: float = Field(ge=0)
    order_sensitive: bool
    numeric_tolerance: float | None
    timeout_ms: int = Field(gt=0)


@dataclass(frozen=True)
class SlowSqlScore:
    """一条用例的诊断和测量结果。"""

    case_id: str
    findings: tuple[str, ...]
    equivalent: bool
    optimize_success: bool
    planner_cost_drop: float | None
    execution_time_drop: float | None
    shared_buffer_access_drop: float | None
    isolated: bool
    detail: str


@dataclass(frozen=True)
class _Measurement:
    total_cost: float
    execution_time_ms: float
    shared_hit_blocks: int
    shared_read_blocks: int


def load_slow_sql_cases(path: Path | None = None) -> list[SlowSqlCase]:
    """读取慢 SQL 冒烟用例，并先校验索引前置条件。"""

    payload = yaml.safe_load((path or SMOKE_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("contract_version") != "1.0":
        raise ValueError("slow sql smoke file must declare contract_version 1.0")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("slow sql smoke file must contain a cases list")
    cases = [SlowSqlCase.model_validate(item) for item in raw_cases]
    loaded: list[SlowSqlCase] = []
    for case in cases:
        if case.snapshot_version != _SNAPSHOT_VERSION or case.database_id != DATABASE_ID:
            raise ValueError("slow sql case must use the ecommerce-v1 snapshot")
        preconditions = [validate_index_precondition(item) for item in case.index_preconditions]
        loaded.append(case.model_copy(update={"index_preconditions": preconditions}))
    return loaded


async def score_slow_sql_cases(
    cases: Sequence[SlowSqlCase],
    model: ChatModel,
    settings: Settings,
) -> list[SlowSqlScore]:
    """复制一次快照，再为每条用例克隆独立数据库。"""

    snapshot = await create_loaded_snapshot(settings)
    try:
        return [await _score_case(case, model, settings, snapshot) for case in cases]
    finally:
        await drop_database(settings, snapshot)


async def _score_case(
    case: SlowSqlCase,
    model: ChatModel,
    settings: Settings,
    snapshot: str,
) -> SlowSqlScore:
    await create_case_database(
        settings,
        case.id,
        snapshot=snapshot,
        index_preconditions=case.index_preconditions,
    )
    engine = create_async_engine(
        settings.sandbox_url().set(database=case.id),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SET max_parallel_workers_per_gather = 0")
            await conn.commit()
            response = await run_slow_sql(
                await build_slow_sql_services_with_context(model, connection=conn),
                sql=case.sql,
                database_id=case.database_id,
                run_analyze=True,
                rewrite=True,
                order_sensitive=case.order_sensitive,
                numeric_tolerance=case.numeric_tolerance,
            )
            isolated = await _index_isolated(settings, case)
            findings = tuple(item.rule_id for item in response.findings)
            if response.status != "succeeded" or response.candidate is None:
                message = response.error.message if response.error is not None else "没有改写候选"
                return _score(case, findings, False, False, None, None, None, isolated, message)
            if not response.candidate.equivalent:
                return _score(
                    case,
                    findings,
                    False,
                    False,
                    None,
                    None,
                    None,
                    isolated,
                    "改写结果未通过语义 EX",
                )
            try:
                raw, optimized = await _measure_pair(conn, case.sql, response.candidate.sql)
            except RuntimeError as exc:
                return _score(case, findings, True, False, None, None, None, isolated, str(exc))
            return _measured_score(case, findings, isolated, raw, optimized)
    finally:
        await engine.dispose()
        await drop_database(settings, case.id)
    raise RuntimeError("slow sql case ended without a score")


async def _measure_pair(
    conn: AsyncConnection,
    original_sql: str,
    candidate_sql: str,
) -> tuple[_Measurement, _Measurement]:
    await _sample(conn, original_sql)
    await _sample(conn, candidate_sql)
    original_samples: list[_Measurement] = []
    candidate_samples: list[_Measurement] = []
    for _ in range(MEASUREMENT_RUNS):
        original_samples.append(await _sample(conn, original_sql))
        candidate_samples.append(await _sample(conn, candidate_sql))
    return _median(original_samples), _median(candidate_samples)


async def _sample(conn: AsyncConnection, sql: str) -> _Measurement:
    outcome = await explain_readonly(sql, analyze=True, connection=conn)
    if isinstance(outcome, ExecutionError):
        raise RuntimeError(outcome.normalized_message)
    measurement = _measurement(outcome)
    if measurement is None:
        raise RuntimeError("执行计划缺少运行时间或 Buffer")
    return measurement


def _measurement(summary: PlanSummary) -> _Measurement | None:
    if (
        summary.execution_time_ms is None
        or summary.shared_hit_blocks is None
        or summary.shared_read_blocks is None
    ):
        return None
    return _Measurement(
        total_cost=summary.total_cost,
        execution_time_ms=summary.execution_time_ms,
        shared_hit_blocks=summary.shared_hit_blocks,
        shared_read_blocks=summary.shared_read_blocks,
    )


def _median(samples: Sequence[_Measurement]) -> _Measurement:
    ordered = sorted(samples, key=lambda item: item.execution_time_ms)
    return ordered[len(ordered) // 2]


async def _index_isolated(settings: Settings, case: SlowSqlCase) -> bool:
    for statement in case.index_preconditions:
        if "idx_order_status" not in statement or not statement.upper().startswith("DROP INDEX"):
            continue
        clone_has = await index_exists(settings, "idx_order_status", database=case.id)
        source_has = await index_exists(settings, "idx_order_status")
        return (not clone_has) and source_has
    return True


def _measured_score(
    case: SlowSqlCase,
    findings: tuple[str, ...],
    isolated: bool,
    raw: _Measurement,
    optimized: _Measurement,
) -> SlowSqlScore:
    planner = drop(raw.total_cost, optimized.total_cost)
    elapsed = drop(raw.execution_time_ms, optimized.execution_time_ms)
    buffers = drop(
        float(shared_buffer_access(raw.shared_hit_blocks, raw.shared_read_blocks)),
        float(shared_buffer_access(optimized.shared_hit_blocks, optimized.shared_read_blocks)),
    )
    values = {
        "planner_cost": planner,
        "execution_time": elapsed,
        "shared_buffer_access": buffers,
    }
    success = is_optimize_success(
        read_only=True,
        equivalent=True,
        primary_drop=values[case.primary_metric],
        secondary_drops={
            name: value for name, value in values.items() if name != case.primary_metric
        },
        min_primary_drop=case.min_primary_drop,
        max_secondary_regression=case.max_secondary_regression,
        breached_limits=False,
    )
    detail = (
        f"cost {raw.total_cost:.2f}->{optimized.total_cost:.2f} "
        f"time {raw.execution_time_ms:.2f}->{optimized.execution_time_ms:.2f}"
    )
    return _score(case, findings, True, success, planner, elapsed, buffers, isolated, detail)


def _score(
    case: SlowSqlCase,
    findings: tuple[str, ...],
    equivalent: bool,
    optimize_success: bool,
    planner_cost_drop: float | None,
    execution_time_drop: float | None,
    shared_buffer_access_drop: float | None,
    isolated: bool,
    detail: str,
) -> SlowSqlScore:
    return SlowSqlScore(
        case_id=case.id,
        findings=findings,
        equivalent=equivalent,
        optimize_success=optimize_success,
        planner_cost_drop=planner_cost_drop,
        execution_time_drop=execution_time_drop,
        shared_buffer_access_drop=shared_buffer_access_drop,
        isolated=isolated,
        detail=detail,
    )
