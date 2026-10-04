"""Schema 文本、BGE-M3 标识和工具契约。"""

from __future__ import annotations

import math

import pytest
from app.mcp.definitions import TOOL_ERROR_SCHEMA, TOOLS
from app.retrieval.embedder import (
    BGE_M3_MODEL,
    BGE_M3_REVISION,
    EMBEDDING_DIMENSION,
    BgeM3Embedder,
    vector_literal,
)
from app.retrieval.index import SCHEMA_TOP_K, TOOL_TOP_K, search_schema_seeds
from app.retrieval.text import schema_document_text
from app.schemas.catalog import ColumnDocument, TableDocument

_REQUIRED = {
    "get_table_schema": ["tables"],
    "get_column_enums": ["table", "column", "limit"],
    "get_foreign_keys": ["table"],
    "get_table_row_count": ["table"],
    "get_partition_keys": ["table"],
    "explain_sql_cost": ["sql"],
    "check_sql_syntax": ["sql"],
    "get_etl_status": ["table"],
    "get_data_owner": ["table"],
    "get_metric_definition": ["metric_name"],
}


def test_schema_document_text_uses_names_and_comments_only() -> None:
    document = TableDocument(
        database_id="ecommerce",
        schema_name="public",
        table_name="t_order",
        table_comment="交易订单主事实表",
        columns=[
            ColumnDocument(
                name="order_id",
                data_type="bigint",
                nullable=False,
                comment="订单流水号主键",
            )
        ],
        is_junction=False,
        content_hash="sha256:test",
        embedding_model=None,
        embedding_version=None,
    )

    text = schema_document_text(document)

    assert text == "t_order 交易订单主事实表 order_id 订单流水号主键"
    assert "bigint" not in text


def test_bge_m3_identity_is_pinned() -> None:
    embedder = BgeM3Embedder()

    assert embedder.model_name == BGE_M3_MODEL == "BAAI/bge-m3"
    assert embedder.model_version == BGE_M3_REVISION
    assert len(embedder.model_version) == 40
    assert embedder.dimension == EMBEDDING_DIMENSION == 1024


def test_vector_literal_rejects_non_finite_values() -> None:
    values = [0.0] * EMBEDDING_DIMENSION
    literal = vector_literal(values)

    assert literal.startswith("[") and literal.endswith("]")
    assert all(character in "0123456789.,-[]" for character in literal)
    values[0] = math.nan
    with pytest.raises(ValueError):
        vector_literal(values)


def test_schema_top_k_is_three_to_five_and_tools_are_top_three() -> None:
    assert frozenset({3, 4, 5}) == SCHEMA_TOP_K
    assert TOOL_TOP_K == 3


async def test_schema_search_rejects_top_k_outside_the_design_range() -> None:
    embedder = BgeM3Embedder()

    with pytest.raises(ValueError, match="top_k"):
        await search_schema_seeds(None, "订单", embedder, top_k=2)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="top_k"):
        await search_schema_seeds(None, "订单", embedder, top_k=6)  # type: ignore[arg-type]


def test_mcp_catalog_has_ten_read_only_tool_definitions() -> None:
    assert [tool.name for tool in TOOLS] == list(_REQUIRED)
    for tool in TOOLS:
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert schema["required"] == _REQUIRED[tool.name]
        assert tool.description.strip()
        assert tool.embedding_text().startswith(tool.name)
    explain = next(tool for tool in TOOLS if tool.name == "explain_sql_cost")
    properties = explain.input_schema["properties"]
    assert isinstance(properties, dict)
    assert properties["analyze"] == {"type": "boolean", "default": False}
    output = explain.output_schema["properties"]
    assert isinstance(output, dict)
    assert output["execution_time_ms"] == {"type": ["number", "null"]}
    assert TOOL_ERROR_SCHEMA["required"] == ["ok", "data", "error"]
