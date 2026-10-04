"""Junction 不进入 Seed Top-K，图扩展仍然补全映射表。"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from app.db.catalog import load_foreign_keys, load_table_documents
from app.db.ecommerce_schema import apply_ecommerce_schema
from app.db.engine import get_admin_engine
from app.db.tables import JUNCTION_TABLES
from app.graph.expand import expand_schema
from app.mcp.definitions import TOOLS
from app.retrieval.embedder import EMBEDDING_DIMENSION
from app.retrieval.index import (
    ensure_embedding_tables,
    search_schema_seeds,
    search_tools,
    upsert_schema_embeddings,
    upsert_tool_embeddings,
)
from app.retrieval.text import schema_document_text
from app.schemas.catalog import TableDocument
from sqlalchemy import text

pytestmark = pytest.mark.integration

_ORDER_QUESTION = "订单优惠券和商品"
_REGION_QUESTION = "用户区域和会员等级"
_TOOL_QUESTION = "查询外键、行数和 SQL 语法"


class LookupEmbedder:
    """按预定文本返回向量，用来证明过滤发生在截断之前。"""

    model_name = "test-embedder"
    model_version = "test-v1"
    dimension = EMBEDDING_DIMENSION

    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._mapping = mapping

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._mapping[text] for text in texts]


def _axis(index: int, scale: float = 1.0) -> list[float]:
    values = [0.0] * EMBEDDING_DIMENSION
    values[index] = scale
    return values


def _query(*pairs: tuple[int, float]) -> list[float]:
    values = [0.0] * EMBEDDING_DIMENSION
    for index, scale in pairs:
        values[index] = scale
    return values


@pytest.fixture
async def indexed_retrieval(database_settings):
    del database_settings
    async with get_admin_engine().begin() as conn:
        await apply_ecommerce_schema(conn)
        documents = await load_table_documents(conn)
        edges = await load_foreign_keys(conn)
        embedder = _embedder(documents)
        await ensure_embedding_tables(conn)
        await upsert_schema_embeddings(conn, documents, embedder)
        await upsert_tool_embeddings(conn, embedder)
        await upsert_schema_embeddings(conn, documents, embedder)
    return documents, edges, embedder


def _embedder(documents: Sequence[TableDocument]) -> LookupEmbedder:
    table_axes = {
        "t_order": 1,
        "t_coupon": 2,
        "t_product": 3,
        "t_user": 4,
        "t_region": 5,
        "t_user_level": 6,
        "t_order_detail": 7,
        "t_merchant": 8,
        "t_category": 9,
    }
    mapping = {
        schema_document_text(document): _axis(0)
        if document.is_junction
        else _axis(table_axes[document.table_name])
        for document in documents
    }
    mapping[_ORDER_QUESTION] = _query((0, 1.0), (1, 0.5), (2, 0.4), (3, 0.3))
    mapping[_REGION_QUESTION] = _query((4, 1.0), (5, 0.5), (6, 0.4))
    preferred = ("get_foreign_keys", "get_table_row_count", "check_sql_syntax")
    for offset, tool in enumerate(TOOLS):
        if tool.name in preferred:
            mapping[tool.embedding_text()] = _axis(preferred.index(tool.name))
        else:
            mapping[tool.embedding_text()] = _axis(20 + offset)
    mapping[_TOOL_QUESTION] = _query((0, 1.0), (1, 0.8), (2, 0.6))
    missing = set(table_axes) | JUNCTION_TABLES
    assert missing == {document.table_name for document in documents}
    return LookupEmbedder(mapping)


async def test_seed_search_excludes_junctions_before_top_k(indexed_retrieval) -> None:
    documents, edges, embedder = indexed_retrieval
    async with get_admin_engine().connect() as conn:
        stored_junctions = await conn.scalar(
            text(
                """
                SELECT count(*)
                FROM schema_embedding
                WHERE embedding_model = 'test-embedder' AND is_junction
                """
            )
        )
        indexdef = await conn.scalar(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE indexname = 'schema_seed_embedding_hnsw'
                """
            )
        )
        total = await conn.scalar(
            text(
                """
                SELECT count(*)
                FROM schema_embedding
                WHERE embedding_model = 'test-embedder'
                """
            )
        )
        seeds = await search_schema_seeds(conn, _ORDER_QUESTION, embedder, top_k=3)
        region_seeds = await search_schema_seeds(conn, _REGION_QUESTION, embedder, top_k=3)

    assert stored_junctions == len(JUNCTION_TABLES)
    assert total == len(documents)
    assert indexdef is not None
    assert "is_junction = false" in str(indexdef)
    assert [seed.table_name for seed in seeds] == ["t_order", "t_coupon", "t_product"]
    assert all(seed.table_name not in JUNCTION_TABLES for seed in seeds)
    assert [seed.score for seed in seeds] == sorted(
        (seed.score for seed in seeds),
        reverse=True,
    )

    order_graph = expand_schema(
        documents,
        edges,
        [seed.table_name for seed in seeds],
        max_path_edges=1,
    )
    assert order_graph.connected is True
    assert order_graph.expanded_tables == ["t_order_coupon_rel", "t_promo_sku_rel"]
    assert set(order_graph.seed_tables).isdisjoint(JUNCTION_TABLES)

    region_graph = expand_schema(
        documents,
        edges,
        [seed.table_name for seed in region_seeds],
        max_path_edges=1,
    )
    assert [seed.table_name for seed in region_seeds] == ["t_user", "t_region", "t_user_level"]
    assert region_graph.connected is True
    assert "t_user_region_map" in region_graph.expanded_tables


async def test_tool_rag_returns_top_three_definitions(indexed_retrieval) -> None:
    _documents, _edges, embedder = indexed_retrieval
    async with get_admin_engine().connect() as conn:
        hits = await search_tools(conn, _TOOL_QUESTION, embedder)

    assert [hit.name for hit in hits] == [
        "get_foreign_keys",
        "get_table_row_count",
        "check_sql_syntax",
    ]
    assert len(hits) == 3
    assert hits[0].input_schema["required"] == ["table"]
    assert [hit.score for hit in hits] == sorted((hit.score for hit in hits), reverse=True)
