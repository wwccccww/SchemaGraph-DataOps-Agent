"""已登记数据源、目录隔离和通用种子。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from app.datasources.postgres_catalog import (
    ColumnCatalogRow,
    ForeignKeyCatalogRow,
    assemble_documents,
    assemble_foreign_keys,
)
from app.datasources.postgres_exec import execute_registered_postgres
from app.datasources.registry import registered_database_ids, resolve_data_source
from app.datasources.seeds import FALLBACK_SEED_CAP, lexical_schema_seeds
from app.datasources.sqlite_catalog import load_sqlite_catalog
from app.sandbox.gate import check_read_only_sql
from app.schemas.catalog import ColumnDocument, TableDocument


def test_unknown_database_stays_unresolved() -> None:
    assert resolve_data_source("other_db") is None
    assert resolve_data_source("warehouse") is None
    assert "ecommerce" in registered_database_ids()


def test_registered_sources_keep_their_dialect_and_profile() -> None:
    ecommerce = resolve_data_source("ecommerce")
    schools = resolve_data_source("california_schools")
    financial = resolve_data_source("financial")
    tpcds = resolve_data_source("tpcds")
    assert ecommerce is not None and ecommerce.profile == "ecommerce"
    assert ecommerce.dialect == "postgres" and ecommerce.schema_name == "public"
    assert schools is not None and schools.dialect == "sqlite" and schools.profile == "generic"
    assert financial is not None and financial.dialect == "sqlite"
    assert tpcds is not None and tpcds.dialect == "postgres" and tpcds.profile == "generic"


def test_sqlite_catalog_uses_the_requested_database_id(tmp_path: Path) -> None:
    database = tmp_path / "demo.sqlite"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE schools (cds TEXT PRIMARY KEY, name TEXT)")
    connection.execute(
        """
        CREATE TABLE satscores (
            cds TEXT,
            avg INTEGER,
            FOREIGN KEY (cds) REFERENCES schools (cds)
        )
        """
    )
    connection.commit()
    connection.close()

    documents, edges = load_sqlite_catalog(database, "california_schools")

    assert {document.database_id for document in documents} == {"california_schools"}
    assert {document.schema_name for document in documents} == {"main"}
    assert {document.table_name for document in documents} == {"satscores", "schools"}
    assert all(not document.is_junction for document in documents)
    assert any(
        edge.source_table == "satscores" and edge.target_table == "schools" for edge in edges
    )


def test_lexical_seed_names_the_table_and_skips_junctions() -> None:
    documents = [
        _table("schools", database_id="california_schools"),
        _table("students", database_id="california_schools"),
        _table("bridge", database_id="california_schools", junction=True),
    ]

    seeds = lexical_schema_seeds("count the schools", documents)

    assert [seed.table_name for seed in seeds] == ["schools"]
    assert {seed.database_id for seed in seeds} == {"california_schools"}
    assert {seed.embedding_model for seed in seeds} == {"lexical"}


def test_fallback_seeds_are_capped_and_ranked_by_name_overlap() -> None:
    documents = [_table(f"table_{index:02d}", database_id="tpcds") for index in range(13)]
    documents.append(_table("bridge", database_id="tpcds", junction=True))
    documents.extend(
        [
            _table("call_center", database_id="financial"),
            _table("store_sales", database_id="financial"),
        ]
    )
    with pytest.raises(ValueError, match="mixed"):
        lexical_schema_seeds("store sales", documents)

    owned = [document for document in documents if document.database_id == "financial"]
    seeds = lexical_schema_seeds("store sales", owned)
    assert [seed.table_name for seed in seeds] == ["store_sales", "call_center"]

    generic = [document for document in documents if document.database_id == "tpcds"]
    fallback = lexical_schema_seeds("zzzz", generic)
    assert len(fallback) == FALLBACK_SEED_CAP
    assert "bridge" not in {seed.table_name for seed in fallback}
    assert {seed.database_id for seed in fallback} == {"tpcds"}


def test_public_catalog_drops_dbgen_and_foreign_keys_outside_the_database() -> None:
    documents = assemble_documents(
        [
            ColumnCatalogRow("store_sales", None, "ss_item_sk", "integer", True, None),
            ColumnCatalogRow("dbgen_version", None, "version", "text", True, None),
            ColumnCatalogRow(
                "link",
                "映射 [Junction Table]",
                "left_id",
                "integer",
                False,
                None,
            ),
        ],
        database_id="tpcds",
        schema_name="public",
    )
    names = {document.table_name: document for document in documents}

    assert "dbgen_version" not in names
    assert names["store_sales"].database_id == "tpcds"
    assert names["link"].is_junction is True
    edges = assemble_foreign_keys(
        [
            ForeignKeyCatalogRow("store_sales", "item", "fk_item", ("ss_item_sk",), ("i_item_sk",)),
            ForeignKeyCatalogRow(
                "dbgen_version", "item", "fk_version", ("version",), ("i_item_sk",)
            ),
        ],
        set(names),
    )
    assert edges == []


def test_chinese_fallback_prefers_retail_table_names() -> None:
    documents = [
        _table("call_center", database_id="tpcds"),
        _table("store_sales", database_id="tpcds"),
        _table("customer", database_id="tpcds"),
        _table("item", database_id="tpcds"),
    ]

    seeds = lexical_schema_seeds("统计门店顾客购买商品的销售金额", documents)

    assert [seed.table_name for seed in seeds] == [
        "store_sales",
        "customer",
        "item",
        "call_center",
    ]


def test_gate_turns_parser_recursion_into_syntax_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_args: object, **_kwargs: object) -> list[object]:
        raise RecursionError("boom")

    monkeypatch.setattr("app.sandbox.gate.sqlglot.parse", explode)
    decision = check_read_only_sql("SELECT 1")

    assert decision.error is not None
    assert decision.error.category == "syntax_error"
    assert decision.sql == ""


def test_sqlite_gate_renders_sqlite_and_rejects_an_unknown_dialect() -> None:
    decision = check_read_only_sql("SELECT date('now')", dialect="sqlite")
    assert decision.error is None
    assert "date" in decision.sql.lower()
    rejected = check_read_only_sql("SELECT 1", dialect="mysql")
    assert rejected.error is not None
    assert rejected.sql == ""


async def test_external_postgres_executor_refuses_the_ecommerce_database() -> None:
    with pytest.raises(ValueError, match="ecommerce"):
        await execute_registered_postgres(
            "SELECT 1",
            max_rows=10,
            host="127.0.0.1",
            port=1,
            user="reader",
            password="secret-password",
            database="text2sql_db",
            timeout_seconds=1,
        )


def _table(
    name: str,
    *,
    database_id: str,
    junction: bool = False,
) -> TableDocument:
    comment = "[Junction Table]" if junction else None
    return TableDocument(
        database_id=database_id,
        schema_name="main",
        table_name=name,
        table_comment=comment,
        columns=[ColumnDocument(name="id", data_type="TEXT", nullable=False, comment=None)],
        is_junction=junction,
        content_hash=f"sha256:{name}",
    )
