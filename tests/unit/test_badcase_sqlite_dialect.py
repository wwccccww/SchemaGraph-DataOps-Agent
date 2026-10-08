"""BIRD Gold 为 SQLite，badcase 须用 case.dialect 解析 Gold。"""

from __future__ import annotations

from app.evaluation.badcase import classify_badcase
from app.evaluation.bird import load_bird_cases


def test_bird_gold_projections_are_not_empty_with_sqlite_dialect() -> None:
    case = next(item for item in load_bird_cases() if item.id == "bird_0002")
    predicted = case.gold_sql.replace("High FRPM", "Low FRPM")
    detail, symptoms = classify_badcase(
        question=case.question,
        gold_sql=case.gold_sql,
        predicted_sql=predicted,
        required_tables=case.required_tables,
        error_category=None,
        ex=0,
        anchor_date=case.anchor_date.isoformat(),
        repair_trace=(),
        dialect=case.dialect,
    )
    assert detail != "response_shape"
    extra = next(value for key, value in symptoms if key == "extra_projections")
    assert extra == ""
