"""Schema Graph 扩展的失败语义和三条 Junction 路径。"""

from __future__ import annotations

import re

import pytest
from app.db.ecommerce_schema import ecommerce_sql
from app.db.tables import FOREIGN_KEYS, JUNCTION_TABLES, TABLE_SPECS
from app.graph.expand import expand_schema, render_schema_context
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


def _commented_documents() -> list[TableDocument]:
    columns: dict[str, list[ColumnDocument]] = {}
    table_comments: dict[str, str] = {}
    column_comments: dict[tuple[str, str], str] = {}
    current = ""
    for line in ecommerce_sql().splitlines():
        create = re.match(r"^CREATE TABLE (t_[a-z0-9_]+) \(", line)
        if create:
            current = create.group(1)
            columns[current] = []
            continue
        column = re.match(r"^    ([a-z_]+) ", line)
        if current and column:
            columns[current].append(
                ColumnDocument(name=column.group(1), data_type="text", nullable=True)
            )
        table_comment = re.match(r"^COMMENT ON TABLE (t_[a-z0-9_]+) IS '([^']*)';$", line)
        if table_comment:
            table_comments[table_comment.group(1)] = table_comment.group(2)
        column_comment = re.match(
            r"^COMMENT ON COLUMN (t_[a-z0-9_]+)\.([a-z_]+) IS '([^']*)';$",
            line,
        )
        if column_comment:
            column_comments[(column_comment.group(1), column_comment.group(2))] = (
                column_comment.group(3)
            )
    documents: list[TableDocument] = []
    for name, specs in columns.items():
        comment = table_comments[name]
        documents.append(
            TableDocument(
                database_id="ecommerce",
                schema_name="public",
                table_name=name,
                table_comment=comment,
                columns=[
                    spec.model_copy(update={"comment": column_comments.get((name, spec.name))})
                    for spec in specs
                ],
                is_junction="[Junction Table]" in comment,
                content_hash=f"sha256:{name}",
            )
        )
    return documents


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


def test_rendered_context_includes_only_edges_inside_the_selection() -> None:
    documents = _documents()
    selected = [item for item in documents if item.table_name in {"t_order", "t_user"}]
    context = render_schema_context(selected, _edges())

    assert "join t_order.user_id = t_user.user_id" in context
    assert "t_order_detail" not in context
    assert "外键：" in context


def test_question_drops_low_confidence_seeds_and_keeps_the_named_table() -> None:
    result = expand_schema(
        _commented_documents(),
        _edges(),
        ["t_user_level", "t_coupon", "t_merchant", "t_order_detail", "t_user"],
        question="按等级编号升序查询全部会员等级的名称和折扣率",
    )

    assert result.connected is True
    assert result.seed_tables == ["t_user_level"]
    assert result.expanded_tables == []
    assert any("t_coupon" in warning for warning in result.warnings)


def test_merchant_coupon_order_uses_detail_path_not_promo() -> None:
    question = "统计自营商家使用满减优惠券的已支付订单数"
    documents = _commented_documents()
    seeds = ["t_coupon", "t_merchant", "t_order"]
    result = expand_schema(documents, _edges(), seeds, question=question)

    assert result.connected is True
    assert result.seed_tables == seeds
    assert "t_order_detail" in result.expanded_tables
    assert "t_product" in result.expanded_tables
    assert "t_order_coupon_rel" in result.expanded_tables
    assert "t_promo_sku_rel" not in result.expanded_tables
    assert "join t_order_detail.order_id = t_order.order_id" in render_schema_context(
        [item for item in documents if item.table_name in {*seeds, *result.expanded_tables}],
        result.edges,
    )


def test_applicability_question_adds_the_promo_bridge() -> None:
    result = expand_schema(
        _commented_documents(),
        _edges(),
        ["t_order", "t_product", "t_coupon"],
        question="查询已支付订单中优惠券适用于所购商品的促销记录",
    )

    assert result.connected is True
    assert "t_promo_sku_rel" in result.expanded_tables
    assert "t_order_detail" in result.expanded_tables


def test_region_question_still_adds_the_only_bridge() -> None:
    result = expand_schema(
        _commented_documents(),
        _edges(),
        ["t_user", "t_region", "t_order", "t_coupon"],
        question="统计2026年9月华东大区使用满减优惠券的已支付订单数",
    )

    assert result.connected is True
    assert "t_user_region_map" in result.expanded_tables
    assert "t_order_coupon_rel" in result.expanded_tables


def test_question_aware_expansion_covers_custom_entities_and_junctions() -> None:
    from app.evaluation.custom_cases import load_custom_cases
    from app.retrieval.dynamic import choose_schema_seeds

    documents = _commented_documents()
    edges = _edges()
    scores = {document.table_name: 0.2 for document in documents if not document.is_junction}
    entity_recall = 0.0
    junction_hits = 0
    junction_total = 0
    for case in load_custom_cases():
        seeds = [
            choice.table_name for choice in choose_schema_seeds(case.question, documents, scores)
        ]
        result = expand_schema(documents, edges, seeds, question=case.question)
        selected = set(result.seed_tables) | set(result.expanded_tables)
        assert result.connected is True
        assert set(case.required_junctions).isdisjoint(result.seed_tables)
        entity_recall += sum(name in selected for name in case.required_tables) / len(
            case.required_tables
        )
        junction_total += len(case.required_junctions)
        junction_hits += sum(name in result.expanded_tables for name in case.required_junctions)
        if "t_promo_sku_rel" not in case.required_junctions:
            assert "t_promo_sku_rel" not in result.expanded_tables

    assert entity_recall / 132 == 1.0
    assert junction_hits == junction_total == 81


def test_direct_foreign_key_needs_no_expansion() -> None:
    result = expand_schema(_documents(), _edges(), ["t_order", "t_user"])

    assert result.connected is True
    assert result.expanded_tables == []
    assert [edge.constraint_name for edge in result.edges] == ["t_order_user_id_fkey"]
