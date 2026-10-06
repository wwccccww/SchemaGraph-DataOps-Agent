"""BIRD 语义契约。"""

from __future__ import annotations

from datetime import date

from app.evaluation.bird_contracts import contract_for
from app.schemas.benchmark import BenchmarkCase


def test_bird_contract_lists_core_tables_and_projections() -> None:
    case = BenchmarkCase.model_validate(
        {
            "id": "bird_0001",
            "source": "bird",
            "source_version": "test",
            "database_id": "california_schools",
            "difficulty": "complex",
            "dialect": "sqlite",
            "question": "List schools in ascending order",
            "gold_sql": "SELECT 1",
            "required_tables": ["schools", "frpm"],
            "required_junctions": [],
            "order_sensitive": True,
            "numeric_tolerance": None,
            "expected_columns": ["School Name", "FreeRate"],
            "anchor_date": date(2026, 10, 1),
            "tags": [],
        }
    )
    contract = contract_for(case)
    assert contract.projections == ["School Name", "FreeRate"]
    assert "core_tables=frpm,schools" in contract.filters
    assert "order_sensitive=true" in contract.filters
    assert "anchor_date=2026-10-01" in contract.filters
    assert contract.group_keys == []
    assert contract.projections[-1] == "FreeRate"


def test_bird_0032_contract_includes_top_frpm_soc66_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0032")
    assert "top_frpm_soc66_profile=true" in contract_for(case).filters


def test_bird_0010_contract_includes_top_reading_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0010")
    assert "top_reading_sat_profile=true" in contract_for(case).filters


def test_bird_0006_contract_includes_magnet_sat_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0006")
    contract = contract_for(case)
    assert "magnet_sat_profile=true" in contract.filters


def test_bird_0008_contract_includes_top10_high_frpm_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0008")
    assert "top10_high_frpm_profile=true" in contract_for(case).filters


def test_bird_0011_contract_includes_enrollment500_frpm_sat_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0011")
    assert "enrollment500_frpm_sat_profile=true" in contract_for(case).filters


def test_bird_0005_contract_includes_virtual_sat_f_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0005")
    assert "virtual_sat_f_profile=true" in contract_for(case).filters


def test_bird_0002_contract_includes_coe_charter_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0002")
    contract = contract_for(case)
    assert "coe_charter_profile=true" in contract.filters
    text = __import__(
        "app.agents.text_to_sql.frozen_contract", fromlist=["format_frozen_semantic_contract"]
    ).format_frozen_semantic_contract(contract)
    assert "PercentFRPM 用小数列" in text


def test_bird_contract_does_not_treat_last_column_as_measure() -> None:
    case = BenchmarkCase.model_validate(
        {
            "id": "bird_0028",
            "source": "bird",
            "source_version": "test",
            "database_id": "california_schools",
            "difficulty": "complex",
            "dialect": "sqlite",
            "question": "Schools above average enrollment difference",
            "gold_sql": "SELECT 1",
            "required_tables": ["frpm", "schools"],
            "required_junctions": [],
            "order_sensitive": False,
            "numeric_tolerance": None,
            "expected_columns": ["School", "DOC"],
            "anchor_date": date(2026, 10, 1),
            "tags": [],
        }
    )
    contract = contract_for(case)
    assert contract.group_keys == []
