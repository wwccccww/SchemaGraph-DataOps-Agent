"""把表文档和 MCP 工具写入 pgvector，并按候选条件检索。

Seed 查询在 LIMIT 之前要求 is_junction = false。禁止先取 Top-K 再丢弃
Junction Table，否则名额会被映射表占掉。
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.catalog import DATABASE_ID, SCHEMA_NAME, load_table_documents
from app.db.engine import get_admin_engine
from app.db.initialize import initialize_database_with_retry
from app.mcp.definitions import TOOLS, TOOLS_BY_NAME
from app.retrieval.embedder import EMBEDDING_DIMENSION, BgeM3Embedder, Embedder, vector_literal
from app.retrieval.text import schema_document_text
from app.schemas.catalog import TableDocument
from app.schemas.retrieval import SchemaSeed, ToolHit

logger = logging.getLogger(__name__)

SCHEMA_TOP_K = frozenset({3, 4, 5})
TOOL_TOP_K = 3
_INDEX_LOCK = "schemagraph.retrieval_index"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_SANDBOX_ROLE = "sandbox_readonly"


async def ensure_embedding_tables(conn: AsyncConnection) -> None:
    """创建向量表。Seed 的 HNSW 索引本身不包含 Junction Table。"""

    statements = (
        "CREATE EXTENSION IF NOT EXISTS vector",
        """
        CREATE TABLE IF NOT EXISTS schema_embedding (
            database_id TEXT NOT NULL,
            schema_name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            is_junction BOOLEAN NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_version TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            document_text TEXT NOT NULL,
            embedding vector(1024) NOT NULL,
            PRIMARY KEY (
                database_id, schema_name, table_name, embedding_model, embedding_version
            )
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS schema_seed_embedding_hnsw
        ON schema_embedding USING hnsw (embedding vector_cosine_ops)
        WHERE is_junction = false
        """,
        """
        CREATE TABLE IF NOT EXISTS tool_embedding (
            tool_name TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_version TEXT NOT NULL,
            document_text TEXT NOT NULL,
            embedding vector(1024) NOT NULL,
            PRIMARY KEY (tool_name, embedding_model, embedding_version)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS tool_embedding_hnsw
        ON tool_embedding USING hnsw (embedding vector_cosine_ops)
        """,
        f"GRANT SELECT ON schema_embedding, tool_embedding TO {_SANDBOX_ROLE}",
        f"GRANT EXECUTE ON FUNCTION cosine_distance(vector, vector) TO {_SANDBOX_ROLE}",
    )
    for statement in statements:
        await conn.execute(text(statement))


async def upsert_schema_embeddings(
    conn: AsyncConnection,
    documents: Sequence[TableDocument],
    embedder: Embedder,
) -> None:
    """保存全部表的元数据和向量，包括 Junction Table。"""

    _check_embedder(embedder)
    if not documents:
        raise ValueError("schema indexing requires documents")
    database_ids = {document.database_id for document in documents}
    schema_names = {document.schema_name for document in documents}
    if len(database_ids) != 1 or len(schema_names) != 1:
        raise ValueError("schema indexing accepts one database and schema at a time")
    texts = [schema_document_text(document) for document in documents]
    vectors = embedder.embed_texts(texts)
    if len(vectors) != len(documents):
        raise RuntimeError("schema embedder returned the wrong number of vectors")
    await conn.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)"),
        {"key": _INDEX_LOCK},
    )
    rows = [
        {
            "database_id": document.database_id,
            "schema_name": document.schema_name,
            "table_name": document.table_name,
            "is_junction": document.is_junction,
            "embedding_model": embedder.model_name,
            "embedding_version": embedder.model_version,
            "content_hash": document.content_hash,
            "document_text": text_value,
            "embedding": vector_literal(vector),
        }
        for document, text_value, vector in zip(documents, texts, vectors, strict=True)
    ]
    await conn.execute(
        text(
            """
            INSERT INTO schema_embedding (
                database_id, schema_name, table_name, is_junction, embedding_model,
                embedding_version, content_hash, document_text, embedding
            )
            VALUES (
                :database_id, :schema_name, :table_name, :is_junction, :embedding_model,
                :embedding_version, :content_hash, :document_text, CAST(:embedding AS vector)
            )
            ON CONFLICT (
                database_id, schema_name, table_name, embedding_model, embedding_version
            )
            DO UPDATE SET
                is_junction = EXCLUDED.is_junction,
                content_hash = EXCLUDED.content_hash,
                document_text = EXCLUDED.document_text,
                embedding = EXCLUDED.embedding
            """
        ),
        rows,
    )
    await conn.execute(
        text(
            """
            DELETE FROM schema_embedding
            WHERE database_id = :database_id
              AND schema_name = :schema_name
              AND embedding_model = :embedding_model
              AND embedding_version = :embedding_version
              AND table_name NOT IN :table_names
            """
        ).bindparams(bindparam("table_names", expanding=True)),
        {
            "database_id": documents[0].database_id,
            "schema_name": documents[0].schema_name,
            "embedding_model": embedder.model_name,
            "embedding_version": embedder.model_version,
            "table_names": [document.table_name for document in documents],
        },
    )


async def upsert_tool_embeddings(conn: AsyncConnection, embedder: Embedder) -> None:
    """索引全部 10 个工具定义。"""

    _check_embedder(embedder)
    texts = [tool.embedding_text() for tool in TOOLS]
    vectors = embedder.embed_texts(texts)
    rows = [
        {
            "tool_name": tool.name,
            "embedding_model": embedder.model_name,
            "embedding_version": embedder.model_version,
            "document_text": text_value,
            "embedding": vector_literal(vector),
        }
        for tool, text_value, vector in zip(TOOLS, texts, vectors, strict=True)
    ]
    await conn.execute(
        text(
            """
            INSERT INTO tool_embedding (
                tool_name, embedding_model, embedding_version, document_text, embedding
            )
            VALUES (
                :tool_name, :embedding_model, :embedding_version, :document_text,
                CAST(:embedding AS vector)
            )
            ON CONFLICT (tool_name, embedding_model, embedding_version)
            DO UPDATE SET
                document_text = EXCLUDED.document_text,
                embedding = EXCLUDED.embedding
            """
        ),
        rows,
    )
    await conn.execute(
        text(
            """
            DELETE FROM tool_embedding
            WHERE embedding_model = :embedding_model
              AND embedding_version = :embedding_version
              AND tool_name NOT IN :tool_names
            """
        ).bindparams(bindparam("tool_names", expanding=True)),
        {
            "embedding_model": embedder.model_name,
            "embedding_version": embedder.model_version,
            "tool_names": [tool.name for tool in TOOLS],
        },
    )


async def search_schema_seeds(
    conn: AsyncConnection,
    question: str,
    embedder: Embedder,
    *,
    top_k: int = 5,
    database_id: str = DATABASE_ID,
    schema_name: str = SCHEMA_NAME,
) -> list[SchemaSeed]:
    """召回 Top-3～5 张实体种子表。过滤发生在排序截断之前。"""

    if top_k not in SCHEMA_TOP_K:
        raise ValueError("schema seed top_k must be 3, 4, or 5")
    _check_scope(database_id, schema_name)
    query = _query_vector(question, embedder)
    rows = (
        await conn.execute(
            text(
                """
                SELECT
                    database_id,
                    schema_name,
                    table_name,
                    is_junction,
                    content_hash,
                    embedding_model,
                    embedding_version,
                    1 - (embedding <=> CAST(:query AS vector)) AS score
                FROM schema_embedding
                WHERE database_id = :database_id
                  AND schema_name = :schema_name
                  AND embedding_model = :embedding_model
                  AND embedding_version = :embedding_version
                  AND is_junction = false
                ORDER BY embedding <=> CAST(:query AS vector), table_name
                LIMIT :top_k
                """
            ),
            {
                "query": query,
                "database_id": database_id,
                "schema_name": schema_name,
                "embedding_model": embedder.model_name,
                "embedding_version": embedder.model_version,
                "top_k": top_k,
            },
        )
    ).all()
    if any(row.is_junction for row in rows):
        raise RuntimeError("junction table leaked into seed candidates")
    return [
        SchemaSeed(
            database_id=str(row.database_id),
            schema_name=str(row.schema_name),
            table_name=str(row.table_name),
            content_hash=str(row.content_hash),
            embedding_model=str(row.embedding_model),
            embedding_version=str(row.embedding_version),
            score=float(row.score),
        )
        for row in rows
    ]


async def search_tools(conn: AsyncConnection, question: str, embedder: Embedder) -> list[ToolHit]:
    """召回 Top-3 工具定义。"""

    query = _query_vector(question, embedder)
    rows = (
        await conn.execute(
            text(
                """
                SELECT tool_name, 1 - (embedding <=> CAST(:query AS vector)) AS score
                FROM tool_embedding
                WHERE embedding_model = :embedding_model
                  AND embedding_version = :embedding_version
                ORDER BY embedding <=> CAST(:query AS vector), tool_name
                LIMIT :top_k
                """
            ),
            {
                "query": query,
                "embedding_model": embedder.model_name,
                "embedding_version": embedder.model_version,
                "top_k": TOOL_TOP_K,
            },
        )
    ).all()
    hits: list[ToolHit] = []
    for row in rows:
        definition = TOOLS_BY_NAME.get(str(row.tool_name))
        if definition is None:
            raise RuntimeError(f"indexed tool is not registered: {row.tool_name}")
        hits.append(
            ToolHit(
                name=definition.name,
                description=definition.description,
                input_schema=definition.input_schema,
                score=float(row.score),
            )
        )
    return hits


def _query_vector(question: str, embedder: Embedder) -> str:
    if question.strip() == "":
        raise ValueError("retrieval question must be non-empty")
    _check_embedder(embedder)
    vectors = embedder.embed_texts([question])
    if len(vectors) != 1:
        raise RuntimeError("query embedder must return one vector")
    return vector_literal(vectors[0])


def _check_embedder(embedder: Embedder) -> None:
    if embedder.dimension != EMBEDDING_DIMENSION:
        raise ValueError("embedder dimension must be 1024")
    if embedder.model_name.strip() == "" or embedder.model_version.strip() == "":
        raise ValueError("embedder model identity must be set")


def _check_scope(database_id: str, schema_name: str) -> None:
    if _IDENTIFIER.fullmatch(database_id) is None or _IDENTIFIER.fullmatch(schema_name) is None:
        raise ValueError("database and schema names must be identifiers")


def main() -> None:
    """用 BGE-M3 重建 Schema 与 Tool 向量索引。"""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(_main())


async def _main() -> None:
    await initialize_database_with_retry()
    embedder = BgeM3Embedder()
    async with get_admin_engine().begin() as conn:
        await ensure_embedding_tables(conn)
        documents = await load_table_documents(conn)
        await upsert_schema_embeddings(conn, documents, embedder)
        await upsert_tool_embeddings(conn, embedder)
        logger.info(
            "indexed %s schema documents and %s tools with %s@%s",
            len(documents),
            len(TOOLS),
            embedder.model_name,
            embedder.model_version,
        )


if __name__ == "__main__":
    main()
