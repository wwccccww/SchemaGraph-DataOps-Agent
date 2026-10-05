"""用一份已经提取好的目录组装问数依赖。不访问电商向量索引。"""

from __future__ import annotations

from collections.abc import Sequence

from app.agents.text_to_sql.workflow import ServiceBundle, SqlExecutor
from app.datasources.seeds import lexical_schema_seeds
from app.graph.expand import TokenCounter
from app.llm.gateway import ChatModel
from app.schemas.catalog import SchemaEdge, TableDocument
from app.schemas.retrieval import SchemaSeed, ToolHit


def build_static_bundle(
    *,
    model: ChatModel,
    token_counter: TokenCounter,
    documents: Sequence[TableDocument],
    edges: Sequence[SchemaEdge],
    execute: SqlExecutor,
    database_id: str,
) -> ServiceBundle:
    """工具列表为空。种子只来自这份目录。"""

    owned = tuple(documents)
    owned_edges = tuple(edges)
    if any(document.database_id != database_id for document in owned):
        raise ValueError("static bundle catalog must belong to its database")

    async def select_tools(_question: str) -> Sequence[ToolHit]:
        return ()

    async def select_seeds(question: str) -> Sequence[SchemaSeed]:
        return lexical_schema_seeds(question, owned)

    async def load_catalog() -> tuple[Sequence[TableDocument], Sequence[SchemaEdge]]:
        return owned, owned_edges

    return ServiceBundle(
        model=model,
        select_tools=select_tools,
        select_seeds=select_seeds,
        load_catalog=load_catalog,
        execute=execute,
        token_counter=token_counter,
        database_id=database_id,
    )
