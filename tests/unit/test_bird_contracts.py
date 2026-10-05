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
    assert contract.group_keys == ["School Name"]
    assert contract.projections[-1] == "FreeRate"


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
