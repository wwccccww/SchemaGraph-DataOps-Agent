"""JSON 计划只保留成本、时间和按节点相加的 Buffer。"""

from __future__ import annotations

from app.agents.slow_sql.plan import parse_explain

_PLAN = [
    {
        "Plan": {
            "Node Type": "Nested Loop",
            "Total Cost": 10.5,
            "Shared Hit Blocks": 1,
            "Shared Read Blocks": 2,
            "Plans": [
                {
                    "Node Type": "Seq Scan",
                    "Relation Name": "t_order",
                    "Total Cost": 8,
                    "Shared Hit Blocks": 4,
                    "Shared Read Blocks": 5,
                    "Actual Total Time": 99,
                }
            ],
        },
        "Execution Time": 12.5,
    }
]


def test_analyzed_plan_sums_blocks_and_uses_root_execution_time() -> None:
    summary = parse_explain(_PLAN, analyzed=True)
    assert summary.total_cost == 10.5
    assert summary.execution_time_ms == 12.5
    assert summary.shared_hit_blocks == 5
    assert summary.shared_read_blocks == 7
    assert summary.nodes[1].relation == "t_order"


def test_plan_without_analyze_keeps_runtime_fields_empty() -> None:
    summary = parse_explain(_PLAN, analyzed=False)
    assert summary.total_cost == 10.5
    assert summary.execution_time_ms is None
    assert summary.shared_hit_blocks is None
    assert summary.shared_read_blocks is None
