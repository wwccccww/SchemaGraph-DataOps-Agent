"""Generic 输出形状对 BIRD 英文问句的启发式检查。"""

from __future__ import annotations

from app.agents.text_to_sql.prompt import GENERIC_PROMPT_VERSION, system_prompt_for
from app.agents.text_to_sql.shape import check_answer_shape
from app.schemas.catalog import TableDocument


def test_generic_prompt_v52_includes_large_loan_and_prachatice() -> None:
    assert GENERIC_PROMPT_VERSION == "text-to-sql-generic-v52"
    sqlite_system = system_prompt_for(dialect="sqlite", profile="generic")
    assert "rtype='S'" in sqlite_system
    assert "PerformanceClassification" in sqlite_system
    assert "despite high FRPM" in sqlite_system
    assert "High/Medium/Low" in sqlite_system
    assert "MailStreet" in sqlite_system
    assert "Total Schools Ratio" in sqlite_system
    assert "ROW_NUMBER()" in sqlite_system
    assert "IN (10,11)" in sqlite_system
    assert "Equal to District Average" in sqlite_system
    assert "Ricci" in sqlite_system
    assert "Adelanto" in sqlite_system
    assert "grade_span_rank" in sqlite_system
    assert "DOC='52'" in sqlite_system
    assert "High Performing" in sqlite_system or "Performing" in sqlite_system
    assert "A2='Sokolov'" in sqlite_system
    assert "status'D'" in sqlite_system or "status='D'" in sqlite_system
    assert "1994-03-03" in sqlite_system
    assert "A11" in sqlite_system
    assert "GROUP_CONCAT" in sqlite_system
    assert "salary_rank_in_region" in sqlite_system
    assert "1994-08-25" in sqlite_system
    assert "PRIJEM" in sqlite_system
    assert "1996-10-21" in sqlite_system
    assert "High Value" in sqlite_system or "Low Value" in sqlite_system
    assert "Litomerice" in sqlite_system
    assert "PRIJEM" in sqlite_system
    assert "1976-01-29" in sqlite_system
    assert "Same as residence" in sqlite_system
    assert "98832" in sqlite_system
    assert "1996-01-03" in sqlite_system
    assert "south Bohemia" in sqlite_system
    assert "population_rank" in sqlite_system
    assert "4990" in sqlite_system
    assert "Finished-No Issues" in sqlite_system
    assert "paid_amount_percentage DESC" in sqlite_system
    assert "status='A' 计 paid" in sqlite_system or "status='A'" in sqlite_system
    assert "Prachatice" in sqlite_system
    assert "ROW_NUMBER" in sqlite_system
    assert "High Activity" in sqlite_system
    assert "300000" in sqlite_system
    assert "High/Medium/Low Income" in sqlite_system
    assert "region_loan_rank" in sqlite_system


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
        "SELECT CASE WHEN f.\"Percent (%) Eligible FRPM (K-12)\" * 100 < 40 THEN 'High' END "
        "FROM frpm f WHERE f.\"County Name\" = 'Fresno County Office of Education'"
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
        "WHERE f.\"District Name\" = 'Fresno County Office of Education' "
        'AND f."Charter School (Y/N)" = 1'
    )
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    messages = [item.message for item in findings]
    assert not any("不要用 frpm 的 Y/N" in message for message in messages)


def test_fully_virtual_flags_literal_fully_virtual_filter() -> None:
    question = "What are the details of fully virtual schools that have an average SAT Math score above 400?"
    sql = "SELECT s.School FROM schools s WHERE s.Virtual = 'Fully Virtual' AND s.GSserved AS SchoolType"
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    messages = [item.message for item in findings]
    assert any("Virtual='F'" in message for message in messages)
    assert any("GSserved" in message or "Charter School" in message for message in messages)


def test_coe_charter_flags_percent_frpm_times_100() -> None:
    question = (
        "For charter schools in Fresno County Office of Education, categorizing schools "
        "by their FRPM percentage levels."
    )
    sql = (
        'SELECT f."Percent (%) Eligible FRPM (K-12)" * 100 AS PercentFRPM FROM frpm f '
        "WHERE f.\"District Name\" = 'Fresno County Office of Education'"
    )
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    assert any("不要 ×100" in item.message for item in findings)


def test_top_reading_sat_flags_k12_frpm_and_limit_one() -> None:
    question = (
        "For the school with the highest average SAT Reading score among schools "
        "with more than 10 test takers, provide poverty indicators."
    )
    sql = (
        'SELECT f."Enrollment (K-12)" FROM schools s JOIN satscores ss ON ss.cds=s.CDSCode '
        "JOIN frpm f ON f.CDSCode=s.CDSCode ORDER BY ss.AvgScrRead DESC LIMIT 1"
    )
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    messages = [item.message for item in findings]
    assert any("Ages 5-17" in m for m in messages)
    assert any("ReadingRank=1" in m for m in messages)


def test_magnet_sat_flags_frpm_school_type_and_poverty_labels() -> None:
    question = (
        "For magnet schools with over 500 SAT test takers, provide poverty levels "
        "and performance categories."
    )
    sql = (
        "SELECT CASE WHEN x >= 75 THEN 'High FRPM' END, 'Above Average' AS PerformanceCategory "
        'FROM frpm f JOIN schools s ON 1=1 WHERE f."Free Meal Count (K-12)" * 100 / '
        'f."Enrollment (K-12)" > 0'
    )
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    messages = [item.message for item in findings]
    assert any("High Poverty" in m for m in messages)
    assert any("Excellent" in m for m in messages)
    assert any("Percent (%) Eligible FRPM" in m or "Free Meal Count" in m for m in messages)


def test_top_n_cte_order_limit_flagged() -> None:
    question = "For the top 5 schools with the highest FRPM count, list details."
    sql = "WITH base AS (SELECT 1 AS x FROM frpm ORDER BY x DESC LIMIT 5) SELECT * FROM base"
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    assert any("RANK()" in item.message for item in findings)


def test_charter_prefers_schools_table() -> None:
    question = "Is it a charter school?"
    sql = (
        'SELECT f."Charter School (Y/N)" FROM frpm AS f '
        "LEFT JOIN schools AS s ON f.CDSCode = s.CDSCode"
    )
    findings = check_answer_shape(question, sql, (_schools_doc(),), dialect="sqlite")
    messages = [item.message for item in findings]
    assert any("schools" in message and "Charter" in message for message in messages)
