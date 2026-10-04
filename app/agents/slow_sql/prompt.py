"""慢 SQL 改写 Prompt。参考改写和完整 EXPLAIN JSON 不得进入这里。"""

from __future__ import annotations

from collections.abc import Sequence

from app.agents.slow_sql.plan import PlanNode
from app.agents.slow_sql.rules import Finding

PROMPT_VERSION = "slow-sql-v1"
SYSTEM_PROMPT = (
    "你是 PostgreSQL 只读 SQL 改写器。只输出一条语义等价的 SELECT，"
    "放在 sql 代码块中。不要解释，不要输出第二语句。"
)
_MAX_PLAN_NODES = 40


def render_rewrite_prompt(
    *,
    sql: str,
    findings: Sequence[Finding],
    nodes: Sequence[PlanNode],
) -> str:
    """组装改写请求。调用方只提供原 SQL、规则说明和压缩后的计划节点。"""

    finding_lines = [f"- {item.rule_id}: {item.message}" for item in findings]
    plan_lines = [
        f"- {node.node_type} {node.relation or '-'} cost={node.total_cost:.2f}"
        for node in nodes[:_MAX_PLAN_NODES]
    ]
    findings_text = "\n".join(finding_lines) if finding_lines else "- 无"
    plan_text = "\n".join(plan_lines) if plan_lines else "- 无"
    return (
        "请把下面的只读 SQL 改写成语义等价且代价更低的单条 SELECT。\n"
        f"原 SQL:\n{sql}\n"
        f"诊断:\n{findings_text}\n"
        f"计划节点:\n{plan_text}\n"
    )
