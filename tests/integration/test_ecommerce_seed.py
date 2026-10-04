"""相同种子的数据库摘要，以及 10 条 Gold SQL 的稳定结果。"""

from __future__ import annotations

import pytest
from app.db.engine import get_admin_engine, get_sandbox_engine
from app.db.seed import seed_ecommerce
from app.db.seed_data import build_dataset
from app.evaluation.smoke import canonical_rows, execute_gold_sql, load_smoke_cases
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def test_same_seed_produces_the_same_database_digest(database_settings) -> None:
    del database_settings
    dataset = build_dataset()

    first = await seed_ecommerce(dataset)
    second = await seed_ecommerce(dataset)

    assert first == dataset.digest
    assert second == dataset.digest
    async with get_admin_engine().connect() as conn:
        reltuples = await conn.scalar(
            text("SELECT reltuples FROM pg_class WHERE relname = 't_order'")
        )
    assert reltuples is not None
    assert float(reltuples) > 1000


async def test_smoke_gold_sql_returns_nonempty_stable_rows(database_settings) -> None:
    del database_settings
    await seed_ecommerce()
    cases = load_smoke_cases()
    assert len(cases) == 10

    async with get_sandbox_engine().connect() as conn:
        for case in cases:
            first = await execute_gold_sql(case, conn)
            second = await execute_gold_sql(case, conn)
            assert first.columns == case.expected_columns
            assert first.rows
            assert canonical_rows(
                first.rows, order_sensitive=case.order_sensitive
            ) == canonical_rows(second.rows, order_sensitive=case.order_sensitive)
            if case.id == "smoke_complex_001":
                assert len(first.rows) >= 2
