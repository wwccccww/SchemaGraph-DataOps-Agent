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


def test_rank_window_counts_as_aggregate_for_shape_checks() -> None:
    from app.agents.text_to_sql.shape import _AGGREGATE

    assert _AGGREGATE.search("SELECT RANK() OVER (ORDER BY enrollment DESC) FROM schools")


def test_frpm_category_labels_for_coe_charter() -> None:
    question = (
        "For charter schools in Fresno County Office of Education, categorizing schools "
        "by their FRPM percentage levels."
    )
    sql = (
        'SELECT CASE WHEN f."Percent (%) Eligible FRPM (K-12)" * 100 < 40 THEN \'High\' END '
        'FROM frpm f WHERE f."County Name" = \'Fresno County Office of Education\''
    )
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    messages = [item.message for item in findings]
    assert any("District Name" in message for message in messages)
    assert any("High FRPM" in message for message in messages)


def test_loan_running_ok_uses_count_status() -> None:
    loan_doc = TableDocument(
        database_id="financial",
        schema_name="main",
        table_name="loan",
        table_comment=None,
        columns=[],
        is_junction=False,
        content_hash="sha256:loan",
    )
    question = "What is the percentage of loans running with no issues in each region?"
    sql = (
        "SELECT ROUND(100.0 * SUM(x) / COUNT(*), 2), ROUND(AVG(duration), 2) "
        "FROM loan GROUP BY region"
    )
    findings = check_answer_shape(question, sql, (loan_doc,), dialect="sqlite")
    messages = [item.message for item in findings]
    assert any("COUNT(status)" in message for message in messages)


def test_coe_charter_does_not_forbid_frpm_charter_filter() -> None:
    question = (
        "For charter schools in Fresno County Office of Education, categorizing schools "
        "by their FRPM percentage levels."
    )
    sql = (
        'SELECT f."School Name" FROM frpm AS f JOIN schools AS s ON f.CDSCode = s.CDSCode '
        'WHERE f."District Name" = \'Fresno County Office of Education\' '
        'AND f."Charter School (Y/N)" = 1'
    )
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    messages = [item.message for item in findings]
    assert not any("不要用 frpm 的 Y/N" in message for message in messages)


def test_coe_charter_flags_percent_frpm_times_100() -> None:
    question = (
        "For charter schools in Fresno County Office of Education, categorizing schools "
        "by their FRPM percentage levels."
    )
    sql = (
        'SELECT f."Percent (%) Eligible FRPM (K-12)" * 100 AS PercentFRPM FROM frpm f '
        'WHERE f."District Name" = \'Fresno County Office of Education\''
    )
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    assert any("不要 ×100" in item.message for item in findings)


def test_top_n_cte_order_limit_flagged() -> None:
    question = "For the top 5 schools with the highest FRPM count, list details."
    sql = (
        "WITH base AS (SELECT 1 AS x FROM frpm ORDER BY x DESC LIMIT 5) "
        "SELECT * FROM base"
    )
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    assert any("RANK()" in item.message for item in findings)


def test_charter_prefers_schools_table() -> None:
    question = "Is it a charter school?"
    sql = (
        'SELECT f."Charter School (Y/N)" FROM frpm AS f '
        'LEFT JOIN schools AS s ON f.CDSCode = s.CDSCode'
    )
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    messages = [item.message for item in findings]
    assert any("schools" in message and "Charter" in message for message in messages)
