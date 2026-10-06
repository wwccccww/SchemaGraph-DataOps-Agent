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


def test_bird_0020_contract_includes_amador_high_school_stats_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0020")
    assert "amador_high_school_stats_profile=true" in contract_for(case).filters


def test_bird_0031_contract_includes_enrollment_rank_10_11_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0031")
    assert "enrollment_rank_10_11_profile=true" in contract_for(case).filters


def test_bird_0045_contract_includes_ricci_ulrich_admin_sat_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0045")
    assert "ricci_ulrich_admin_sat_profile=true" in contract_for(case).filters


def test_bird_0078_contract_includes_adelanto_grade_span_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0078")
    assert "adelanto_grade_span_profile=true" in contract_for(case).filters


def test_bird_0061_contract_includes_hickman_elementary_charter_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0061")
    assert "hickman_elementary_charter_profile=true" in contract_for(case).filters


def test_bird_0100_contract_includes_sokolov_pre1950_female_owner_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0100")
    assert "sokolov_pre1950_female_owner_profile=true" in contract_for(case).filters


def test_bird_0019_contract_includes_top_math_sat_active_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0019")
    assert "top_math_sat_active_profile=true" in contract_for(case).filters


def test_bird_0013_contract_includes_top3_sat_excellence_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0013")
    assert "top3_sat_excellence_profile=true" in contract_for(case).filters


def test_bird_0012_contract_includes_sat_excellence_county_free_meal_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0012")
    assert "sat_excellence_county_free_meal_profile=true" in contract_for(case).filters


def test_bird_0062_contract_includes_la_low_free_meal_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0062")
    assert "la_low_free_meal_profile=true" in contract_for(case).filters


def test_bird_0018_contract_includes_fresno_direct_funded_charter_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0018")
    assert "fresno_direct_funded_charter_profile=true" in contract_for(case).filters


def test_bird_0055_contract_includes_colusa_humboldt_ratio_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0055")
    assert "colusa_humboldt_ratio_profile=true" in contract_for(case).filters


def test_bird_0003_contract_includes_high_frpm_unexpected_performance_profile() -> None:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == "bird_0003")
    assert "high_frpm_unexpected_performance_profile=true" in contract_for(case).filters


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
