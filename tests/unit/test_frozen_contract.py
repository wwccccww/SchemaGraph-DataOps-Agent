"""冻结语义契约 Prompt 与复核。"""

from __future__ import annotations

from datetime import date

from app.agents.text_to_sql.frozen_contract import (
    check_frozen_semantic_contract,
    format_frozen_semantic_contract,
)
from app.schemas.benchmark import SemanticContract, TimeWindow


def test_format_includes_projections_and_item_hint() -> None:
    contract = SemanticContract(
        projections=["income_lower", "item_category", "sales_amount"],
        group_keys=["income_lower", "item_category"],
        filters=["calendar_year=2001"],
        category_scope="exact",
        time_window=TimeWindow(
            start="2001-01-01",
            end="2002-01-01",
            anchor_date=date(2026, 10, 1),
        ),
        dedup_key=None,
    )
    text = format_frozen_semantic_contract(contract)
    assert "item_category" in text
    assert "item" in text


def test_primary_fact_filter_requires_store_sales() -> None:
    contract = SemanticContract(
        projections=["sales_amount"],
        group_keys=[],
        filters=["primary_fact=store_sales"],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    bad = "SELECT SUM(cs_net_profit) FROM catalog_sales"
    findings = check_frozen_semantic_contract(contract, bad, dialect="postgres")
    assert any("store_sales" in item.message for item in findings)


def test_check_requires_item_when_item_category_projected() -> None:
    contract = SemanticContract(
        projections=["item_category", "sales_amount"],
        group_keys=["item_category"],
        filters=[],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    sql = (
        "SELECT i.i_category AS item_category, SUM(ss.ss_ext_sales_price) AS sales_amount "
        "FROM store_sales AS ss JOIN item AS i ON ss.ss_item_sk = i.i_item_sk "
        "GROUP BY i.i_category"
    )
    assert check_frozen_semantic_contract(contract, sql, dialect="postgres") == ()
    bad = "SELECT SUM(ss.ss_ext_sales_price) AS sales_amount FROM store_sales AS ss"
    findings = check_frozen_semantic_contract(contract, bad, dialect="postgres")
    assert any(item.category == "missing_entity" for item in findings)
