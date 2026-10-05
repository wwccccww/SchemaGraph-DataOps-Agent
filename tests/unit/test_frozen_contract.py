"""冻结语义契约 Prompt 与复核。"""

from __future__ import annotations

from datetime import date

from app.agents.text_to_sql.frozen_contract import (
    check_frozen_semantic_contract,
    format_frozen_semantic_contract,
)
from app.schemas.benchmark import SemanticContract, TimeWindow


def test_format_includes_projection_order_hint_when_grouped() -> None:
    contract = SemanticContract(
        projections=["a", "b", "total"],
        group_keys=["a", "b"],
        filters=["order_sensitive=true"],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    text = format_frozen_semantic_contract(contract)
    assert "投影列顺序" in text
    assert "ORDER BY" in text


def test_order_sensitive_checks_alias_order() -> None:
    contract = SemanticContract(
        projections=["School Name", "Enrollment"],
        group_keys=["School Name"],
        filters=["order_sensitive=true"],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    wrong = (
        'SELECT s."Enrollment" AS "Enrollment", s."School Name" AS "School Name" '
        'FROM schools AS s ORDER BY 2'
    )
    findings = check_frozen_semantic_contract(contract, wrong, dialect="sqlite")
    assert any("顺序" in item.message for item in findings)
    ok = (
        'SELECT s."School Name" AS "School Name", s."Enrollment" AS "Enrollment" '
        'FROM schools AS s ORDER BY 1'
    )
    assert check_frozen_semantic_contract(contract, ok, dialect="sqlite") == ()


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


def test_core_tables_reject_audited_extra_tables() -> None:
    contract = SemanticContract(
        projections=["sales_amount"],
        group_keys=[],
        filters=["core_tables=store_sales,customer,date_dim", "audit_tables_strict=true"],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    ok = "SELECT SUM(ss_ext_sales_price) AS sales_amount FROM store_sales AS ss"
    assert check_frozen_semantic_contract(contract, ok, dialect="postgres") == ()
    bad = (
        "SELECT SUM(ss_ext_sales_price) AS sales_amount FROM store_sales AS ss "
        "JOIN promotion AS p ON ss.ss_promo_sk = p.p_promo_sk"
    )
    findings = check_frozen_semantic_contract(contract, bad, dialect="postgres")
    assert any("请移除" in item.message and "promotion" in item.message for item in findings)


def test_multi_channel_flat_join_is_rejected() -> None:
    contract = SemanticContract(
        projections=["sales_amount"],
        group_keys=["sales_channel", "item_category", "sales_year"],
        filters=[
            "core_tables=store_sales,catalog_sales,web_sales,date_dim,item",
            "multi_channel_union=true",
            "audit_tables_strict=true",
        ],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    sql = (
        "SELECT SUM(ss.ss_ext_sales_price + cs.cs_ext_sales_price) "
        "FROM store_sales ss JOIN catalog_sales cs ON ss.ss_item_sk = cs.cs_item_sk"
    )
    findings = check_frozen_semantic_contract(contract, sql, dialect="postgres")
    assert any("UNION ALL" in item.message for item in findings)


def test_returns_case_rejects_channel_sales_table() -> None:
    contract = SemanticContract(
        projections=["return_amount"],
        group_keys=[],
        filters=[
            "core_tables=catalog_returns,date_dim,item,reason,warehouse,call_center",
            "primary_fact=catalog_returns",
            "audit_tables_strict=true",
        ],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    sql = (
        "SELECT SUM(cr.cr_return_amount) FROM catalog_returns AS cr "
        "JOIN catalog_sales AS cs ON cs.cs_item_sk = cr.cr_item_sk"
    )
    findings = check_frozen_semantic_contract(contract, sql, dialect="postgres")
    assert any("catalog_sales" in item.message for item in findings)


def test_wrong_channel_fact_table_is_flagged() -> None:
    contract = SemanticContract(
        projections=["net_profit"],
        group_keys=[],
        filters=["primary_fact=store_sales"],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    sql = (
        "SELECT SUM(cs_net_profit) AS net_profit FROM catalog_sales AS cs "
        "JOIN date_dim AS d ON cs.cs_sold_date_sk = d.d_date_sk WHERE d.d_year = 2001"
    )
    findings = check_frozen_semantic_contract(contract, sql, dialect="postgres")
    assert any("store_sales" in item.message and "catalog_sales" in item.message for item in findings)


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


def test_quoted_sqlite_aliases_are_detected() -> None:
    contract = SemanticContract(
        projections=["School Name"],
        group_keys=["School Name"],
        filters=[],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    sql = 'SELECT s."School Name" AS "School Name" FROM schools AS s'
    assert check_frozen_semantic_contract(contract, sql, dialect="sqlite") == ()


def test_window_and_group_by_same_select_is_flagged() -> None:
    contract = SemanticContract(
        projections=["SATRanking", "Enrollment"],
        group_keys=[],
        filters=[],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    sql = (
        "SELECT RANK() OVER (ORDER BY score DESC) AS SATRanking, enrollment AS Enrollment "
        "FROM t GROUP BY enrollment, score"
    )
    findings = check_frozen_semantic_contract(contract, sql, dialect="sqlite")
    assert any("窗口函数" in item.message for item in findings)


def test_spurious_promotion_join_is_flagged_when_not_in_core_tables() -> None:
    contract = SemanticContract(
        projections=["sales_amount"],
        group_keys=[],
        filters=["core_tables=store_sales,date_dim,item,store,customer", "primary_fact=store_sales"],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    sql = (
        "SELECT SUM(ss.ss_ext_sales_price) AS sales_amount FROM store_sales AS ss "
        "JOIN promotion AS p ON ss.ss_promo_sk = p.p_promo_sk"
    )
    findings = check_frozen_semantic_contract(contract, sql, dialect="postgres")
    assert any("promotion" in item.message for item in findings)


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
