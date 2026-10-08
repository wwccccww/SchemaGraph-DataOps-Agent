"""Schema 变更后 Gold EX 回放 canary。"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.catalog_loader import get_schema_registry, load_catalog_for_runtime, reset_schema_registry
from app.db.engine import get_admin_engine, get_sandbox_engine
from app.db.seed import seed_ecommerce
from app.agents.text_to_sql.runtime import build_services
from app.evaluation.schema_mutation import (
    baseline_canary_cases,
    compare_replay_stable,
    load_mutation_canary_cases,
    mutation_canary_cases,
    replay_canary_ex,
    replay_smoke_subset_ex,
    score_agent_ex_cases,
)
from app.evaluation.smoke import load_smoke_cases
from app.graph.expand import EstimatedTokenCounter
from app.retrieval.index import ensure_embedding_tables, upsert_tool_embeddings
from app.schema_registry.indexing import sync_embeddings_for_snapshot
from tests.integration.test_text_to_sql_smoke import GoldModel, _embedder, _with_executor

pytestmark = pytest.mark.integration

_CANARY_TABLE = "schema_mutation_canary"


async def test_mutation_canary_and_smoke_ex_replay(
    database_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del database_settings
    reset_schema_registry()
    await seed_ecommerce()
    cases = load_mutation_canary_cases()
    baselines = baseline_canary_cases(cases)
    mutations = mutation_canary_cases(cases)

    async with get_sandbox_engine().connect() as conn:
        before = await replay_canary_ex(baselines, conn)
        assert all(item.passed for item in before)
        smoke_before = await replay_smoke_subset_ex(
            ["smoke_basic_001", "smoke_basic_002"],
            conn,
        )
        assert all(item.passed for item in smoke_before)

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
                VALUES (1, 'canary')
                ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label
                """
            )
        )

    from app.config.settings import get_settings

    monkeypatch.setenv("TEXT_TO_SQL_CATALOG_MODE", "live_public")
    get_settings.cache_clear()
    reset_schema_registry()
    settings = get_settings()

    async with get_sandbox_engine().connect() as conn:
        documents, _, fingerprint = await load_catalog_for_runtime(conn)
        names = {document.table_name for document in documents}
        assert _CANARY_TABLE in names
        active = get_schema_registry().active_snapshot(settings.postgres_db)
        assert active is not None
        assert active.fingerprint == fingerprint

        after_baselines = await replay_canary_ex(baselines, conn)
        after_mutations = await replay_canary_ex(mutations, conn)
        smoke_after = await replay_smoke_subset_ex(
            ["smoke_basic_001", "smoke_basic_002"],
            conn,
        )

    assert all(item.passed for item in after_baselines)
    assert all(item.passed for item in after_mutations)
    assert all(item.passed for item in smoke_after)
    assert compare_replay_stable(
        before,
        after_baselines,
        case_ids=[item.id for item in baselines],
    )

    monkeypatch.setenv("TEXT_TO_SQL_CATALOG_MODE", "fixed_ecommerce")
    get_settings.cache_clear()
    reset_schema_registry()

    smoke_cases = load_smoke_cases()
    subset_ids = ["smoke_basic_001", "smoke_basic_002"]
    async with get_sandbox_engine().connect() as conn:
        catalog_docs, _, _ = await load_catalog_for_runtime(conn)
    embedder = _embedder(catalog_docs, smoke_cases)
    active_ecommerce = get_schema_registry().active_snapshot("ecommerce")
    async with get_admin_engine().begin() as conn:
        await ensure_embedding_tables(conn)
        assert active_ecommerce is not None
        await sync_embeddings_for_snapshot(conn, active_ecommerce, embedder)
        await upsert_tool_embeddings(conn, embedder)

    services = _with_executor(
        build_services(
            embedder=embedder,
            model=GoldModel(smoke_cases),
            token_counter=EstimatedTokenCounter(),
            database_id="ecommerce",
        )
    )
    agent_scores = await score_agent_ex_cases(
        subset_ids,
        services,
        database_id="ecommerce",
    )
    assert [item.ex for item in agent_scores] == [1, 1]
    assert all(item.status == "succeeded" for item in agent_scores)

    async with get_admin_engine().begin() as conn:
        await conn.execute(text(f"DROP TABLE IF EXISTS {_CANARY_TABLE} CASCADE"))

    reset_schema_registry()
    get_settings.cache_clear()
    monkeypatch.setenv("TEXT_TO_SQL_CATALOG_MODE", "live_public")
    get_settings.cache_clear()

    async with get_sandbox_engine().connect() as conn:
        await load_catalog_for_runtime(conn)
        after_drop_baselines = await replay_canary_ex(baselines, conn)
        after_drop_mutations = await replay_canary_ex(mutations, conn)

    assert all(item.passed for item in after_drop_baselines)
    assert not any(item.passed for item in after_drop_mutations)
