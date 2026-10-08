"""TPC-DS 派生和 BIRD 用例与冻结文件一致，且不混入自建轨道。"""

from __future__ import annotations

from app.evaluation.bird import (
    BIRD_CASE_COUNT,
    BIRD_SOURCE_VERSION,
    QUESTIONS_SHA256,
    adapt_bird_wall_clock,
    build_bird_cases,
    load_bird_cases,
    load_bird_questions,
    question_requests_order,
)
from app.evaluation.bird_contracts import contract_for as bird_contract_for
from app.evaluation.custom_cases import normalize_sql, referenced_tables
from app.evaluation.external_data import patch_tpcds_makefile, schema_statements
from app.evaluation.tpcds import (
    BUSINESS_TABLES,
    SALES_YEAR,
    TPCDS_CASE_COUNT,
    TPCDS_SOURCE_VERSION,
    build_tpcds_cases,
    load_tpcds_cases,
)
from app.evaluation.tpcds_contracts import contract_for as tpcds_contract_for
from app.evaluation.tpcds_oracle import structural_oracle_passed


def test_tpcds_cases_match_the_builder_and_cover_required_shapes() -> None:
    built = build_tpcds_cases()
    frozen = load_tpcds_cases()

    assert frozen == built
    assert len(frozen) == TPCDS_CASE_COUNT
    tags: set[str] = set()
    statements: set[str] = set()
    for case in frozen:
        assert case.source == "tpcds-derived"
        assert case.source_version == TPCDS_SOURCE_VERSION
        assert case.database_id == "tpcds"
        assert case.difficulty == "complex"
        assert case.dialect == "postgres"
        assert case.order_sensitive is False
        assert case.numeric_tolerance is None
        assert case.required_junctions == []
        assert 5 <= len(case.required_tables) <= 12
        assert set(case.required_tables) <= BUSINESS_TABLES
        assert case.required_tables == sorted(referenced_tables(case.gold_sql, dialect="postgres"))
        assert "now()" not in case.gold_sql.lower()
        assert "order by" not in normalize_sql(case.gold_sql)
        assert str(SALES_YEAR) in case.question
        assert any("\u4e00" <= char <= "\u9fff" for char in case.question)
        assert case.semantic_contract is not None
        contract = tpcds_contract_for(case)
        assert case.semantic_contract == contract
        assert case.semantic_contract.projections == case.expected_columns
        assert structural_oracle_passed(case)
        tags.update(case.tags)
        statements.add(normalize_sql(case.gold_sql))
    assert {"cte", "subquery", "aggregation", "join"} <= tags
    assert len(statements) == TPCDS_CASE_COUNT


def test_bird_cases_match_the_builder_and_keep_original_questions() -> None:
    questions = {int(str(row["question_id"])): row for row in load_bird_questions()}
    frozen = load_bird_cases()
    built = build_bird_cases()

    assert frozen == built
    assert len(frozen) == BIRD_CASE_COUNT
    assert QUESTIONS_SHA256
    seen: set[str] = set()
    for case in frozen:
        question_id = int(case.id.removeprefix("bird_"))
        original = questions[question_id]
        assert case.source == "bird"
        assert case.source_version == BIRD_SOURCE_VERSION
        assert case.database_id == original["db_id"]
        assert case.difficulty == "complex"
        assert case.dialect == "sqlite"
        assert case.question == str(original["question"]).strip()
        assert case.gold_sql == adapt_bird_wall_clock(str(original["SQL"]).strip())
        assert case.required_junctions == []
        assert case.order_sensitive is question_requests_order(case.question)
        assert case.semantic_contract is not None
        assert case.semantic_contract == bird_contract_for(case)
        assert case.semantic_contract.projections == case.expected_columns
        assert "evidence" not in case.model_dump()
        seen.add(case.database_id)
    assert seen
    assert [case.id for case in frozen] == sorted(case.id for case in frozen)


def test_order_sensitive_follows_the_question_text() -> None:
    assert question_requests_order("List schools in ascending order") is True
    assert question_requests_order("Show the names sorted by city") is True
    assert question_requests_order("Compute the total in order to compare states") is False


def test_tpcds_makefile_patch_adds_fcommon_once() -> None:
    patched = patch_tpcds_makefile("LINUX_CFLAGS\t= -g -Wall\n")
    assert patched == "LINUX_CFLAGS\t= -g -Wall -fcommon\n"
    assert patch_tpcds_makefile(patched) == patched


def test_tpcds_schema_loader_removes_primary_keys() -> None:
    statements = schema_statements(
        "\ncreate table date_dim\n(\n    d_date_sk integer not null,\n"
        "    d_year integer,\n    primary key (d_date_sk)\n);\n"
    )
    expected = "create table date_dim\n(\n    d_date_sk integer not null,\n    d_year integer\n);"
    assert statements == [("date_dim", expected)]
