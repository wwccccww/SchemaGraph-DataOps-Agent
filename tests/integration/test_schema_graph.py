"""Catalog 中的显式外键可以驱动图扩展。"""

from __future__ import annotations

import pytest
from app.db.catalog import load_foreign_keys, load_table_documents
from app.db.ecommerce_schema import apply_ecommerce_schema
from app.db.engine import get_admin_engine
from app.db.tables import FOREIGN_KEYS, INDEX_NAMES, JUNCTION_TABLES
from app.graph.expand import expand_schema
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def test_catalog_reads_explicit_foreign_keys_and_junctions(database_settings) -> None:
    del database_settings
    async with get_admin_engine().begin() as conn:
        await apply_ecommerce_schema(conn)
        documents = await load_table_documents(conn)
        edges = await load_foreign_keys(conn)
        indexes = await conn.scalar(
            text(
                """
                SELECT count(*)
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname LIKE 'idx_%'
                """
            )
        )

    assert {document.table_name for document in documents if document.is_junction} == set(
        JUNCTION_TABLES
    )
    assert all(document.embedding_model is None for document in documents)
    assert all(document.content_hash.startswith("sha256:") for document in documents)
    assert {
        (
            edge.constraint_name,
            edge.source_table,
            tuple(edge.source_columns),
            edge.target_table,
            tuple(edge.target_columns),
        )
        for edge in edges
    } == {
        (
            item.constraint_name,
            item.source_table,
            (item.source_column,),
            item.target_table,
            (item.target_column,),
        )
        for item in FOREIGN_KEYS
    }
    assert all(
        edge.weight == 1.0 and edge.inferred is False and edge.confidence == 1.0 for edge in edges
    )
    assert indexes == len(INDEX_NAMES)


async def test_real_catalog_graph_expands_and_rejects_deep_paths(database_settings) -> None:
    del database_settings
    async with get_admin_engine().begin() as conn:
        await apply_ecommerce_schema(conn)
        documents = await load_table_documents(conn)
        edges = await load_foreign_keys(conn)

    bridged = expand_schema(documents, edges, ["t_order", "t_coupon"], max_path_edges=1)
    assert bridged.connected is True
    assert bridged.expanded_tables == ["t_order_coupon_rel"]

    too_deep = expand_schema(documents, edges, ["t_user_level", "t_category"])
    assert too_deep.connected is False
    assert too_deep.diagnostic is not None
    assert too_deep.diagnostic.code == "path_too_deep"
