"""冻结语义契约 Prompt 与复核。"""

from __future__ import annotations

from datetime import date

from app.agents.text_to_sql.frozen_contract import (
    check_frozen_semantic_contract,
    format_frozen_semantic_contract,
)
from app.schemas.benchmark import SemanticContract, TimeWindow


def test_soft_core_tables_allow_extra_joins_in_prompt() -> None:
    contract = SemanticContract(
        projections=["School", "DOC"],
        group_keys=[],
        filters=["core_tables=frpm,schools", "anchor_date=2026-10-01"],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    text = format_frozen_semantic_contract(contract)
    assert "其它维表" in text
    assert "不要 JOIN 上述清单以外" not in text


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


def test_la_k9_profile_flags_peak_0077_sql() -> None:
    import json
    from pathlib import Path

    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0077")
    run = Path(
        "/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
    )
    if not (run / "cases" / "bird_0077.json").is_file():
        import pytest

        pytest.skip("peak run fixture missing")
    sql = json.loads((run / "cases" / "bird_0077.json").read_text())["prediction"]["sql"]
    messages = [
        item.message
        for item in check_frozen_semantic_contract(case.semantic_contract, sql, dialect="sqlite")
    ]
    assert any("County" in message for message in messages)
    assert any("Poverty" in message or "Ages 5-17" in message for message in messages)


def test_admin_doc_soc_profile_flags_peak_0087_sql() -> None:
    import json
    from pathlib import Path

    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0087")
    run = Path(
        "/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
    )
    if not (run / "cases" / "bird_0087.json").is_file():
        import pytest

        pytest.skip("peak run fixture missing")
    sql = json.loads((run / "cases" / "bird_0087.json").read_text())["prediction"]["sql"]
    messages = [
        item.message
        for item in check_frozen_semantic_contract(case.semantic_contract, sql, dialect="sqlite")
    ]
    assert any("DOC=54" in message or "SOC=62" in message for message in messages)


def test_enrollment500_profile_flags_peak_0011_sql() -> None:
    import json
    from pathlib import Path

    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0011")
    run = Path(
        "/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
    )
    if not (run / "cases" / "bird_0011.json").is_file():
        import pytest

        pytest.skip("peak run fixture missing")
    sql = json.loads((run / "cases" / "bird_0011.json").read_text())["prediction"]["sql"]
    messages = [
        item.message
        for item in check_frozen_semantic_contract(case.semantic_contract, sql, dialect="sqlite")
    ]
    assert any("High FRPM" in message for message in messages)
    assert any("Ages 5-17" in message for message in messages)


def test_top10_frpm_profile_flags_peak_0008_sql() -> None:
    import json
    from pathlib import Path

    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0008")
    run = Path(
        "/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
    )
    if not (run / "cases" / "bird_0008.json").is_file():
        import pytest

        pytest.skip("peak run fixture missing")
    sql = json.loads((run / "cases" / "bird_0008.json").read_text())["prediction"]["sql"]
    messages = [
        item.message
        for item in check_frozen_semantic_contract(case.semantic_contract, sql, dialect="sqlite")
    ]
    assert any("frpm_rank" in message for message in messages)


def test_virtual_sat_f_frozen_contract_flags_peak_0005_sql() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0005")
    contract = case.semantic_contract
    assert contract is not None
    bad = (
        "SELECT s.GSserved AS SchoolType FROM schools s "
        "WHERE s.Virtual = 'Fully Virtual' "
        "AND FRPMPercentage >= 75 THEN 'High FRPM'"
    )
    messages = [
        item.message for item in check_frozen_semantic_contract(contract, bad, dialect="sqlite")
    ]
    assert any("Virtual='F'" in message for message in messages)
    assert any("GSserved" in message or "Charter" in message for message in messages)


def test_coe_charter_frozen_contract_flags_peak_run_mistakes() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0002")
    contract = case.semantic_contract
    assert contract is not None
    bad = (
        "SELECT s.School AS CharterSchoolName, "
        'f."Percent (%) Eligible FRPM (K-12)" * 100 AS PercentFRPM, '
        "CASE WHEN f.\"Percent (%) Eligible FRPM (K-12)\" >= 0.75 THEN 'High FRPM' END, "
        "CAST(strftime('%Y', s.OpenDate) AS INTEGER) AS YearOpened "
        "FROM frpm f JOIN schools s ON f.CDSCode = s.CDSCode"
    )
    messages = [
        item.message for item in check_frozen_semantic_contract(contract, bad, dialect="sqlite")
    ]
    assert any("×100" in message for message in messages)
    assert any("School Name" in message for message in messages)
    assert any(">0.75" in message or ">=" in message for message in messages)
    assert any("CAST" in message or "文本" in message for message in messages)


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
        "FROM schools AS s ORDER BY 2"
    )
    findings = check_frozen_semantic_contract(contract, wrong, dialect="sqlite")
    assert any("顺序" in item.message for item in findings)
    ok = (
        'SELECT s."School Name" AS "School Name", s."Enrollment" AS "Enrollment" '
        "FROM schools AS s ORDER BY 1"
    )
    assert check_frozen_semantic_contract(contract, ok, dialect="sqlite") == ()


def test_store_sales_demographics_use_current_cdemo_sk() -> None:
    from app.evaluation.tpcds import load_tpcds_cases

    case = next(item for item in load_tpcds_cases() if item.id == "tpcds_complex_002")
    bad = case.gold_sql.replace(
        "ON customer.c_current_cdemo_sk = customer_demographics.cd_demo_sk",
        "ON store_sales.ss_cdemo_sk = customer_demographics.cd_demo_sk",
    ).replace("JOIN customer ON", "JOIN customer ON")
    findings = check_frozen_semantic_contract(case.semantic_contract, bad, dialect="postgres")
    assert any("c_current_cdemo_sk" in item.message for item in findings)


def test_slim_loan_core_tables_reject_disp_and_status_filter() -> None:
    contract = SemanticContract(
        projections=["pct"],
        group_keys=[],
        filters=["core_tables=account,loan,trans", "anchor_date=2026-10-01"],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    bad = (
        "SELECT 1 AS pct FROM loan AS T1 JOIN account AS T2 ON T1.account_id = T2.account_id "
        "JOIN trans AS T3 ON T3.account_id = T2.account_id "
        "JOIN disp AS T4 ON T2.account_id = T4.account_id "
        "WHERE T4.type = 'OWNER' AND T1.status = 'C'"
    )
    findings = check_frozen_semantic_contract(contract, bad, dialect="sqlite")
    assert any("disp" in item.message for item in findings)
    assert any("loan.status" in item.message for item in findings)


def test_frozen_contract_rejects_extra_output_columns() -> None:
    from app.evaluation.tpcds import load_tpcds_cases

    case = next(item for item in load_tpcds_cases() if item.id == "tpcds_complex_020")
    bad = (
        "SELECT t.t_shift AS shift_name, s.s_state AS store_state, "
        "i.i_category AS item_category, d.d_year AS sales_year, "
        "SUM(ss.ss_quantity) AS quantity_sold, SUM(ss.ss_ext_sales_price) AS total_sales "
        "FROM store_sales ss "
        "JOIN date_dim d ON ss.ss_sold_date_sk = d.d_date_sk "
        "JOIN time_dim t ON ss.ss_sold_time_sk = t.t_time_sk "
        "JOIN store s ON ss.ss_store_sk = s.s_store_sk "
        "JOIN item i ON ss.ss_item_sk = i.i_item_sk "
        "WHERE d.d_year = 2001 AND d.d_weekend = 'Y' "
        "GROUP BY 1,2,3,4"
    )
    findings = check_frozen_semantic_contract(case.semantic_contract, bad, dialect="postgres")
    assert any("不要额外输出列" in item.message for item in findings)
    assert (
        check_frozen_semantic_contract(case.semantic_contract, case.gold_sql, dialect="postgres")
        == ()
    )


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


def test_web_bill_ship_requires_bill_customer_sk_join() -> None:
    from app.evaluation.tpcds import load_tpcds_cases

    case = next(item for item in load_tpcds_cases() if item.id == "tpcds_complex_013")
    bad = case.gold_sql.replace(
        "web_sales.ws_bill_customer_sk = customer.c_customer_sk",
        "customer.c_current_addr_sk = bill_address.ca_address_sk",
    ).replace("JOIN customer ON", "JOIN customer ON")
    findings = check_frozen_semantic_contract(case.semantic_contract, bad, dialect="postgres")
    assert any("ws_bill_customer_sk" in item.message for item in findings)
    assert (
        check_frozen_semantic_contract(case.semantic_contract, case.gold_sql, dialect="postgres")
        == ()
    )


def test_audit_strict_requires_all_core_tables() -> None:
    contract = SemanticContract(
        projections=["sales_amount"],
        group_keys=[],
        filters=[
            "core_tables=web_sales,customer,customer_address,date_dim,item,web_site",
            "audit_tables_strict=true",
        ],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    bad = (
        "SELECT SUM(ws_ext_sales_price) AS sales_amount FROM web_sales ws "
        "JOIN date_dim d ON ws.ws_sold_date_sk = d.d_date_sk"
    )
    findings = check_frozen_semantic_contract(contract, bad, dialect="postgres")
    assert any("customer" in item.message for item in findings)


def test_channel_pivot_rejects_web_sales_warehouse_join() -> None:
    contract = SemanticContract(
        projections=["catalog_sales_amount", "web_sales_amount"],
        group_keys=["carrier", "item_category", "sales_year"],
        filters=["channel_pivot_compare=true"],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    bad = (
        "WITH web_agg AS (SELECT SUM(ws_ext_sales_price) FROM web_sales ws "
        "JOIN warehouse w ON ws.ws_warehouse_sk = w.w_warehouse_sk) SELECT 1"
    )
    findings = check_frozen_semantic_contract(contract, bad, dialect="postgres")
    assert any("web_sales" in item.message and "warehouse" in item.message for item in findings)


def test_core_tables_reject_audited_extra_tables() -> None:
    contract = SemanticContract(
        projections=["sales_amount"],
        group_keys=[],
        filters=["core_tables=store_sales,customer,date_dim", "audit_tables_strict=true"],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    ok = (
        "SELECT SUM(ss_ext_sales_price) AS sales_amount FROM store_sales AS ss "
        "JOIN customer c ON ss.ss_customer_sk = c.c_customer_sk "
        "JOIN date_dim d ON ss.ss_sold_date_sk = d.d_date_sk"
    )
    assert check_frozen_semantic_contract(contract, ok, dialect="postgres") == ()
    bad = (
        "SELECT SUM(ss_ext_sales_price) AS sales_amount FROM store_sales AS ss "
        "JOIN promotion AS p ON ss.ss_promo_sk = p.p_promo_sk"
    )
    findings = check_frozen_semantic_contract(contract, bad, dialect="postgres")
    assert any("请移除" in item.message and "promotion" in item.message for item in findings)


def test_dmail_promotion_join_is_rejected() -> None:
    contract = SemanticContract(
        projections=["net_profit"],
        group_keys=["education_status"],
        filters=["promotion_channel=dmail", "promotion_via_item_sk_subquery=true"],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    sql = (
        "SELECT SUM(ss.ss_net_profit) FROM store_sales ss "
        "JOIN promotion p ON ss.ss_promo_sk = p.p_promo_sk WHERE p.p_channel_dmail = 'Y'"
    )
    findings = check_frozen_semantic_contract(contract, sql, dialect="postgres")
    assert any("IN (SELECT" in item.message for item in findings)


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
    assert any(
        "store_sales" in item.message and "catalog_sales" in item.message for item in findings
    )


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
        filters=[
            "core_tables=store_sales,date_dim,item,store,customer",
            "primary_fact=store_sales",
        ],
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


def test_returns_amount_rejects_inc_tax_column() -> None:
    from app.evaluation.tpcds import load_tpcds_cases

    case = next(item for item in load_tpcds_cases() if item.id == "tpcds_complex_005")
    bad = case.gold_sql.replace("cr_return_amount", "cr_return_amt_inc_tax")
    findings = check_frozen_semantic_contract(case.semantic_contract, bad, dialect="postgres")
    assert any("inc_tax" in item.message or "含税" in item.message for item in findings)
    assert (
        check_frozen_semantic_contract(case.semantic_contract, case.gold_sql, dialect="postgres")
        == ()
    )


def test_income_band_rejects_ss_hdemo_sk_shortcut() -> None:
    contract = SemanticContract(
        projections=["income_lower", "buy_potential", "sales_amount"],
        group_keys=["income_lower", "buy_potential"],
        filters=[
            "core_tables=customer,date_dim,household_demographics,income_band,item,store_sales",
            "primary_fact=store_sales",
        ],
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
    bad = (
        "SELECT ib.ib_lower_bound AS income_lower, hd.hd_buy_potential AS buy_potential, "
        "SUM(ss.ss_ext_sales_price) AS sales_amount FROM store_sales ss "
        "JOIN household_demographics hd ON ss.ss_hdemo_sk = hd.hd_demo_sk "
        "JOIN income_band ib ON hd.hd_income_band_sk = ib.ib_income_band_sk "
        "GROUP BY ib.ib_lower_bound, hd.hd_buy_potential"
    )
    findings = check_frozen_semantic_contract(contract, bad, dialect="postgres")
    assert any("c_current_hdemo_sk" in item.message for item in findings)


def test_multi_channel_union_skips_sk_heavy_cte_warning() -> None:
    from app.evaluation.tpcds import load_tpcds_cases

    case = next(item for item in load_tpcds_cases() if item.id == "tpcds_complex_008")
    assert (
        check_frozen_semantic_contract(case.semantic_contract, case.gold_sql, dialect="postgres")
        == ()
    )


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
