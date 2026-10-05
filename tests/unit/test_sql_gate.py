"""SQLGlot 门禁拒绝写操作，并放行冒烟 Gold SQL。"""

from __future__ import annotations

import pytest
from app.evaluation.smoke import load_smoke_cases
from app.sandbox.gate import check_read_only_sql


def test_smoke_gold_sql_passes_the_read_only_gate() -> None:
    cases = load_smoke_cases()

    assert len(cases) == 10
    for case in cases:
        decision = check_read_only_sql(case.gold_sql)
        assert decision.error is None
        assert decision.sql.upper().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO t_user_level VALUES (1, 'x', 1)",
        "UPDATE t_user SET nickname = 'x'",
        "DELETE FROM t_order",
        "MERGE INTO t_user USING t_user_level ON true WHEN MATCHED THEN DELETE",
        "CREATE TABLE phase4_forbidden (id INT)",
        "DROP TABLE t_user",
        "TRUNCATE t_order",
        "COPY t_user TO STDOUT",
        "SELECT 1; SELECT 2",
        (
            "WITH changed AS (UPDATE t_user SET nickname = 'x' RETURNING user_id) "
            "SELECT * FROM changed"
        ),
        "SELECT pg_sleep(1)",
        "SELECT pg_catalog.pg_sleep(1)",
        "SELECT nextval('t_user_user_id_seq')",
        "SELECT set_config('statement_timeout', '1h', false)",
        "SELECT public.evil(1)",
        "SELECT * FROM t_user FOR UPDATE",
        "SELECT user_id INTO TEMP copied_user FROM t_user",
        "EXPLAIN SELECT 1",
        "SELEC 1",
        "",
    ],
)
def test_gate_rejects_without_executing(sql: str) -> None:
    decision = check_read_only_sql(sql)

    assert decision.error is not None
    assert decision.sql == ""
    assert decision.error.retryable is True


def test_qualified_pg_catalog_count_is_allowed() -> None:
    decision = check_read_only_sql("SELECT pg_catalog.count(*)")

    assert decision.error is None


def test_date_trunc_uses_the_postgres_function_name() -> None:
    decision = check_read_only_sql("SELECT DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')")

    assert decision.error is None


def test_to_char_uses_the_postgres_function_name() -> None:
    decision = check_read_only_sql("SELECT to_char(CURRENT_DATE, 'YYYY-MM')")

    assert decision.error is None


def test_unknown_function_stays_rejected() -> None:
    decision = check_read_only_sql("SELECT secret_probe(1)")

    assert decision.error is not None
    assert decision.error.category == "disallowed_function"


@pytest.mark.parametrize(
    ("case_id", "cte_name"),
    [
        ("custom_medium_006", "phone_category"),
        ("custom_medium_007", "beauty_categories"),
        ("custom_medium_022", "perfume_tree"),
        ("custom_complex_024", "east_categories"),
        ("custom_complex_025", "central_categories"),
        ("custom_complex_026", "south_categories"),
        ("custom_complex_027", "southwest_categories"),
        ("custom_complex_028", "northwest_categories"),
        ("custom_complex_029", "vip_categories"),
        ("custom_complex_032", "coupon_categories"),
    ],
)
def test_self_referential_cte_is_rejected_before_execution(case_id: str, cte_name: str) -> None:
    sql = (
        f"WITH {cte_name} AS ("
        f"SELECT category_id FROM t_category WHERE category_name = '{case_id}' "
        "UNION ALL "
        f"SELECT c.category_id FROM t_category AS c JOIN {cte_name} AS parent "
        "ON c.parent_id = parent.category_id) "
        f"SELECT category_id FROM {cte_name}"
    )

    decision = check_read_only_sql(sql)

    assert decision.error is not None
    assert decision.error.category == "recursive_cte_missing"
    assert "WITH RECURSIVE" in decision.error.normalized_message
    assert "非递归等值过滤" in decision.error.normalized_message


def test_recursive_keyword_allows_a_self_referential_cte() -> None:
    decision = check_read_only_sql(
        "WITH RECURSIVE phone_category AS ("
        "SELECT category_id FROM t_category WHERE category_name = '手机' "
        "UNION ALL SELECT c.category_id FROM t_category AS c "
        "JOIN phone_category AS parent ON c.parent_id = parent.category_id) "
        "SELECT category_id FROM phone_category"
    )

    assert decision.error is None
