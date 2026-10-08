"""确定性 profile 补丁（实测 EX 路径，非 Gold 覆盖）。"""

from __future__ import annotations

import json

from app.agents.text_to_sql.frozen_contract import check_frozen_semantic_contract
from app.agents.text_to_sql.profile_autofix import (
    patch_profiles_for_contract,
    try_deterministic_profile_patch,
)
from app.evaluation.bird import load_bird_cases
from app.evaluation.bird_contracts import contract_for
from app.evaluation.tpcds import load_tpcds_cases
from app.evaluation.tpcds_contracts import contract_for as tpcds_contract_for
from tests.unit.bird_replay_fixtures import patch_autofix_case_path


def test_patch_profiles_from_coe_charter_contract() -> None:
    case = next(c for c in load_bird_cases() if c.id == "bird_0002")
    profiles = patch_profiles_for_contract(contract_for(case))
    assert profiles == frozenset({"coe_charter"})


def test_patch_profiles_from_hickman_contract() -> None:
    case = next(c for c in load_bird_cases() if c.id == "bird_0061")
    profiles = patch_profiles_for_contract(contract_for(case))
    assert profiles == frozenset({"hickman_frpm"})


def test_patch_profiles_from_high_frpm_unexpected_performance_contract() -> None:
    case = next(c for c in load_bird_cases() if c.id == "bird_0003")
    profiles = patch_profiles_for_contract(contract_for(case))
    assert profiles == frozenset({"high_frpm_frpm_pct"})


def test_patch_profiles_from_top_frpm_soc66_contract() -> None:
    case = next(c for c in load_bird_cases() if c.id == "bird_0032")
    profiles = patch_profiles_for_contract(contract_for(case))
    assert profiles == frozenset({"top_frpm_soc66"})


def test_patch_profiles_from_weekly_statement_demographics_contract() -> None:
    case = next(c for c in load_bird_cases() if c.id == "bird_0096")
    profiles = patch_profiles_for_contract(contract_for(case))
    assert profiles == frozenset({"weekly_statement_demographics"})


def test_patch_profiles_from_top3_sat_excellence_contract() -> None:
    case = next(c for c in load_bird_cases() if c.id == "bird_0013")
    profiles = patch_profiles_for_contract(contract_for(case))
    assert profiles == frozenset({"top3_sat_poverty"})


def test_patch_profiles_from_tpcds_023_contract() -> None:
    case = next(c for c in load_tpcds_cases() if c.id == "tpcds_complex_023")
    profiles = patch_profiles_for_contract(tpcds_contract_for(case))
    assert profiles == frozenset({"tpcds_023_stock"})


def test_tpcds_023_stock_autofix_adds_stock_cte_group_by() -> None:
    case = next(c for c in load_tpcds_cases() if c.id == "tpcds_complex_023")
    contract = tpcds_contract_for(case)
    bad = (
        "WITH sold AS (SELECT ss_item_sk AS item_sk, SUM(ss_quantity) AS quantity_sold "
        "FROM store_sales JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk "
        "WHERE date_dim.d_year = 2001 GROUP BY ss_item_sk), "
        "stock AS (SELECT warehouse.w_state AS warehouse_state, item.i_category AS item_category, "
        "date_dim.d_year AS inventory_year, inventory.inv_item_sk AS item_sk, "
        "inventory.inv_quantity_on_hand AS quantity_on_hand FROM inventory "
        "JOIN date_dim ON inventory.inv_date_sk = date_dim.d_date_sk "
        "JOIN item ON inventory.inv_item_sk = item.i_item_sk "
        "JOIN warehouse ON inventory.inv_warehouse_sk = warehouse.w_warehouse_sk "
        "WHERE date_dim.d_year = 2001) "
        "SELECT stock.warehouse_state, stock.item_category, stock.inventory_year, "
        "SUM(stock.quantity_on_hand) AS quantity_on_hand, SUM(sold.quantity_sold) AS quantity_sold "
        "FROM stock JOIN sold ON stock.item_sk = sold.item_sk "
        "GROUP BY stock.warehouse_state, stock.item_category, stock.inventory_year"
    )
    patched = try_deterministic_profile_patch("tpcds_complex_023", bad, contract)
    assert patched is not None
    assert "GROUP BY warehouse.w_state" in patched
    assert check_frozen_semantic_contract(contract, patched, dialect="postgres") == ()


def test_coe_charter_autofix_changes_peak_0002_sql() -> None:
    case_file = patch_autofix_case_path("bird_0002")
    if not case_file.is_file():
        import pytest

        pytest.skip("v15 PATCH autofix fixture missing")
    payload = json.loads(case_file.read_text())
    case = next(c for c in load_bird_cases() if c.id == "bird_0002")
    sql = payload["prediction"]["sql"]
    patched = try_deterministic_profile_patch("bird_0002", sql, contract_for(case))
    assert patched is not None
    assert patched != sql
    assert "PercentFRPM" in patched
    assert "* 100 AS PercentFRPM" not in patched
    post_findings = check_frozen_semantic_contract(contract_for(case), patched, dialect="sqlite")
    pre_findings = check_frozen_semantic_contract(contract_for(case), sql, dialect="sqlite")
    assert len(post_findings) < len(pre_findings), (pre_findings, post_findings)
    assert not any("×100" in item.message for item in post_findings)
