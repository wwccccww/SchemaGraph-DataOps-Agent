"""Text-to-SQL 的 LangGraph 状态机。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict, cast
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.agents.text_to_sql.contract import (
    AnswerContract,
    check_contract,
    extract_answer_contract,
    format_query_plan,
)
from app.agents.text_to_sql.prompt import (
    extract_sql,
    render_generation_prompt,
    render_repair_prompt,
    system_prompt_for,
)
from app.agents.text_to_sql.semantic import (
    SemanticFinding,
    check_catalog_sql,
    check_cte_outputs,
    check_semantics,
)
from app.agents.text_to_sql.shape import (
    check_answer_shape,
    extract_generic_shape,
    format_generic_shape,
)
from app.datasources.registry import resolve_data_source
from app.graph.expand import (
    DEFAULT_MAX_TOTAL_TABLES,
    TokenCounter,
    attach_neighbor_tables,
    expand_schema,
    render_schema_context,
)
from app.llm.gateway import ChatModel
from app.observability.tracing import (
    RequestTrace,
    model_name_of,
    request_span,
    set_request_attributes,
    sql_hash,
)
from app.sandbox.errors import ExecutionError, make_error
from app.sandbox.execute import ExecutionSuccess
from app.sandbox.gate import check_read_only_sql
from app.schemas.catalog import SchemaEdge, TableDocument
from app.schemas.retrieval import SchemaSeed, ToolHit
from app.schemas.text_to_sql import (
    ApiError,
    JsonValue,
    SchemaContextView,
    TextToSqlResponse,
    json_rows,
)

MAX_RECOVERY_ROUNDS = 3
MAX_MODEL_CALLS = 1 + MAX_RECOVERY_ROUNDS
CIRCUIT_THRESHOLD = 3
GENERATION_TEMPERATURE = 0.0
TextToSqlVariant = Literal["zero_shot", "schema_rag", "schema_graph", "self_healing"]
TEXT_TO_SQL_VARIANTS: tuple[TextToSqlVariant, ...] = (
    "zero_shot",
    "schema_rag",
    "schema_graph",
    "self_healing",
)
ZERO_SHOT_SCHEMA = "PostgreSQL 数据库 ecommerce，schema 为 public。只生成一条只读 SELECT。"

Catalog = tuple[Sequence[TableDocument], Sequence[SchemaEdge]]


class SqlExecutor(Protocol):
    """执行一条已经通过门禁的 SQL。"""

    async def __call__(self, sql: str, *, max_rows: int) -> ExecutionSuccess | ExecutionError:
        """返回结果或结构化错误。"""


class PlanRowEstimator(Protocol):
    """读取 EXPLAIN 的计划行数。失败时返回 None。"""

    async def __call__(self, sql: str) -> float | None:
        """返回根节点的 Plan Rows。"""


class TextToSqlState(TypedDict):
    """一次问数的图状态。默认不持久化。"""

    request_id: str
    question: str
    database_id: str
    variant: str
    execute: bool
    max_rows: int
    selected_tools: list[dict[str, object]]
    seed_tables: list[str]
    expanded_tables: list[str]
    schema_context: str
    schema_token_count: int
    truncated: bool
    prompt: str
    generated_sql: str | None
    attempt: int
    consecutive_error_hash: str | None
    consecutive_error_count: int
    status: str
    columns: list[str]
    rows: list[list[JsonValue]]
    error_category: str | None
    error_message: str | None
    error_retryable: bool
    circuit_breaker_triggered: bool
    db_execution_ms: float | None
    anchor_date: str
    dialect: str
    profile: str
    schema_name: str
    contract_repairs: int
    repair_trace: list[dict[str, object]]
    join_paths: list[str]
    initial_sql: str
    candidate_sql: str | None
    candidate_columns: list[str]
    candidate_rows: list[list[JsonValue]]
    candidate_score: int
    candidate_execution_ms: float | None


@dataclass(frozen=True)
class ServiceBundle:
    model: ChatModel
    select_tools: Callable[[str], Awaitable[Sequence[ToolHit]]]
    select_seeds: Callable[[str], Awaitable[Sequence[SchemaSeed]]]
    load_catalog: Callable[[], Awaitable[Catalog]]
    execute: SqlExecutor
    token_counter: TokenCounter
    estimate_plan_rows: PlanRowEstimator | None = None
    database_id: str = "ecommerce"


def build_graph(services: ServiceBundle) -> Any:
    """编译问数图。节点名与架构文档一致。"""

    bound = ServiceBundle(
        model=services.model,
        select_tools=services.select_tools,
        select_seeds=services.select_seeds,
        load_catalog=services.load_catalog,
        execute=services.execute,
        token_counter=services.token_counter,
        estimate_plan_rows=services.estimate_plan_rows,
        database_id=services.database_id,
    )
    builder = StateGraph(TextToSqlState)
    builder.add_node("route_tools", cast(Any, _route_tools(bound)))
    builder.add_node("retrieve_schema", cast(Any, _retrieve_schema(bound)))
    builder.add_node("expand_schema_graph", cast(Any, _expand_schema_graph(bound)))
    builder.add_node("build_prompt", cast(Any, _build_prompt(bound)))
    builder.add_node("generate_sql", cast(Any, _generate_sql(bound)))
    builder.add_node("validate_sql", cast(Any, _validate_sql(bound)))
    builder.add_node("execute_sql", cast(Any, _execute_sql(bound)))
    builder.add_node("repair_sql", cast(Any, _repair_sql(bound)))
    builder.add_node("finish", cast(Any, _finish))
    builder.add_edge(START, "route_tools")
    builder.add_edge("route_tools", "retrieve_schema")
    builder.add_edge("retrieve_schema", "expand_schema_graph")
    builder.add_conditional_edges(
        "expand_schema_graph",
        _after_expand,
        {"build_prompt": "build_prompt", "finish": "finish"},
    )
    builder.add_edge("build_prompt", "generate_sql")
    builder.add_edge("generate_sql", "validate_sql")
    builder.add_conditional_edges(
        "validate_sql",
        _after_validate,
        {"execute_sql": "execute_sql", "repair_sql": "repair_sql", "finish": "finish"},
    )
    builder.add_conditional_edges(
        "execute_sql",
        _after_execute,
        {"repair_sql": "repair_sql", "finish": "finish"},
    )
    builder.add_edge("repair_sql", "validate_sql")
    builder.add_edge("finish", END)
    return builder.compile()


@dataclass(frozen=True)
class TextToSqlInspection:
    """问数响应，以及最后一条预测 SQL。失败响应本身仍不携带 SQL。"""

    response: TextToSqlResponse
    generated_sql: str | None
    repair_trace: tuple[dict[str, object], ...] = ()
    prompt: str = ""


async def run_text_to_sql(
    services: ServiceBundle,
    *,
    question: str,
    database_id: str,
    execute: bool = True,
    max_rows: int = 1000,
    request_id: str | None = None,
    variant: TextToSqlVariant = "self_healing",
    anchor_date: str = "2026-10-01",
) -> TextToSqlResponse:
    """运行一次问数。评测标签和 Gold SQL 不是参数。默认走自愈。"""

    inspection = await inspect_text_to_sql(
        services,
        question=question,
        database_id=database_id,
        execute=execute,
        max_rows=max_rows,
        request_id=request_id,
        variant=variant,
        anchor_date=anchor_date,
    )
    return inspection.response


async def inspect_text_to_sql(
    services: ServiceBundle,
    *,
    question: str,
    database_id: str,
    execute: bool = True,
    max_rows: int = 1000,
    request_id: str | None = None,
    variant: TextToSqlVariant = "self_healing",
    anchor_date: str = "2026-10-01",
    initial_sql: str | None = None,
) -> TextToSqlInspection:
    """运行一次问数，并保留最后一条预测 SQL 供本地评测诊断。"""

    identifier = request_id or f"req_{uuid4().hex}"
    if variant not in TEXT_TO_SQL_VARIANTS:
        raise ValueError(f"unknown text-to-sql variant: {variant}")
    final: TextToSqlState | None = None
    with request_span("text_to_sql") as span:
        try:
            source = resolve_data_source(database_id)
            if source is None:
                return TextToSqlInspection(
                    response=TextToSqlResponse(
                        request_id=identifier,
                        status="failed",
                        attempts=0,
                        error=ApiError(
                            category="unsupported_database",
                            message="当前只支持 ecommerce 数据库",
                            retryable=False,
                        ),
                    ),
                    generated_sql=None,
                )
            if services.database_id != database_id:
                return _catalog_rejection(identifier)
            graph = cast(CompiledGraph, build_graph(services))
            final = await graph.ainvoke(
                _initial_state(
                    request_id=identifier,
                    question=question,
                    database_id=database_id,
                    variant=variant,
                    execute=execute,
                    max_rows=max_rows,
                    anchor_date=anchor_date,
                    initial_sql=initial_sql or "",
                    dialect=source.dialect,
                    profile=source.profile,
                    schema_name=source.schema_name,
                )
            )
            return TextToSqlInspection(
                response=_response(final),
                generated_sql=final["generated_sql"],
                repair_trace=tuple(final["repair_trace"]),
                prompt=final["prompt"],
            )
        finally:
            set_request_attributes(span, _trace_fields(services, final))


class CompiledGraph(Protocol):
    """ainvoke 的最小调用面。"""

    async def ainvoke(self, state: TextToSqlState) -> TextToSqlState:
        """运行到结束节点。"""


def _initial_state(
    *,
    request_id: str,
    question: str,
    database_id: str,
    variant: str,
    execute: bool,
    max_rows: int,
    anchor_date: str,
    initial_sql: str,
    dialect: str,
    profile: str,
    schema_name: str,
) -> TextToSqlState:
    return {
        "request_id": request_id,
        "question": question,
        "database_id": database_id,
        "variant": variant,
        "execute": execute,
        "max_rows": max_rows,
        "selected_tools": [],
        "seed_tables": [],
        "expanded_tables": [],
        "schema_context": "",
        "schema_token_count": 0,
        "truncated": False,
        "prompt": "",
        "generated_sql": None,
        "attempt": 0,
        "consecutive_error_hash": None,
        "consecutive_error_count": 0,
        "status": "running",
        "columns": [],
        "rows": [],
        "error_category": None,
        "error_message": None,
        "error_retryable": False,
        "circuit_breaker_triggered": False,
        "db_execution_ms": None,
        "anchor_date": anchor_date,
        "dialect": dialect,
        "profile": profile,
        "schema_name": schema_name,
        "contract_repairs": 0,
        "repair_trace": [],
        "join_paths": [],
        "initial_sql": initial_sql,
        "candidate_sql": None,
        "candidate_columns": [],
        "candidate_rows": [],
        "candidate_score": 0,
        "candidate_execution_ms": None,
    }


def _route_tools(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def route_tools(state: TextToSqlState) -> dict[str, object]:
        if state["variant"] == "zero_shot":
            return {"selected_tools": []}
        tools = await services.select_tools(state["question"])
        return {"selected_tools": [_tool_payload(tool) for tool in tools]}

    return route_tools


def _retrieve_schema(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def retrieve_schema(state: TextToSqlState) -> dict[str, object]:
        if state["variant"] == "zero_shot":
            return {"seed_tables": []}
        seeds = await services.select_seeds(state["question"])
        return {"seed_tables": [seed.table_name for seed in seeds]}

    return retrieve_schema


def _expand_schema_graph(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def expand_schema_graph(state: TextToSqlState) -> dict[str, object]:
        if state["variant"] == "zero_shot":
            schema = _zero_shot_schema(state)
            return {
                "status": "running",
                "seed_tables": [],
                "expanded_tables": [],
                "schema_context": schema,
                "schema_token_count": services.token_counter.count(schema),
                "truncated": False,
            }
        if not state["seed_tables"]:
            return _fail("no_schema_seed", "没有检索到实体种子表", retryable=False)
        documents, edges = await services.load_catalog()
        if _catalog_mismatch(documents, state["database_id"]):
            return _fail("cross_database_catalog", "检索到的表不属于当前数据库", retryable=False)
        by_name = {document.table_name: document for document in documents}
        if any(name not in by_name or by_name[name].is_junction for name in state["seed_tables"]):
            return _fail("junction_seed_leak", "种子结果包含不可用的表", retryable=False)
        if state["variant"] == "schema_rag":
            selected = [by_name[name] for name in state["seed_tables"]]
            context = _visible_schema(state, render_schema_context(selected, edges))
            return {
                "status": "running",
                "seed_tables": list(state["seed_tables"]),
                "expanded_tables": [],
                "schema_context": context,
                "schema_token_count": services.token_counter.count(context),
                "truncated": False,
                "join_paths": _join_paths(edges, state["seed_tables"]),
            }
        result = expand_schema(
            documents,
            edges,
            state["seed_tables"],
            question=state["question"] if state["profile"] == "ecommerce" else None,
            token_counter=services.token_counter,
        )
        if not result.connected and state["profile"] != "ecommerce":
            names = _with_neighbors(
                documents,
                edges,
                list(result.seed_tables)[:DEFAULT_MAX_TOTAL_TABLES],
                services.token_counter,
                state["question"],
            )
            selected = [by_name[name] for name in names if name in by_name]
            context = _visible_schema(state, render_schema_context(selected, edges))
            return {
                "status": "running",
                "seed_tables": [name for name in names if name in result.seed_tables],
                "expanded_tables": [name for name in names if name not in result.seed_tables],
                "schema_context": context,
                "schema_token_count": services.token_counter.count(context),
                "truncated": len(names) >= DEFAULT_MAX_TOTAL_TABLES,
                "join_paths": _join_paths(edges, names),
            }
        if not result.connected:
            diagnostic = result.diagnostic
            code = diagnostic.code if diagnostic is not None else "no_path"
            message = diagnostic.message if diagnostic is not None else "Schema 扩展失败"
            category = "schema_path_budget_exceeded" if code == "budget_exceeded" else code
            return {
                **_fail(category, message, retryable=False),
                "seed_tables": list(result.seed_tables),
                "expanded_tables": [],
                "schema_token_count": result.context_tokens,
                "truncated": result.context_truncated,
            }
        base_names = [
            name for name in (*result.seed_tables, *result.expanded_tables) if name in by_name
        ]
        if state["profile"] != "ecommerce":
            base_names = _with_neighbors(
                documents,
                edges,
                base_names,
                services.token_counter,
                state["question"],
            )
        selected = [by_name[name] for name in base_names if name in by_name]
        context = _visible_schema(state, render_schema_context(selected, result.edges))
        selected_names = [document.table_name for document in selected]
        expanded_names = [name for name in selected_names if name not in result.seed_tables]
        return {
            "status": "running",
            "seed_tables": list(result.seed_tables),
            "expanded_tables": expanded_names,
            "schema_context": context,
            "schema_token_count": services.token_counter.count(context),
            "truncated": result.context_truncated,
            "join_paths": _join_paths(result.edges, selected_names),
        }

    return expand_schema_graph


def _build_prompt(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def build_prompt(state: TextToSqlState) -> dict[str, object]:
        contract = _contract(state)
        return {
            "prompt": render_generation_prompt(
                question=state["question"],
                schema_context=state["schema_context"],
                tools=_tools(state),
                contract=contract,
                plan=_plan(contract, state),
                output_shape=await _output_shape(services, state),
            )
        }

    return build_prompt


def _generate_sql(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def generate_sql(state: TextToSqlState) -> dict[str, object]:
        preset = state["initial_sql"].strip()
        if state["attempt"] == 0 and preset:
            return {"generated_sql": preset, "attempt": 1, "initial_sql": ""}
        content = await services.model.complete(
            _messages(state, state["prompt"]),
            temperature=GENERATION_TEMPERATURE,
        )
        return {"generated_sql": extract_sql(content), "attempt": state["attempt"] + 1}

    return generate_sql


def _validate_sql(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def validate_sql(state: TextToSqlState) -> dict[str, object]:
        decision = check_read_only_sql(state["generated_sql"] or "", dialect=state["dialect"])
        if decision.error is not None:
            return _fail_or_restore(state, _hinted(state, decision.error))
        findings = list(check_cte_outputs(decision.sql, dialect=state["dialect"]))
        if state["profile"] != "ecommerce":
            documents, _edges = await services.load_catalog()
            if _catalog_mismatch(documents, state["database_id"]):
                return _fail_or_restore(state, _catalog_error())
            findings.extend(check_catalog_sql(decision.sql, documents, dialect=state["dialect"]))
            if (
                state["variant"] == "self_healing"
                and state["profile"] != "ecommerce"
                and state["attempt"] >= 1
            ) or (
                state["variant"] == "self_healing"
                and state["profile"] == "ecommerce"
                and state["attempt"] > 1
            ):
                findings.extend(
                    check_answer_shape(
                        state["question"],
                        decision.sql,
                        _selected_documents(documents, state),
                        dialect=state["dialect"],
                        edges=_edges,
                    )
                )
        if (
            state["profile"] == "ecommerce"
            and state["variant"] == "self_healing"
            and state["attempt"] > 1
        ):
            findings.extend(
                check_contract(
                    question=state["question"],
                    sql=decision.sql,
                    anchor_date=state["anchor_date"],
                )
            )
        findings = _actionable_findings(findings)
        if findings:
            return _fail_or_restore(state, _review_error(findings))
        return {"status": "validated", "generated_sql": decision.sql}

    return validate_sql


def _execute_sql(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def execute_sql(state: TextToSqlState) -> dict[str, object]:
        sql = state["generated_sql"] or ""
        outcome = await services.execute(sql, max_rows=state["max_rows"])
        if isinstance(outcome, ExecutionError):
            return _fail_or_restore(state, _hinted(state, outcome))
        success = {
            "status": "succeeded",
            "columns": [name for name, _database_type in outcome.columns],
            "rows": json_rows(outcome.rows),
            "db_execution_ms": outcome.execution_time_ms,
            "error_category": None,
            "error_message": None,
            "error_retryable": False,
        }
        if state["variant"] != "self_healing":
            return success
        documents, edges = await services.load_catalog()
        if _catalog_mismatch(documents, state["database_id"]):
            return _fail_or_restore(state, _catalog_error())
        plan_rows = None
        if services.estimate_plan_rows is not None:
            plan_rows = await services.estimate_plan_rows(sql)
        if state["profile"] != "ecommerce":
            findings_shape = check_answer_shape(
                state["question"],
                sql,
                _selected_documents(documents, state),
                dialect=state["dialect"],
                edges=edges,
            )
        else:
            findings_shape = ()
        findings = list(
            check_semantics(
                question=state["question"],
                sql=sql,
                documents=documents,
                edges=edges,
                selected_tables=[*state["seed_tables"], *state["expanded_tables"]],
                row_count=outcome.row_count,
                truncated=outcome.truncated,
                max_rows=state["max_rows"],
                plan_rows=plan_rows,
                business_rules=state["profile"] == "ecommerce",
                dialect=state["dialect"],
            )
        )
        findings.extend(findings_shape)
        if state["profile"] == "ecommerce":
            findings.extend(
                check_contract(
                    question=state["question"],
                    sql=sql,
                    anchor_date=state["anchor_date"],
                )
            )
        findings = _actionable_findings(findings)
        if not findings:
            if state["repair_trace"]:
                success["repair_trace"] = [
                    *state["repair_trace"],
                    {
                        "attempt": state["attempt"],
                        "category": "accepted",
                        "symptom": "",
                        "sql_hash": sql_hash(sql),
                    },
                ]
            return success
        return _fail_or_restore(
            state,
            _review_error(findings),
            outcome=outcome,
            score=_execution_score(len(findings)),
        )

    return execute_sql


def _repair_sql(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def repair_sql(state: TextToSqlState) -> dict[str, object]:
        contract = _contract(state)
        prompt = render_repair_prompt(
            question=state["question"],
            schema_context=state["schema_context"],
            tools=_tools(state),
            previous_sql=state["generated_sql"] or "",
            error_category=state["error_category"] or "",
            error_message=state["error_message"] or "",
            contract=contract,
            plan=_plan(contract, state),
            output_shape=await _output_shape(services, state),
        )
        content = await services.model.complete(
            _messages(state, prompt),
            temperature=GENERATION_TEMPERATURE,
        )
        return {
            "prompt": prompt,
            "generated_sql": extract_sql(content),
            "attempt": state["attempt"] + 1,
            "status": "running",
        }

    return repair_sql


async def _finish(state: TextToSqlState) -> dict[str, object]:
    if state["status"] == "validated":
        return {"status": "succeeded", "columns": [], "rows": []}
    return {}


def _after_expand(state: TextToSqlState) -> str:
    if state["status"] == "failed":
        return "finish"
    return "build_prompt"


def _after_validate(state: TextToSqlState) -> str:
    if state["status"] == "validated":
        return "execute_sql" if state["execute"] else "finish"
    if state["status"] == "succeeded":
        return "finish"
    return _failure_target(state)


def _after_execute(state: TextToSqlState) -> str:
    if state["status"] == "succeeded":
        return "finish"
    return _failure_target(state)


def _failure_target(state: TextToSqlState) -> str:
    if state["variant"] != "self_healing":
        return "finish"
    if state["circuit_breaker_triggered"] or state["attempt"] >= MAX_MODEL_CALLS:
        return "finish"
    return "repair_sql"


def _record_error(state: TextToSqlState, error: ExecutionError) -> dict[str, object]:
    same = state["consecutive_error_hash"] == error.error_hash
    count = state["consecutive_error_count"] + 1 if same else 1
    contract_repairs = state["contract_repairs"]
    repeated_contract = error.category == "contract_mismatch" and contract_repairs >= 1
    if error.category == "contract_mismatch":
        contract_repairs += 1
    stalled = (same and count >= 2) or repeated_contract
    tripped = stalled or count >= CIRCUIT_THRESHOLD
    category = error.category
    message = error.normalized_message
    if stalled:
        category = "no_progress"
        message = "修复没有改变症状，已标记 no_progress 并熔断"
    elif tripped:
        category = "circuit_breaker"
        message = "同一规范化错误连续出现 3 次，已熔断"
    trace = [
        *state["repair_trace"],
        {
            "attempt": state["attempt"],
            "category": category,
            "symptom": error.error_hash,
            "sql_hash": sql_hash(state["generated_sql"]),
        },
    ]
    return {
        "status": "failed",
        "consecutive_error_hash": error.error_hash,
        "consecutive_error_count": count,
        "circuit_breaker_triggered": tripped,
        "error_category": category,
        "error_message": message,
        "error_retryable": False if tripped else error.retryable,
        "contract_repairs": contract_repairs,
        "repair_trace": trace,
    }


def _contract(state: TextToSqlState) -> AnswerContract | None:
    if state["profile"] != "ecommerce":
        return None
    return extract_answer_contract(state["question"], anchor_date=state["anchor_date"])


def _plan(contract: AnswerContract | None, state: TextToSqlState) -> str | None:
    if contract is None:
        return None
    return format_query_plan(contract, state["join_paths"])


async def _output_shape(services: ServiceBundle, state: TextToSqlState) -> str | None:
    if state["profile"] == "ecommerce":
        return None
    documents, edges = await services.load_catalog()
    if _catalog_mismatch(documents, state["database_id"]):
        return None
    return format_generic_shape(
        extract_generic_shape(
            state["question"],
            _selected_documents(documents, state),
            edges,
        )
    )


def _catalog_rejection(request_id: str) -> TextToSqlInspection:
    return TextToSqlInspection(
        response=TextToSqlResponse(
            request_id=request_id,
            status="failed",
            attempts=0,
            error=ApiError(
                category="cross_database_catalog",
                message="检索到的表不属于当前数据库",
                retryable=False,
            ),
        ),
        generated_sql=None,
    )


def _catalog_error() -> ExecutionError:
    return make_error(
        category="cross_database_catalog",
        message="检索到的表不属于当前数据库",
        exception_type="CatalogIsolation",
        retryable=False,
    )


def _catalog_mismatch(documents: Sequence[TableDocument], database_id: str) -> bool:
    return any(document.database_id != database_id for document in documents)


def _dialect_label(dialect: str) -> str:
    if dialect == "sqlite":
        return "SQLite"
    return "PostgreSQL"


def _zero_shot_schema(state: TextToSqlState) -> str:
    if state["profile"] == "ecommerce":
        return ZERO_SHOT_SCHEMA
    return (
        f"{_dialect_label(state['dialect'])} 数据库 {state['database_id']}，"
        f"schema 为 {state['schema_name']}。只生成一条只读 SELECT。"
    )


def _with_neighbors(
    documents: Sequence[TableDocument],
    edges: Sequence[SchemaEdge],
    names: Sequence[str],
    token_counter: TokenCounter,
    question: str,
) -> list[str]:
    return attach_neighbor_tables(
        documents,
        edges,
        names,
        token_counter=token_counter,
        question=question,
    )


def _visible_schema(state: TextToSqlState, context: str) -> str:
    if state["profile"] == "ecommerce":
        return context
    header = (
        f"{_dialect_label(state['dialect'])} 数据库 {state['database_id']}，"
        f"schema 为 {state['schema_name']}。"
    )
    return f"{header}\n{context}"


def _join_paths(edges: Sequence[SchemaEdge], tables: Sequence[str]) -> list[str]:
    selected = {name.lower() for name in tables}
    lines: list[str] = []
    for edge in edges:
        if edge.source_table.lower() not in selected or edge.target_table.lower() not in selected:
            continue
        left = ",".join(edge.source_columns)
        right = ",".join(edge.target_columns)
        lines.append(f"{edge.source_table}.{left} = {edge.target_table}.{right}")
    return lines


def _execution_score(finding_count: int) -> int:
    return max(1, 1000 - finding_count)


def _should_keep_candidate(state: TextToSqlState, score: int) -> bool:
    return bool(
        state["attempt"] > 1
        and state["candidate_sql"]
        and state["candidate_score"] > 0
        and score <= state["candidate_score"]
    )


def _candidate_update(
    state: TextToSqlState,
    outcome: ExecutionSuccess,
    score: int,
) -> dict[str, object]:
    return {
        "candidate_sql": state["generated_sql"],
        "candidate_columns": [name for name, _database_type in outcome.columns],
        "candidate_rows": json_rows(outcome.rows),
        "candidate_score": score,
        "candidate_execution_ms": outcome.execution_time_ms,
    }


def _fail_or_restore(
    state: TextToSqlState,
    error: ExecutionError,
    *,
    outcome: ExecutionSuccess | None = None,
    score: int = 0,
) -> dict[str, object]:
    recorded = _record_error(state, error)
    saved: dict[str, object] = {}
    if outcome is not None and score > state["candidate_score"]:
        saved = _candidate_update(state, outcome, score)
    merged = {**state, **saved}
    candidate_sql = merged.get("candidate_sql") or state["candidate_sql"]
    tripped = bool(recorded.get("circuit_breaker_triggered"))
    keep = _should_keep_candidate(state, 0 if tripped else score)
    if candidate_sql and (tripped or keep):
        return _restore_candidate(
            cast(TextToSqlState, merged),
            recorded["repair_trace"] if isinstance(recorded["repair_trace"], list) else None,
            str(recorded.get("error_category") or ""),
        )
    return {**recorded, **saved}


def _restore_candidate(
    state: TextToSqlState,
    trace: list[dict[str, object]] | None = None,
    symptom: str = "",
) -> dict[str, object]:
    steps = list(state["repair_trace"] if trace is None else trace)
    steps.append(
        {
            "attempt": state["attempt"],
            "category": "kept_candidate",
            "symptom": symptom or state["error_category"] or "",
            "sql_hash": sql_hash(state["candidate_sql"]),
        }
    )
    return {
        "status": "succeeded",
        "generated_sql": state["candidate_sql"],
        "columns": list(state["candidate_columns"]),
        "rows": [list(row) for row in state["candidate_rows"]],
        "db_execution_ms": state["candidate_execution_ms"],
        "error_category": None,
        "error_message": None,
        "error_retryable": False,
        "repair_trace": steps,
    }


def _actionable_findings(findings: Sequence[SemanticFinding]) -> list[SemanticFinding]:
    """无法证明的 JOIN 只作为警告，不因此再调用模型。"""

    warnings = {"join_unverified"}
    return [item for item in findings if item.category not in warnings]


def _selected_documents(
    documents: Sequence[TableDocument],
    state: TextToSqlState,
) -> tuple[TableDocument, ...]:
    selected = {name.lower() for name in (*state["seed_tables"], *state["expanded_tables"])}
    return tuple(document for document in documents if document.table_name.lower() in selected)


def _hinted(state: TextToSqlState, error: ExecutionError) -> ExecutionError:
    if state["profile"] == "ecommerce":
        return error
    extra = _generic_error_hint(error.category, error.normalized_message)
    if extra is None:
        return error
    return make_error(
        category=error.category,
        message=f"{error.normalized_message} {extra}",
        exception_type=error.exception_type,
        sqlstate=error.sqlstate,
        retryable=error.retryable,
    )


def _generic_error_hint(category: str, message: str) -> str | None:
    if category == "query_canceled":
        return "先按连接键聚合，再连接维表，避免笛卡尔积。"
    if category == "undefined_column" and "可用列" not in message:
        return "列名必须与当前库可用表一致；包含空格、括号或百分号时使用双引号。"
    if category == "undefined_table" and "最接近" not in message:
        return "改用当前库中的表名。"
    if category == "disallowed_function":
        return "只使用当前方言允许的只读函数；SQLite 用 strftime/julianday，PostgreSQL 用 date_trunc/extract。"
    if category == "cross_database_catalog":
        return "只引用当前数据库 catalog 中的表。"
    return None


def _review_error(findings: Sequence[SemanticFinding]) -> ExecutionError:
    others = [item for item in findings if item.category != "contract_mismatch"]
    chosen = others[0] if others else findings[0]
    message = "；".join(f"{item.category}: {item.message}" for item in findings)
    return make_error(
        category=chosen.category,
        message=message,
        exception_type="SemanticReview",
        retryable=True,
    )


def _fail(category: str, message: str, *, retryable: bool) -> dict[str, object]:
    return {
        "status": "failed",
        "error_category": category,
        "error_message": message,
        "error_retryable": retryable,
    }


def _messages(state: TextToSqlState, prompt: str) -> list[Mapping[str, str]]:
    return [
        {
            "role": "system",
            "content": system_prompt_for(dialect=state["dialect"], profile=state["profile"]),
        },
        {"role": "user", "content": prompt},
    ]


def _tools(state: TextToSqlState) -> list[ToolHit]:
    return [ToolHit.model_validate(tool) for tool in state["selected_tools"]]


def _tool_payload(tool: ToolHit) -> dict[str, object]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.input_schema,
        "score": tool.score,
    }


def _trace_fields(services: ServiceBundle, state: TextToSqlState | None) -> RequestTrace:
    if state is None:
        return {
            "request_type": "text_to_sql",
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
    elapsed = state["db_execution_ms"]
    return {
        "request_type": "text_to_sql",
        "model_name": model_name_of(services.model),
        "retrieved_seed_tables": tuple(state["seed_tables"]),
        "expanded_tables": tuple(state["expanded_tables"]),
        "schema_context_tokens": state["schema_token_count"],
        "selected_tools": _selected_tool_names(state),
        "generation_attempt": state["attempt"],
        "sql_hash": sql_hash(state["generated_sql"]),
        "error_hash": state["consecutive_error_hash"] or "",
        "db_execution_ms": 0.0 if elapsed is None else elapsed,
        "planner_total_cost": 0.0,
        "result_row_count": len(state["rows"]),
        "circuit_breaker_triggered": state["circuit_breaker_triggered"],
    }


def _selected_tool_names(state: TextToSqlState) -> tuple[str, ...]:
    names: list[str] = []
    for tool in state["selected_tools"]:
        name = tool.get("name")
        if isinstance(name, str):
            names.append(name)
    return tuple(names)


def _response(state: TextToSqlState) -> TextToSqlResponse:
    context = None
    if state["seed_tables"] or state["expanded_tables"] or state["schema_token_count"]:
        context = SchemaContextView(
            seed_tables=state["seed_tables"],
            expanded_tables=state["expanded_tables"],
            token_count=state["schema_token_count"],
            truncated=state["truncated"],
        )
    if state["status"] == "succeeded":
        return TextToSqlResponse(
            request_id=state["request_id"],
            status="succeeded",
            sql=state["generated_sql"],
            columns=state["columns"],
            rows=state["rows"],
            schema_context=context,
            attempts=state["attempt"],
        )
    return TextToSqlResponse(
        request_id=state["request_id"],
        status="failed",
        schema_context=context,
        attempts=state["attempt"],
        error=ApiError(
            category=state["error_category"] or "workflow_failed",
            message=state["error_message"] or "问数失败",
            retryable=state["error_retryable"],
        ),
    )
