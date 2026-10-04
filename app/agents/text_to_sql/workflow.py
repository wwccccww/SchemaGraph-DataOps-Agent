"""Text-to-SQL 的 LangGraph 状态机。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict, cast
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.agents.text_to_sql.prompt import (
    SYSTEM_PROMPT,
    extract_sql,
    render_generation_prompt,
    render_repair_prompt,
)
from app.db.catalog import DATABASE_ID
from app.graph.expand import TokenCounter, expand_schema, render_schema_context
from app.llm.gateway import ChatModel
from app.sandbox.errors import ExecutionError
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

Catalog = tuple[Sequence[TableDocument], Sequence[SchemaEdge]]


class SqlExecutor(Protocol):
    """执行一条已经通过门禁的 SQL。"""

    async def __call__(self, sql: str, *, max_rows: int) -> ExecutionSuccess | ExecutionError:
        """返回结果或结构化错误。"""


class TextToSqlState(TypedDict):
    """一次问数的图状态。默认不持久化。"""

    request_id: str
    question: str
    database_id: str
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


@dataclass(frozen=True)
class ServiceBundle:
    model: ChatModel
    select_tools: Callable[[str], Awaitable[Sequence[ToolHit]]]
    select_seeds: Callable[[str], Awaitable[Sequence[SchemaSeed]]]
    load_catalog: Callable[[], Awaitable[Catalog]]
    execute: SqlExecutor
    token_counter: TokenCounter


def build_graph(services: ServiceBundle) -> Any:
    """编译问数图。节点名与架构文档一致。"""

    bound = ServiceBundle(
        model=services.model,
        select_tools=services.select_tools,
        select_seeds=services.select_seeds,
        load_catalog=services.load_catalog,
        execute=services.execute,
        token_counter=services.token_counter,
    )
    builder = StateGraph(TextToSqlState)
    builder.add_node("route_tools", cast(Any, _route_tools(bound)))
    builder.add_node("retrieve_schema", cast(Any, _retrieve_schema(bound)))
    builder.add_node("expand_schema_graph", cast(Any, _expand_schema_graph(bound)))
    builder.add_node("build_prompt", cast(Any, _build_prompt))
    builder.add_node("generate_sql", cast(Any, _generate_sql(bound)))
    builder.add_node("validate_sql", cast(Any, _validate_sql))
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


async def run_text_to_sql(
    services: ServiceBundle,
    *,
    question: str,
    database_id: str,
    execute: bool = True,
    max_rows: int = 1000,
    request_id: str | None = None,
) -> TextToSqlResponse:
    """运行一次问数。评测标签和 Gold SQL 不是参数。"""

    identifier = request_id or f"req_{uuid4().hex}"
    if database_id != DATABASE_ID:
        return TextToSqlResponse(
            request_id=identifier,
            status="failed",
            attempts=0,
            error=ApiError(
                category="unsupported_database",
                message="当前只支持 ecommerce 数据库",
                retryable=False,
            ),
        )
    graph = cast(CompiledGraph, build_graph(services))
    final = await graph.ainvoke(
        _initial_state(
            request_id=identifier,
            question=question,
            database_id=database_id,
            execute=execute,
            max_rows=max_rows,
        )
    )
    return _response(final)


class CompiledGraph(Protocol):
    """ainvoke 的最小调用面。"""

    async def ainvoke(self, state: TextToSqlState) -> TextToSqlState:
        """运行到结束节点。"""


def _initial_state(
    *,
    request_id: str,
    question: str,
    database_id: str,
    execute: bool,
    max_rows: int,
) -> TextToSqlState:
    return {
        "request_id": request_id,
        "question": question,
        "database_id": database_id,
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
    }


def _route_tools(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def route_tools(state: TextToSqlState) -> dict[str, object]:
        tools = await services.select_tools(state["question"])
        return {"selected_tools": [_tool_payload(tool) for tool in tools]}

    return route_tools


def _retrieve_schema(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def retrieve_schema(state: TextToSqlState) -> dict[str, object]:
        seeds = await services.select_seeds(state["question"])
        return {"seed_tables": [seed.table_name for seed in seeds]}

    return retrieve_schema


def _expand_schema_graph(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def expand_schema_graph(state: TextToSqlState) -> dict[str, object]:
        if not state["seed_tables"]:
            return _fail("no_schema_seed", "没有检索到实体种子表", retryable=False)
        documents, edges = await services.load_catalog()
        by_name = {document.table_name: document for document in documents}
        if any(name not in by_name or by_name[name].is_junction for name in state["seed_tables"]):
            return _fail("junction_seed_leak", "种子结果包含不可用的表", retryable=False)
        result = expand_schema(
            documents,
            edges,
            state["seed_tables"],
            token_counter=services.token_counter,
        )
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
        selected = [
            by_name[name]
            for name in (*result.seed_tables, *result.expanded_tables)
            if name in by_name
        ]
        context = render_schema_context(selected)
        return {
            "status": "running",
            "seed_tables": list(result.seed_tables),
            "expanded_tables": list(result.expanded_tables),
            "schema_context": context,
            "schema_token_count": result.context_tokens,
            "truncated": result.context_truncated,
        }

    return expand_schema_graph


async def _build_prompt(state: TextToSqlState) -> dict[str, object]:
    return {
        "prompt": render_generation_prompt(
            question=state["question"],
            schema_context=state["schema_context"],
            tools=_tools(state),
        )
    }


def _generate_sql(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def generate_sql(state: TextToSqlState) -> dict[str, object]:
        content = await services.model.complete(
            _messages(state["prompt"]),
            temperature=GENERATION_TEMPERATURE,
        )
        return {"generated_sql": extract_sql(content), "attempt": state["attempt"] + 1}

    return generate_sql


async def _validate_sql(state: TextToSqlState) -> dict[str, object]:
    decision = check_read_only_sql(state["generated_sql"] or "")
    if decision.error is None:
        return {"status": "validated", "generated_sql": decision.sql}
    return _record_error(state, decision.error)


def _execute_sql(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def execute_sql(state: TextToSqlState) -> dict[str, object]:
        sql = state["generated_sql"] or ""
        outcome = await services.execute(sql, max_rows=state["max_rows"])
        if isinstance(outcome, ExecutionError):
            return _record_error(state, outcome)
        return {
            "status": "succeeded",
            "columns": [name for name, _database_type in outcome.columns],
            "rows": json_rows(outcome.rows),
        }

    return execute_sql


def _repair_sql(
    services: ServiceBundle,
) -> Callable[[TextToSqlState], Awaitable[dict[str, object]]]:
    async def repair_sql(state: TextToSqlState) -> dict[str, object]:
        prompt = render_repair_prompt(
            question=state["question"],
            schema_context=state["schema_context"],
            tools=_tools(state),
            previous_sql=state["generated_sql"] or "",
            error_category=state["error_category"] or "",
            error_message=state["error_message"] or "",
        )
        content = await services.model.complete(
            _messages(prompt),
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
    return _failure_target(state)


def _after_execute(state: TextToSqlState) -> str:
    if state["status"] == "succeeded":
        return "finish"
    return _failure_target(state)


def _failure_target(state: TextToSqlState) -> str:
    if state["circuit_breaker_triggered"] or state["attempt"] >= MAX_MODEL_CALLS:
        return "finish"
    return "repair_sql"


def _record_error(state: TextToSqlState, error: ExecutionError) -> dict[str, object]:
    same = state["consecutive_error_hash"] == error.error_hash
    count = state["consecutive_error_count"] + 1 if same else 1
    tripped = count >= CIRCUIT_THRESHOLD
    return {
        "status": "failed",
        "consecutive_error_hash": error.error_hash,
        "consecutive_error_count": count,
        "circuit_breaker_triggered": tripped,
        "error_category": "circuit_breaker" if tripped else error.category,
        "error_message": (
            "同一规范化错误连续出现 3 次，已熔断" if tripped else error.normalized_message
        ),
        "error_retryable": False if tripped else error.retryable,
    }


def _fail(category: str, message: str, *, retryable: bool) -> dict[str, object]:
    return {
        "status": "failed",
        "error_category": category,
        "error_message": message,
        "error_retryable": retryable,
    }


def _messages(prompt: str) -> list[Mapping[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
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
