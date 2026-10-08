"""慢 SQL 改写 Prompt。参考改写和完整 EXPLAIN JSON 不得进入这里。"""

from __future__ import annotations

from collections.abc import Sequence

from app.agents.slow_sql.plan import PlanNode
from app.agents.slow_sql.rules import Finding

PROMPT_VERSION = "slow-sql-v2"
SYSTEM_PROMPT = (
    "你是 PostgreSQL 只读 SQL 改写器。只输出一条语义等价的 SELECT，"
    "放在 sql 代码块中。不要解释，不要输出第二语句。"
    "禁止改变结果行集合、列语义或排序含义。"
)
_RULE_HINTS: dict[str, str] = {
    "select-star": "把 SELECT * 展开为与表一致的全部列名，不要漏列或改列顺序含义。",
    "missing-filter-on-large-table": "为大表补上选择性过滤（优先索引列 user_id/order_id/detail_id），保持结果集不变。",
    "function-on-index-column": "去掉索引列上的函数/算术，改为对索引列的直接比较。",
    "implicit-cast-on-index-column": "去掉索引列上的 ::text/::varchar 转换，改为同类型字面量比较。",
    "correlated-subquery": "可改为等价 JOIN 或聚合子查询，但结果必须与原文一致。",
    "aggregate-after-join": "先按 order_id 在 t_order_detail 预聚合，再 JOIN t_order，避免重复行放大 SUM。",
    "unbounded-sort": "保留 ORDER BY；通过更 selective 的 WHERE 或子查询降代价，不要随意加 LIMIT 改变结果。",
    "repeated-distinct": "合并嵌套 DISTINCT 为单层 DISTINCT，投影列不变。",
    "redundant-join": "删除未贡献投影/过滤/连接的冗余 JOIN，保持结果不变。",
    "seq-scan-on-large-table": "改为走索引列等值/范围过滤；NOT IN 可改为 JOIN + 等值过滤。",
}
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
    hints = [
        _RULE_HINTS[item.rule_id]
        for item in findings
        if item.rule_id in _RULE_HINTS
    ]
    hint_text = "\n".join(f"- {line}" for line in hints) if hints else "- 无"
    return (
        "请把下面的只读 SQL 改写成语义等价且代价更低的单条 SELECT。\n"
        f"原 SQL:\n{sql}\n"
        f"诊断:\n{findings_text}\n"
        f"改写提示:\n{hint_text}\n"
        f"计划节点:\n{plan_text}\n"
    )


def render_rewrite_repair_prompt(
    *,
    sql: str,
    previous_sql: str,
    findings: Sequence[Finding],
    nodes: Sequence[PlanNode],
) -> str:
    """上一轮改写未通过语义 EX 时的修复 Prompt。"""

    base = render_rewrite_prompt(sql=sql, findings=findings, nodes=nodes)
    return (
        f"{base}\n"
        "上一轮改写未通过语义 EX（结果集不一致）。\n"
        f"失败 SQL:\n{previous_sql}\n"
        "请重新改写，确保行多重集与列语义完全一致。\n"
    )
