"""Schema Graph 扩展的失败语义和三条 Junction 路径。"""

from __future__ import annotations

import pytest
from app.db.tables import FOREIGN_KEYS, JUNCTION_TABLES, TABLE_SPECS
from app.graph.expand import expand_schema
from app.schemas.catalog import ColumnDocument, SchemaEdge, TableDocument


def _documents() -> list[TableDocument]:
    return [
        TableDocument(
            database_id="ecommerce",
            schema_name="public",
            table_name=spec.name,
            table_comment="映射表[Junction Table]" if spec.name in JUNCTION_TABLES else "业务表",
            columns=[
                ColumnDocument(
                    name=column,
                    data_type="bigint",
                    nullable=False,
                    comment=column,
                )
                for column in spec.columns
            ],
            is_junction=spec.name in JUNCTION_TABLES,
            content_hash=f"sha256:{spec.name}",
            embedding_model=None,
            embedding_version=None,
        )
        for spec in TABLE_SPECS
    ]


def _edges() -> list[SchemaEdge]:
    return [
        SchemaEdge(
            source_table=item.source_table,
            source_columns=[item.source_column],
            target_table=item.target_table,
            target_columns=[item.target_column],
            constraint_name=item.constraint_name,
            weight=1.0,
            inferred=False,
            confidence=1.0,
        )
        for item in FOREIGN_KEYS
    ]


def _orphan() -> TableDocument:
    return TableDocument(
        database_id="ecommerce",
        schema_name="public",
        table_name="t_orphan",
        table_comment="孤立表",
        columns=[ColumnDocument(name="id", data_type="bigint", nullable=False, comment="id")],
        is_junction=False,
        content_hash="sha256:orphan",
        embedding_model=None,
        embedding_version=None,
    )


class PerTableCounter:
    def count(self, text: str) -> int:
        return 1000 * sum(line.startswith("table ") for line in text.splitlines())


@pytest.mark.parametrize(
    ("left", "right", "junction"),
    [
        ("t_user", "t_region", "t_user_region_map"),
        ("t_order", "t_coupon", "t_order_coupon_rel"),
        ("t_product", "t_coupon", "t_promo_sku_rel"),
    ],
)
def test_one_hop_junction_bridges_each_seed(left: str, right: str, junction: str) -> None:
    result = expand_schema(_documents(), _edges(), [left, right], max_path_edges=1)

    assert result.connected is True
    assert result.diagnostic is None
    assert result.expanded_tables == [junction]
    assert len(result.edges) == 2
    assert {edge.source_table for edge in result.edges} == {junction}


def test_long_chain_within_depth_is_completed() -> None:
    result = expand_schema(_documents(), _edges(), ["t_user_level", "t_product"])

    assert result.connected is True
    assert result.expanded_tables == ["t_user", "t_order", "t_order_detail"]
    assert result.context_truncated is False
    assert result.diagnostic is None


def test_path_deeper_than_limit_fails() -> None:
    result = expand_schema(_documents(), _edges(), ["t_user_level", "t_category"])

    assert result.connected is False
    assert result.expanded_tables == []
    assert result.context_truncated is False
    assert result.diagnostic is not None
    assert result.diagnostic.code == "path_too_deep"


def test_table_budget_exhaustion_fails() -> None:
    result = expand_schema(
        _documents(),
        _edges(),
        ["t_user", "t_product"],
        max_total_tables=3,
    )

    assert result.connected is False
    assert result.expanded_tables == []
    assert result.context_truncated is True
    assert result.diagnostic is not None
    assert result.diagnostic.code == "budget_exceeded"


def test_token_budget_rejects_atomic_path() -> None:
    result = expand_schema(
        _documents(),
        _edges(),
        ["t_user", "t_product"],
        max_schema_tokens=2500,
        token_counter=PerTableCounter(),
    )

    assert result.connected is False
    assert result.diagnostic is not None
    assert result.diagnostic.code == "budget_exceeded"
    assert result.expanded_tables == []


def test_lowest_ranked_seed_is_dropped_when_budget_is_short() -> None:
    result = expand_schema(
        _documents(),
        _edges(),
        ["t_user", "t_product", "t_coupon"],
        max_total_tables=4,
    )

    assert result.connected is True
    assert result.context_truncated is True
    assert result.seed_tables == ["t_user", "t_product"]
    assert result.expanded_tables == ["t_order", "t_order_detail"]
    assert result.diagnostic is None
    assert any("t_coupon" in warning for warning in result.warnings)


def test_disconnected_graph_fails() -> None:
    result = expand_schema([*_documents(), _orphan()], _edges(), ["t_user", "t_orphan"])

    assert result.connected is False
    assert result.expanded_tables == []
    assert result.diagnostic is not None
    assert result.diagnostic.code == "no_path"


def test_low_confidence_inferred_edge_is_rejected() -> None:
    edge = SchemaEdge(
        source_table="t_user",
        source_columns=["user_id"],
        target_table="t_orphan",
        target_columns=["id"],
        constraint_name="inferred_user_orphan",
        weight=1.0,
        inferred=True,
        confidence=0.2,
    )
    result = expand_schema(
        [*_documents(), _orphan()],
        [*_edges(), edge],
        ["t_user", "t_orphan"],
    )

    assert result.connected is False
    assert result.diagnostic is not None
    assert result.diagnostic.code == "low_confidence_only"
    assert all(item.constraint_name != edge.constraint_name for item in result.edges)


def test_direct_foreign_key_needs_no_expansion() -> None:
    result = expand_schema(_documents(), _edges(), ["t_order", "t_user"])

    assert result.connected is True
    assert result.expanded_tables == []
    assert [edge.constraint_name for edge in result.edges] == ["t_order_user_id_fkey"]
