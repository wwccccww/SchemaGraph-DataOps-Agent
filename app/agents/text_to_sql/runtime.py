"""组装问数依赖。导入本模块不会下载模型、词表或向量。"""

from __future__ import annotations

from collections.abc import Sequence

from app.agents.text_to_sql.workflow import ServiceBundle
from app.config.settings import get_settings
from app.db.catalog_loader import load_catalog_for_runtime
from app.db.engine import get_sandbox_engine
from app.graph.expand import TokenCounter
from app.llm.gateway import ChatModel, DeepSeekGateway
from app.llm.tokenizer import DeepSeekTokenCounter
from app.retrieval.embedder import BgeM3Embedder, Embedder
from app.retrieval.index import search_dynamic_schema_seeds, search_tools
from app.sandbox.errors import ExecutionError
from app.sandbox.execute import ExecutionSuccess, execute_readonly
from app.sandbox.explain import explain_readonly
from app.schemas.catalog import SchemaEdge, TableDocument
from app.schemas.retrieval import SchemaSeed, ToolHit

_bundle: ServiceBundle | None = None


def get_default_services() -> ServiceBundle:
    """返回进程内默认依赖。首次调用才构造网关，仍不会立刻下载词表。"""

    global _bundle
    if _bundle is None:
        _bundle = build_default_services()
    return _bundle


def reset_default_services() -> None:
    """清掉缓存，供测试替换环境变量后重建。"""

    global _bundle
    _bundle = None


def build_default_services() -> ServiceBundle:
    """使用 BGE-M3、DeepSeek 网关和 DeepSeek tokenizer。"""

    settings = get_settings()
    return build_services(
        embedder=BgeM3Embedder(),
        model=DeepSeekGateway(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        ),
        token_counter=DeepSeekTokenCounter(),
    )


def build_services(
    *,
    embedder: Embedder,
    model: ChatModel,
    token_counter: TokenCounter,
) -> ServiceBundle:
    """用调用方提供的编码器和模型组装工作流。"""

    async def select_tools(question: str) -> Sequence[ToolHit]:
        async with get_sandbox_engine().connect() as conn:
            return await search_tools(conn, question, embedder)

    async def select_seeds(question: str) -> Sequence[SchemaSeed]:
        async with get_sandbox_engine().connect() as conn:
            documents, _, _ = await load_catalog_for_runtime(conn, settings)
            return await search_dynamic_schema_seeds(conn, question, embedder, documents)

    async def load_catalog() -> tuple[Sequence[TableDocument], Sequence[SchemaEdge]]:
        async with get_sandbox_engine().connect() as conn:
            documents, edges, _ = await load_catalog_for_runtime(conn, settings)
        return documents, edges

    async def execute(sql: str, *, max_rows: int) -> ExecutionSuccess | ExecutionError:
        return await execute_readonly(sql, max_rows=max_rows)

    async def estimate_plan_rows(sql: str) -> float | None:
        outcome = await explain_readonly(sql, analyze=False)
        if isinstance(outcome, ExecutionError):
            return None
        return outcome.plan_rows

    return ServiceBundle(
        model=model,
        select_tools=select_tools,
        select_seeds=select_seeds,
        load_catalog=load_catalog,
        execute=execute,
        token_counter=token_counter,
        estimate_plan_rows=estimate_plan_rows,
    )
