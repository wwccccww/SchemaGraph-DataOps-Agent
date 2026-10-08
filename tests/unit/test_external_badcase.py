"""外部 badcase 分类。"""

from __future__ import annotations

from datetime import date

from app.evaluation.external_badcase import classify_external_case
from app.schemas.benchmark import BenchmarkCase


def _case(**overrides: object) -> BenchmarkCase:
    base = BenchmarkCase(
        id="bird_0001",
        source="bird",
        source_version="v1",
        database_id="financial",
        difficulty="complex",
        dialect="sqlite",
        question="How many accounts?",
        gold_sql="SELECT COUNT(*) AS total FROM account",
        required_tables=["account"],
        required_junctions=[],
        order_sensitive=False,
        numeric_tolerance=None,
        expected_columns=["total"],
        anchor_date=date(2026, 10, 1),
        tags=[],
    )
    return base.model_copy(update=overrides)


def test_cross_database_leak_is_a_sql_error() -> None:
    coarse, detail, symptoms = classify_external_case(
        _case(),
        predicted_sql=None,
        error_category=None,
        ex=0,
        leaked_tables=("t_order",),
    )
    assert coarse == "sql_error"
    assert detail == "cross_database_leak"
    assert symptoms


def test_missing_table_maps_to_other_result_mismatch() -> None:
    coarse, detail, _ = classify_external_case(
        _case(required_tables=["account", "loan"]),
        predicted_sql="SELECT COUNT(*) AS total FROM account",
        error_category=None,
        ex=0,
        leaked_tables=(),
    )
    assert coarse == "other_result_mismatch"
    assert detail == "missing_required_table"
