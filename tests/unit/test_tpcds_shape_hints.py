"""TPC-DS 问句的形状与种子启发式。"""

from __future__ import annotations

from app.agents.text_to_sql.shape import extract_generic_shape, format_generic_shape
from app.datasources.seeds import lexical_schema_seeds
from app.schemas.catalog import ColumnDocument, TableDocument


def _doc(name: str) -> TableDocument:
    return TableDocument(
        database_id="tpcds",
        schema_name="public",
        table_name=name,
        table_comment=None,
        columns=[
            ColumnDocument(name="id", data_type="int", nullable=False, comment=None),
        ],
        is_junction=False,
        content_hash=f"sha256:{name}",
    )


def test_inventory_sold_through_store_does_not_require_store_entity() -> None:
    question = "统计 2001 年各仓库所在州和商品类别的库存数量，只保留当年门店卖过的商品。"
    documents = [
        _doc(name)
        for name in ("inventory", "item", "store_sales", "store", "warehouse", "date_dim")
    ]
    shape = extract_generic_shape(question, documents)
    assert "store_sales" in shape.entities
    assert "store" not in shape.entities


def test_item_category_question_does_not_require_promotion() -> None:
    question = "统计 2001 年能关联到当前住址的顾客，在各州门店购买各商品类别的销售金额。"
    documents = [
        _doc(name)
        for name in (
            "customer",
            "customer_address",
            "item",
            "promotion",
            "store",
            "store_sales",
            "date_dim",
        )
    ]
    shape = extract_generic_shape(question, documents)
    assert "promotion" not in shape.entities
    assert "item" in shape.entities


def test_promo_item_question_requires_item_entity_and_join_hint() -> None:
    question = "统计 2001 年购买过直邮促销商品的顾客，按教育程度和信用评级汇总净利润。"
    documents = [
        _doc(name)
        for name in (
            "customer",
            "item",
            "promotion",
            "store_sales",
            "customer_demographics",
            "date_dim",
        )
    ]
    shape = extract_generic_shape(question, documents)
    assert "item" in shape.entities
    text = format_generic_shape(shape)
    assert "item" in text
    assert "promotion" in text
    assert any("促销商品" in line for line in shape.joins)


def test_grouped_call_center_dimension_requires_call_center_entity() -> None:
    question = "统计 2001 年各呼叫中心、配送方式和商品类别的目录销售金额。"
    documents = [
        _doc(name)
        for name in ("call_center", "ship_mode", "item", "catalog_sales", "date_dim")
    ]
    shape = extract_generic_shape(question, documents)
    assert "call_center" in shape.entities
    assert "ship_mode" in shape.entities


def test_lexical_seeds_include_item_for_promo_product_question() -> None:
    question = "购买过直邮促销商品的顾客数量"
    documents = [_doc(name) for name in ("customer", "item", "promotion", "store_sales")]
    seeds = lexical_schema_seeds(question, documents)
    names = {seed.table_name for seed in seeds}
    assert "item" in names
    assert "promotion" in names
