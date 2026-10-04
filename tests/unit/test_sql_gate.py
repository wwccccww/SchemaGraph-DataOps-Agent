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
