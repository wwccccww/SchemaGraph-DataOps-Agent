"""四类慢 SQL 在隔离快照上完成改写、语义 EX 和指标比较。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest
from app.agents.slow_sql.snapshot import index_exists
from app.db.seed import seed_ecommerce
from app.evaluation.slow_sql import load_slow_sql_cases, score_slow_sql_cases

pytestmark = pytest.mark.integration

_REWRITES = {
    "slow_seq_scan": (
        "SELECT d.detail_id, d.quantity\n"
        "FROM t_order_detail d\n"
        "JOIN t_order o ON o.order_id = d.order_id\n"
        "WHERE o.user_id = 1"
    ),
    "slow_index_expr": "SELECT order_id FROM t_order WHERE user_id = 1",
    "slow_implicit_cast": "SELECT order_id FROM t_order WHERE user_id = 1",
    "slow_repeat_agg": (
        "SELECT o.order_status, SUM(o.total_amount * d.line_count) AS amount\n"
        "FROM t_order o\n"
        "JOIN (\n"
        "  SELECT order_id, COUNT(*)::bigint AS line_count\n"
        "  FROM t_order_detail\n"
        "  GROUP BY order_id\n"
        ") d ON d.order_id = o.order_id\n"
        "GROUP BY o.order_status"
    ),
}
_EXPECTED = {
    "slow_seq_scan": "seq-scan-on-large-table",
    "slow_index_expr": "function-on-index-column",
    "slow_implicit_cast": "implicit-cast-on-index-column",
    "slow_repeat_agg": "aggregate-after-join",
}


class _ScriptedRewriter:
    """参考改写只存在于测试模型，不进入诊断 Prompt。"""

    def __init__(self, rewrites: dict[str, str]) -> None:
        self.rewrites = rewrites
        self.prompts: list[str] = []
        self.temperatures: list[float] = []

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float,
    ) -> str:
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        self.temperatures.append(temperature)
        for original, rewrite in self.rewrites.items():
            if original in prompt:
                return f"```sql\n{rewrite}\n```"
        raise AssertionError("prompt did not contain a known original sql")


async def test_four_cases_stay_isolated_and_improve_planner_cost(database_settings) -> None:
    await seed_ecommerce()
    cases = load_slow_sql_cases()
    model = _ScriptedRewriter({case.sql.strip(): _REWRITES[case.id] for case in cases})
    scores = await score_slow_sql_cases(cases, model, database_settings)
    assert [score.case_id for score in scores] == list(_EXPECTED)
    for score in scores:
        assert _EXPECTED[score.case_id] in score.findings, score.detail
        assert score.equivalent, score.detail
        assert score.optimize_success, score.detail
        assert score.isolated, score.detail
        assert score.planner_cost_drop is not None
        assert score.planner_cost_drop >= 0.2
    assert len(model.temperatures) <= 4
    assert all(temperature == 0.0 for temperature in model.temperatures)
    for prompt in model.prompts:
        for rewrite in _REWRITES.values():
            assert rewrite not in prompt
    assert await index_exists(database_settings, "idx_order_status")
