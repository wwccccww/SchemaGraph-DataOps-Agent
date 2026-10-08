"""慢 SQL 诊断的 LangGraph 状态机。它不调用问数工作流。"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict, cast
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.agents.slow_sql.metrics import drop, shared_buffer_access
from app.agents.slow_sql.plan import PlanNode, PlanSummary
from app.agents.slow_sql.autofix import try_autofix_sql
from app.agents.slow_sql.prompt import (
    SYSTEM_PROMPT,
    render_rewrite_prompt,
    render_rewrite_repair_prompt,
)
from app.agents.slow_sql.rules import Finding, diagnose_sql, finding_for_seq_scan
from app.agents.text_to_sql.prompt import extract_sql
from app.db.catalog import DATABASE_ID
from app.evaluation.ex import results_match
from app.llm.gateway import ChatModel
from app.observability.tracing import (
    RequestTrace,
    model_name_of,
    request_span,
    set_request_attributes,
    sql_hash,
)
from app.sandbox.errors import ExecutionError
from app.sandbox.execute import ExecutionSuccess
from app.sandbox.gate import check_read_only_sql
from app.schemas.slow_sql import (
    SlowSqlCandidate,
    SlowSqlFinding,
    SlowSqlPlan,
    SlowSqlResponse,
)
from app.schemas.text_to_sql import ApiError

logger = logging.getLogger(__name__)

EX_MAX_ROWS = 1000
REWRITE_TEMPERATURE = 0.0
MAX_REWRITE_ATTEMPTS = 2
SeverityName = Literal["high", "medium", "low"]


class Explainer(Protocol):
    """执行一条已经通过门禁的 SQL 的计划。"""

    async def __call__(self, sql: str, *, analyze: bool) -> PlanSummary | ExecutionError:
        """返回计划摘要或结构化错误。"""


class SqlExecutor(Protocol):
    """执行一条已经通过门禁的 SQL。"""

    async def __call__(self, sql: str, *, max_rows: int) -> ExecutionSuccess | ExecutionError:
        """返回结果或结构化错误。"""


class SlowSqlState(TypedDict):
    """一次诊断的图状态。默认不持久化。"""

    request_id: str
    database_id: str
    sql: str
    run_analyze: bool
    rewrite: bool
    order_sensitive: bool
    numeric_tolerance: float | None
    rendered_sql: str
    findings: list[dict[str, str]]
    plan_nodes: list[dict[str, object]]
    original_cost: float | None
    original_time_ms: float | None
    original_hit: int | None
    original_read: int | None
    candidate_sql: str | None
    last_candidate_sql: str | None
    equivalent: bool | None
    planner_cost_drop: float | None
    execution_time_drop: float | None
    shared_buffer_access_drop: float | None
    status: str
    error_category: str | None
    error_message: str | None
    error_retryable: bool
    error_hash: str
    generation_attempt: int


@dataclass(frozen=True)
class SlowSqlServices:
    """诊断依赖。测试注入模型和执行器，避免访问真实模型。"""

    model: ChatModel
    explain: Explainer
    execute: SqlExecutor


def build_graph(services: SlowSqlServices) -> Any:
    """编译诊断图。节点名对应架构里的诊断步骤。"""

    builder = StateGraph(SlowSqlState)
    builder.add_node("validate_sql", cast(Any, _validate_sql))
    builder.add_node("diagnose_static", cast(Any, _diagnose_static))
    builder.add_node("explain_plan", cast(Any, _explain_plan(services)))
    builder.add_node("rewrite_sql", cast(Any, _rewrite_sql(services)))
    builder.add_node("verify_equivalence", cast(Any, _verify_equivalence(services)))
    builder.add_node("compare_metrics", cast(Any, _compare_metrics(services)))
    builder.add_node("finish", cast(Any, _finish))
    builder.add_edge(START, "validate_sql")
    builder.add_conditional_edges(
        "validate_sql",
        _after_validate,
        {"diagnose_static": "diagnose_static", "finish": "finish"},
    )
    builder.add_edge("diagnose_static", "explain_plan")
    builder.add_conditional_edges(
        "explain_plan",
        _after_explain,
        {"rewrite_sql": "rewrite_sql", "finish": "finish"},
    )
    builder.add_conditional_edges(
        "rewrite_sql",
        _after_rewrite,
        {"verify_equivalence": "verify_equivalence", "finish": "finish"},
    )
    builder.add_conditional_edges(
        "verify_equivalence",
        _after_verify,
        {
            "compare_metrics": "compare_metrics",
            "rewrite_sql": "rewrite_sql",
            "finish": "finish",
        },
    )
    builder.add_edge("compare_metrics", "finish")
    builder.add_edge("finish", END)
    return builder.compile()


async def run_slow_sql(
    services: SlowSqlServices,
    *,
    sql: str,
    database_id: str,
    run_analyze: bool = True,
    rewrite: bool = True,
    order_sensitive: bool = False,
    numeric_tolerance: float | None = None,
    request_id: str | None = None,
) -> SlowSqlResponse:
    """诊断一条 SQL。评测阈值和参考改写不是参数。"""

    identifier = request_id or f"req_{uuid4().hex}"
    final: SlowSqlState | None = None
    with request_span("slow_sql") as span:
        try:
            graph: Any = build_graph(services)
            final = cast(
                SlowSqlState,
                await graph.ainvoke(
                    _initial_state(
                        request_id=identifier,
                        sql=sql,
                        database_id=database_id,
                        run_analyze=run_analyze,
                        rewrite=rewrite,
                        order_sensitive=order_sensitive,
                        numeric_tolerance=numeric_tolerance,
                    )
                ),
            )
            return _response(final)
        finally:
            set_request_attributes(span, _trace_fields(services, final))


def _initial_state(
    *,
    request_id: str,
    sql: str,
    database_id: str,
    run_analyze: bool,
    rewrite: bool,
    order_sensitive: bool,
    numeric_tolerance: float | None,
) -> SlowSqlState:
    return {
        "request_id": request_id,
        "database_id": database_id,
        "sql": sql,
        "run_analyze": run_analyze,
        "rewrite": rewrite,
        "order_sensitive": order_sensitive,
        "numeric_tolerance": numeric_tolerance,
        "rendered_sql": "",
        "findings": [],
        "plan_nodes": [],
        "original_cost": None,
        "original_time_ms": None,
        "original_hit": None,
        "original_read": None,
        "candidate_sql": None,
        "last_candidate_sql": None,
        "equivalent": None,
        "planner_cost_drop": None,
        "execution_time_drop": None,
        "shared_buffer_access_drop": None,
        "status": "running",
        "error_category": None,
        "error_message": None,
        "error_retryable": False,
        "error_hash": "",
        "generation_attempt": 0,
    }


async def _validate_sql(state: SlowSqlState) -> dict[str, object]:
    if state["database_id"] != DATABASE_ID:
        return _failure("unsupported_database", "当前只支持 ecommerce 数据库", False)
    decision = check_read_only_sql(state["sql"])
    if decision.error is not None:
        return _failure(
            decision.error.category,
            decision.error.normalized_message,
            decision.error.retryable,
            decision.error.error_hash,
        )
    return {"rendered_sql": decision.sql}


async def _diagnose_static(state: SlowSqlState) -> dict[str, object]:
    findings = diagnose_sql(state["rendered_sql"])
    return {"findings": [_finding_dict(item) for item in findings]}


def _explain_plan(
    services: SlowSqlServices,
) -> Callable[[SlowSqlState], Awaitable[dict[str, object]]]:
    async def node(state: SlowSqlState) -> dict[str, object]:
        outcome = await services.explain(state["rendered_sql"], analyze=state["run_analyze"])
        if isinstance(outcome, ExecutionError):
            return _failure(
                outcome.category,
                outcome.normalized_message,
                outcome.retryable,
                outcome.error_hash,
            )
        findings = list(state["findings"])
        scan = finding_for_seq_scan([(item.node_type, item.relation) for item in outcome.nodes])
        if scan is not None and all(item["rule_id"] != scan.rule_id for item in findings):
            findings.append(_finding_dict(scan))
        return {
            "findings": findings,
            "plan_nodes": [_node_dict(item) for item in outcome.nodes],
            "original_cost": outcome.total_cost,
            "original_time_ms": outcome.execution_time_ms,
            "original_hit": outcome.shared_hit_blocks,
            "original_read": outcome.shared_read_blocks,
        }

    return node


def _rewrite_sql(
    services: SlowSqlServices,
) -> Callable[[SlowSqlState], Awaitable[dict[str, object]]]:
    async def node(state: SlowSqlState) -> dict[str, object]:
        findings = tuple(_finding_from_state(item) for item in state["findings"])
        nodes = tuple(_node_from_state(item) for item in state["plan_nodes"])
        attempt = state["generation_attempt"] + 1
        candidate: str | None = None
        if attempt == 1 or (
            attempt > 1 and state.get("equivalent") is False and state.get("last_candidate_sql")
        ):
            candidate = try_autofix_sql(state["sql"], findings)
            if candidate is not None:
                decision = check_read_only_sql(candidate)
                candidate = None if decision.error is not None else decision.sql
        if candidate is None:
            previous = state.get("last_candidate_sql")
            if attempt > 1 and isinstance(previous, str):
                prompt = render_rewrite_repair_prompt(
                    sql=state["sql"],
                    previous_sql=previous,
                    findings=findings,
                    nodes=nodes,
                )
            else:
                prompt = render_rewrite_prompt(
                    sql=state["sql"],
                    findings=findings,
                    nodes=nodes,
                )
            try:
                content = await services.model.complete(
                    (
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ),
                    temperature=REWRITE_TEMPERATURE,
                )
            except Exception:
                logger.info("slow sql rewrite failed with %s", "model_error")
                return {"candidate_sql": None, "generation_attempt": attempt}
            decision = check_read_only_sql(extract_sql(content))
            if decision.error is not None:
                return {"candidate_sql": None, "generation_attempt": attempt}
            candidate = decision.sql
        return {
            "candidate_sql": candidate,
            "last_candidate_sql": candidate,
            "generation_attempt": attempt,
        }

    return node


def _verify_equivalence(
    services: SlowSqlServices,
) -> Callable[[SlowSqlState], Awaitable[dict[str, object]]]:
    async def node(state: SlowSqlState) -> dict[str, object]:
        candidate_sql = state["candidate_sql"]
        if candidate_sql is None:
            return {"equivalent": False}
        original = await services.execute(state["rendered_sql"], max_rows=EX_MAX_ROWS)
        rewritten = await services.execute(candidate_sql, max_rows=EX_MAX_ROWS)
        if isinstance(original, ExecutionError) or isinstance(rewritten, ExecutionError):
            return {"equivalent": False}
        matched = results_match(
            original.rows,
            rewritten.rows,
            order_sensitive=state["order_sensitive"],
            numeric_tolerance=state["numeric_tolerance"],
        )
        return {"equivalent": matched}

    return node


def _compare_metrics(
    services: SlowSqlServices,
) -> Callable[[SlowSqlState], Awaitable[dict[str, object]]]:
    async def node(state: SlowSqlState) -> dict[str, object]:
        candidate_sql = state["candidate_sql"]
        raw_cost = state["original_cost"]
        if candidate_sql is None or raw_cost is None:
            return {}
        outcome = await services.explain(candidate_sql, analyze=state["run_analyze"])
        if isinstance(outcome, ExecutionError):
            return {}
        time_drop = _optional_drop(state["original_time_ms"], outcome.execution_time_ms)
        buffer_drop = _buffer_drop(state, outcome)
        return {
            "planner_cost_drop": drop(raw_cost, outcome.total_cost),
            "execution_time_drop": time_drop,
            "shared_buffer_access_drop": buffer_drop,
        }

    return node


async def _finish(state: SlowSqlState) -> dict[str, object]:
    if state["status"] == "failed":
        return {}
    return {"status": "succeeded"}


def _after_validate(state: SlowSqlState) -> str:
    if state["status"] == "failed":
        return "finish"
    return "diagnose_static"


def _after_explain(state: SlowSqlState) -> str:
    if state["status"] == "failed" or not state["rewrite"]:
        return "finish"
    return "rewrite_sql"


def _after_rewrite(state: SlowSqlState) -> str:
    if state["candidate_sql"] is None:
        return "finish"
    return "verify_equivalence"


def _after_verify(state: SlowSqlState) -> str:
    if state["equivalent"] is True:
        return "compare_metrics"
    if state["generation_attempt"] < MAX_REWRITE_ATTEMPTS:
        return "rewrite_sql"
    return "finish"


def _failure(
    category: str,
    message: str,
    retryable: bool,
    error_hash: str | None = None,
) -> dict[str, object]:
    return {
        "status": "failed",
        "error_category": category,
        "error_message": message,
        "error_retryable": retryable,
        "error_hash": error_hash or "",
    }


def _optional_drop(raw: float | None, optimized: float | None) -> float | None:
    if raw is None or optimized is None:
        return None
    return drop(raw, optimized)


def _buffer_drop(state: SlowSqlState, outcome: PlanSummary) -> float | None:
    raw_hit = state["original_hit"]
    raw_read = state["original_read"]
    if (
        raw_hit is None
        or raw_read is None
        or outcome.shared_hit_blocks is None
        or outcome.shared_read_blocks is None
    ):
        return None
    return drop(
        float(shared_buffer_access(raw_hit, raw_read)),
        float(shared_buffer_access(outcome.shared_hit_blocks, outcome.shared_read_blocks)),
    )


def _finding_dict(finding: Finding) -> dict[str, str]:
    return {
        "rule_id": finding.rule_id,
        "severity": finding.severity,
        "message": finding.message,
    }


def _finding_from_state(item: dict[str, str]) -> Finding:
    return Finding(
        rule_id=item["rule_id"],
        severity=_severity(item["severity"]),
        message=item["message"],
    )


def _severity(value: str) -> SeverityName:
    if value == "medium":
        return "medium"
    if value == "low":
        return "low"
    return "high"


def _node_dict(node: PlanNode) -> dict[str, object]:
    return {
        "node_type": node.node_type,
        "relation": node.relation,
        "total_cost": node.total_cost,
    }


def _node_from_state(item: dict[str, object]) -> PlanNode:
    relation = item.get("relation")
    cost = item.get("total_cost")
    return PlanNode(
        node_type=str(item.get("node_type") or ""),
        relation=relation if isinstance(relation, str) else None,
        total_cost=float(cost) if isinstance(cost, int | float) else 0.0,
    )


def _trace_fields(services: SlowSqlServices, state: SlowSqlState | None) -> RequestTrace:
    if state is None:
        return _empty_trace(services)
    cost = state["original_cost"]
    elapsed = state["original_time_ms"]
    return {
        "request_type": "slow_sql",
        "model_name": model_name_of(services.model),
        "retrieved_seed_tables": (),
        "expanded_tables": (),
        "schema_context_tokens": 0,
        "selected_tools": (),
        "generation_attempt": state["generation_attempt"],
        "sql_hash": sql_hash(_traced_sql(state)),
        "error_hash": state["error_hash"],
        "db_execution_ms": 0.0 if elapsed is None else elapsed,
        "planner_total_cost": 0.0 if cost is None else cost,
        "result_row_count": 0,
        "circuit_breaker_triggered": False,
    }


def _empty_trace(services: SlowSqlServices) -> RequestTrace:
    return {
        "request_type": "slow_sql",
        "model_name": model_name_of(services.model),
        "retrieved_seed_tables": (),
        "expanded_tables": (),
        "schema_context_tokens": 0,
        "selected_tools": (),
        "generation_attempt": 0,
        "sql_hash": "",
        "error_hash": "",
        "db_execution_ms": 0.0,
        "planner_total_cost": 0.0,
        "result_row_count": 0,
        "circuit_breaker_triggered": False,
    }


def _traced_sql(state: SlowSqlState) -> str:
    if state["candidate_sql"]:
        return state["candidate_sql"]
    if state["rendered_sql"]:
        return state["rendered_sql"]
    return state["sql"]


def _response(state: SlowSqlState) -> SlowSqlResponse:
    findings = [
        SlowSqlFinding(
            rule_id=item["rule_id"],
            severity=_severity(item["severity"]),
            message=item["message"],
        )
        for item in state["findings"]
    ]
    if state["status"] != "succeeded":
        return SlowSqlResponse(
            request_id=state["request_id"],
            status="failed",
            findings=findings,
            error=ApiError(
                category=state["error_category"] or "diagnostic_failed",
                message=state["error_message"] or "慢 SQL 诊断失败",
                retryable=state["error_retryable"],
            ),
        )
    plan = None
    if state["original_cost"] is not None:
        plan = SlowSqlPlan(
            total_cost=state["original_cost"],
            execution_time_ms=state["original_time_ms"],
            shared_hit_blocks=state["original_hit"],
            shared_read_blocks=state["original_read"],
        )
    candidate = None
    if state["candidate_sql"] is not None:
        candidate = SlowSqlCandidate(
            sql=state["candidate_sql"],
            equivalent=state["equivalent"] is True,
            planner_cost_drop=state["planner_cost_drop"],
            execution_time_drop=state["execution_time_drop"],
            shared_buffer_access_drop=state["shared_buffer_access_drop"],
        )
    return SlowSqlResponse(
        request_id=state["request_id"],
        status="succeeded",
        findings=findings,
        original_plan=plan,
        candidate=candidate,
    )
