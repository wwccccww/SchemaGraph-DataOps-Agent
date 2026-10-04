"""132 条 Gold SQL 可执行、非空、稳定，并且结果可区分。"""

from __future__ import annotations

import pytest
from app.db.engine import get_sandbox_engine
from app.db.seed import seed_ecommerce
from app.evaluation.custom_cases import load_custom_cases
from app.evaluation.smoke import canonical_rows
from app.evaluation.text_to_sql import EVALUATION_MAX_ROWS
from app.sandbox.execute import ExecutionError, execute_readonly
from app.sandbox.gate import check_read_only_sql

pytestmark = pytest.mark.integration

# 这两条冒烟副本的队列在种子上完全重合，Gold SQL 必须保持原文，不能为了结果去重而改写。
_SHARED_COHORT = frozenset({"custom_complex_001", "custom_complex_004"})


async def test_custom_gold_sql_is_executable_and_discriminative(database_settings) -> None:
    del database_settings
    await seed_ecommerce()
    cases = load_custom_cases()
    assert len(cases) == 132
    seen: dict[tuple[tuple[object, ...], ...], str] = {}

    async with get_sandbox_engine().connect() as conn:
        for case in cases:
            decision = check_read_only_sql(case.gold_sql)
            assert decision.error is None, case.id
            first = await execute_readonly(
                decision.sql,
                max_rows=EVALUATION_MAX_ROWS,
                connection=conn,
            )
            second = await execute_readonly(
                decision.sql,
                max_rows=EVALUATION_MAX_ROWS,
                connection=conn,
            )
            assert not isinstance(first, ExecutionError), (case.id, first)
            assert not isinstance(second, ExecutionError), (case.id, second)
            assert first.rows, case.id
            assert [name for name, _data_type in first.columns] == case.expected_columns
            left = canonical_rows(first.rows, order_sensitive=case.order_sensitive)
            right = canonical_rows(second.rows, order_sensitive=case.order_sensitive)
            assert left == right, case.id
            previous = seen.get(left)
            if previous is not None:
                assert {previous, case.id} == _SHARED_COHORT
            else:
                seen[left] = case.id
