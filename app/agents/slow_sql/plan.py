"""解析 PostgreSQL JSON 执行计划，只保留诊断需要的字段。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class PlanNode:
    """计划树中的一个节点。不保留过滤条件原文。"""

    node_type: str
    relation: str | None
    total_cost: float


@dataclass(frozen=True)
class PlanSummary:
    """一次 EXPLAIN 的摘要。未执行 ANALYZE 时运行时字段保持空。"""

    total_cost: float
    execution_time_ms: float | None
    shared_hit_blocks: int | None
    shared_read_blocks: int | None
    nodes: tuple[PlanNode, ...]


def parse_explain(payload: object, *, analyzed: bool) -> PlanSummary:
    """读取 EXPLAIN FORMAT JSON。Buffer 按节点求和，不把子节点再计入父节点。"""

    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise ValueError("explain json must contain one plan")
    root = payload[0]
    plan = root.get("Plan")
    if not isinstance(plan, dict) or not isinstance(plan.get("Total Cost"), int | float):
        raise ValueError("explain plan is missing total cost")
    nodes: list[PlanNode] = []
    hit, read = _walk(plan, nodes)
    if not analyzed:
        return PlanSummary(
            total_cost=float(plan["Total Cost"]),
            execution_time_ms=None,
            shared_hit_blocks=None,
            shared_read_blocks=None,
            nodes=tuple(nodes),
        )
    elapsed = root.get("Execution Time")
    return PlanSummary(
        total_cost=float(plan["Total Cost"]),
        execution_time_ms=float(elapsed) if isinstance(elapsed, int | float) else None,
        shared_hit_blocks=hit,
        shared_read_blocks=read,
        nodes=tuple(nodes),
    )


def _walk(plan: Mapping[str, object], nodes: list[PlanNode]) -> tuple[int, int]:
    node_type = plan.get("Node Type")
    total_cost = plan.get("Total Cost")
    if not isinstance(node_type, str) or not isinstance(total_cost, int | float):
        raise ValueError("explain node is missing type or cost")
    relation = plan.get("Relation Name")
    nodes.append(
        PlanNode(
            node_type=node_type,
            relation=relation if isinstance(relation, str) else None,
            total_cost=float(total_cost),
        )
    )
    hit = _block_count(plan.get("Shared Hit Blocks"))
    read = _block_count(plan.get("Shared Read Blocks"))
    children = plan.get("Plans")
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, dict):
                raise ValueError("explain child node must be an object")
            child_hit, child_read = _walk(child, nodes)
            hit += child_hit
            read += child_read
    return hit, read


def _block_count(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("explain block count must be numeric")
    return int(value)
