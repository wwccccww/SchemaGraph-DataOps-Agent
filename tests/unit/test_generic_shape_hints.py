"""Generic 输出形状对 BIRD 英文问句的启发式检查。"""

from __future__ import annotations

from app.agents.text_to_sql.shape import check_answer_shape
from app.schemas.catalog import TableDocument


def _schools_doc() -> TableDocument:
    return TableDocument(
        database_id="california_schools",
        schema_name="main",
        table_name="schools",
        table_comment=None,
        columns=[],
        is_junction=False,
        content_hash="sha256:schools",
    )


def test_sat_performance_level_requires_case_bucket() -> None:
    question = "What is its SAT performance level?"
    sql = 'SELECT s."AvgScrRead", s."AvgScrMath" FROM satscores AS s'
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    messages = [item.message for item in findings if item.category == "projection_mismatch"]
    assert any("CASE" in message for message in messages)


def test_charter_prefers_schools_table() -> None:
    question = "Is it a charter school?"
    sql = (
        'SELECT f."Charter School (Y/N)" FROM frpm AS f '
        'LEFT JOIN schools AS s ON f.CDSCode = s.CDSCode'
    )
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    messages = [item.message for item in findings]
    assert any("schools" in message and "Charter" in message for message in messages)
