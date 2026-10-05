"""TPC-DS 语义契约生成。"""

from __future__ import annotations

from datetime import date

from app.evaluation.tpcds_contracts import contract_for
from app.schemas.benchmark import BenchmarkCase


def _case(**overrides: object) -> BenchmarkCase:
    base = {
        "id": "tpcds_complex_test",
        "source": "tpcds-derived",
        "source_version": "test",
        "database_id": "tpcds",
        "difficulty": "complex",
        "dialect": "postgres",
        "question": "统计 2001 年门店销售金额。",
        "gold_sql": "SELECT 1",
        "required_tables": ["store_sales", "date_dim", "item", "store", "customer"],
        "required_junctions": [],
        "order_sensitive": False,
        "numeric_tolerance": None,
        "expected_columns": ["sales_amount"],
        "anchor_date": date(2026, 10, 1),
        "tags": [],
    }
    base.update(overrides)
    return BenchmarkCase.model_validate(base)


def test_single_fact_filter_from_required_tables() -> None:
    contract = contract_for(_case())
    assert "primary_fact=store_sales" in contract.filters
    assert "core_tables=customer,date_dim,item,store,store_sales" in contract.filters
    assert "audit_tables_strict=true" in contract.filters


def test_dmail_question_adds_subquery_filter() -> None:
    contract = contract_for(
        _case(question="统计 2001 年购买过直邮促销商品的顾客净利润。")
    )
    assert "promotion_via_item_sk_subquery=true" in contract.filters


def test_generic_promo_name_question_does_not_add_dmail_filter() -> None:
    contract = contract_for(
        _case(
            question="统计 2001 年各促销名称、门店所在州和商品类别的销售金额。",
            required_tables=[
                "customer",
                "date_dim",
                "item",
                "promotion",
                "store",
                "store_sales",
            ],
            expected_columns=[
                "promo_name",
                "store_state",
                "item_category",
                "sales_year",
                "sales_amount",
            ],
        )
    )
    assert "promotion_via_item_sk_subquery=true" not in contract.filters
    assert "promotion_channel=dmail" not in contract.filters


def test_multi_channel_question_adds_union_hint() -> None:
    contract = contract_for(
        _case(
            question="按销售渠道汇总 2001 年门店、目录和网站销售金额。",
            required_tables=["store_sales", "catalog_sales", "web_sales", "date_dim", "item"],
        )
    )
    assert "multi_channel_union=true" in contract.filters


def test_returns_and_sales_question_adds_separate_cte_hint() -> None:
    contract = contract_for(
        _case(
            question="统计 2001 年门店销售与门店退货金额，按原因和类别汇总。",
            required_tables=["store_sales", "store_returns", "date_dim", "item", "reason", "store"],
        )
    )
    assert "returns_vs_sales=separate_cte" in contract.filters


def test_quantity_on_hand_is_measure_not_group_key() -> None:
    contract = contract_for(
        _case(
            question="统计 2001 年各仓库所在州和商品类别的在手库存，并汇总这些库存商品当年的门店销售数量。",
            required_tables=["inventory", "warehouse", "item", "store_sales", "date_dim"],
            expected_columns=[
                "warehouse_state",
                "item_category",
                "inventory_year",
                "quantity_on_hand",
                "quantity_sold",
            ],
        )
    )
    assert "quantity_on_hand" not in contract.group_keys
    assert "quantity_sold" not in contract.group_keys


def test_inventory_qty_uses_join_cte_not_subquery() -> None:
    contract = contract_for(
        _case(
            question="统计 2001 年各仓库所在州和商品类别的在手库存，并汇总这些库存商品当年的门店销售数量。",
            required_tables=["inventory", "warehouse", "item", "store_sales", "date_dim"],
            expected_columns=[
                "warehouse_state",
                "item_category",
                "inventory_year",
                "quantity_on_hand",
                "quantity_sold",
            ],
        )
    )
    assert "inventory_sold_qty=join_sold_cte" in contract.filters
    assert "inventory_sold_items=subquery" not in contract.filters


def test_same_store_return_sales_filter() -> None:
    contract = contract_for(
        _case(
            question="统计 2001 年电子类商品中，同年同店发生过退货的销售，按门店州汇总销售金额。",
            required_tables=[
                "store_sales",
                "store_returns",
                "store",
                "customer",
                "item",
                "date_dim",
                "reason",
            ],
            expected_columns=["store_state", "sales_amount"],
        )
    )
    assert "return_linked_sales=item_store_year" in contract.filters


def test_cross_channel_buyers_not_union() -> None:
    contract = contract_for(
        _case(
            question="统计 2001 年既在门店又在网站购买过的顾客，按顾客所在州汇总门店销售金额。",
            required_tables=[
                "customer",
                "customer_address",
                "date_dim",
                "item",
                "store_sales",
                "web_sales",
            ],
            expected_columns=["customer_state", "sales_amount"],
        )
    )
    assert "cross_channel_buyers=customer_and_item" in contract.filters
    assert "multi_channel_union=true" not in contract.filters


def test_compare_question_uses_channel_pivot() -> None:
    contract = contract_for(
        _case(
            question="比较 2001 年同一商品类别在网站和门店的销售金额。",
            required_tables=["store_sales", "web_sales", "date_dim", "item", "store", "web_site"],
            expected_columns=["item_category", "store_sales_amount", "web_sales_amount"],
        )
    )
    assert "channel_pivot_compare=true" in contract.filters
    assert "multi_channel_union=true" not in contract.filters


def test_channel_question_picks_catalog_sales() -> None:
    contract = contract_for(
        _case(
            question="统计 2001 年目录销售和门店销售。",
            required_tables=["catalog_sales", "store_sales", "date_dim", "item", "customer"],
        )
    )
    assert any(item.startswith("primary_facts=") for item in contract.filters)
