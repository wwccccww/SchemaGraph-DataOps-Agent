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


def test_returns_and_sales_question_adds_separate_cte_hint() -> None:
    contract = contract_for(
        _case(
            question="统计 2001 年门店销售与门店退货金额，按原因和类别汇总。",
            required_tables=["store_sales", "store_returns", "date_dim", "item", "reason", "store"],
        )
    )
    assert "returns_vs_sales=separate_cte" in contract.filters


def test_channel_question_picks_catalog_sales() -> None:
    contract = contract_for(
        _case(
            question="统计 2001 年目录销售和门店销售。",
            required_tables=["catalog_sales", "store_sales", "date_dim", "item", "customer"],
        )
    )
    assert any(item.startswith("primary_facts=") for item in contract.filters)
