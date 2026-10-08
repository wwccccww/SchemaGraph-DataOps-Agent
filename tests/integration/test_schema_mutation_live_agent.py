"""live_public 下 Agent EX（schema_rag + 单表 canary）。"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.agents.text_to_sql.runtime import build_services
from app.config.settings import get_settings
from app.db.catalog_loader import get_schema_registry, load_catalog_for_runtime, reset_schema_registry
from app.db.engine import get_admin_engine, get_sandbox_engine
from app.db.seed import seed_ecommerce
from app.evaluation.schema_mutation import (
    agent_canary_cases,
    load_mutation_canary_cases,
    score_canary_agent_ex,
)
from app.graph.expand import EstimatedTokenCounter
from app.retrieval.embedder import EMBEDDING_DIMENSION
from app.retrieval.index import ensure_embedding_tables, upsert_tool_embeddings
from app.retrieval.text import schema_document_text
from app.mcp.definitions import TOOLS
from app.schema_registry.indexing import sync_embeddings_for_snapshot
from tests.integration.test_text_to_sql_smoke import GoldModel, LookupEmbedder, _with_executor

pytestmark = pytest.mark.integration

_CANARY_TABLE = "schema_mutation_canary"


def _axis(index: int, scale: float = 1.0) -> list[float]:
    values = [0.0] * EMBEDDING_DIMENSION
    values[index] = scale
    return values


def _canary_embedder(documents, agent_case) -> LookupEmbedder:
    mapping = {}
    for document in documents:
        text = schema_document_text(document)
        if document.table_name == _CANARY_TABLE:
            mapping[text] = _axis(0, 1.0)
        else:
            mapping[text] = _axis(40, 0.01)
    mapping[agent_case.question] = _axis(0, 1.0)
    for offset, tool in enumerate(TOOLS):
        mapping[tool.embedding_text()] = _axis(50 + offset, 0.01)
    return LookupEmbedder(mapping)


async def test_live_public_agent_ex_on_canary_table(
    database_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del database_settings
    reset_schema_registry()
    await seed_ecommerce()
    async with get_admin_engine().begin() as conn:
        await conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {_CANARY_TABLE} (
                    id bigint PRIMARY KEY,
                    label text NOT NULL
                )
                """
            )
        )
        await conn.execute(
            text(
                f"""
                INSERT INTO {_CANARY_TABLE} (id, label)
                VALUES (1, 'canary-live')
                ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label
                """
            )
        )

    monkeypatch.setenv("TEXT_TO_SQL_CATALOG_MODE", "live_public")
    get_settings.cache_clear()
    settings = get_settings()
    cases = agent_canary_cases(load_mutation_canary_cases())
    assert len(cases) == 1
    agent_case = cases[0]

    async with get_sandbox_engine().connect() as conn:
        documents, _, _ = await load_catalog_for_runtime(conn)
    active = get_schema_registry().active_snapshot(settings.postgres_db)
    embedder = _canary_embedder(documents, agent_case)
    async with get_admin_engine().begin() as conn:
        await ensure_embedding_tables(conn)
        assert active is not None
        await sync_embeddings_for_snapshot(conn, active, embedder)
        await upsert_tool_embeddings(conn, embedder)

    services = _with_executor(
        build_services(
            embedder=embedder,
            model=GoldModel([agent_case]),
            token_counter=EstimatedTokenCounter(),
            database_id=settings.postgres_db,
        )
    )
    scores = await score_canary_agent_ex(
        cases,
        services,
        database_id=settings.postgres_db,
    )
    assert scores[0].ex == 1
    assert scores[0].status == "succeeded"
