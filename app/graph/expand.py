"""1-Hop-per-Seed 与受限最短路径。

深度限制只约束第二阶段。1-Hop 指 Junction 距每个 Seed 各 1 跳，
两个实体之间的完整桥接固定是 2 条边。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import networkx as nx

from app.schemas.catalog import (
    GraphDiagnostic,
    GraphExpansionResult,
    GraphFailureCode,
    SchemaEdge,
    TableDocument,
)

DEFAULT_MAX_PATH_EDGES = 4
DEFAULT_MAX_TOTAL_TABLES = 12
DEFAULT_MAX_SCHEMA_TOKENS = 3500
DEFAULT_LOW_CONFIDENCE = 0.8


class TokenCounter(Protocol):
    """Schema 上下文的 token 计数器。"""

    def count(self, text: str) -> int:
        """返回文本的 token 数。"""


class EstimatedTokenCounter:
    """不加载模型词表的临时估算器。问数工作流会改用 DeepSeek tokenizer。"""

    def count(self, text: str) -> int:
        if text == "":
            return 0
        return max(1, len(text) // 4)


def render_schema_context(
    documents: Sequence[TableDocument],
    edges: Sequence[SchemaEdge] = (),
) -> str:
    """把已选表和这些表之间的外键渲染成稳定 Schema 文本。"""

    blocks: list[str] = []
    for document in sorted(documents, key=lambda item: item.table_name):
        lines = [f"table {document.table_name} {document.table_comment or ''}"]
        lines.extend(
            f"column {column.name} {column.data_type} {column.comment or ''}"
            for column in document.columns
        )
        blocks.append("\n".join(lines))
    join_lines = _join_lines(documents, edges)
    if join_lines:
        blocks.append("外键：\n" + "\n".join(join_lines))
    return "\n".join(blocks)


def _join_lines(documents: Sequence[TableDocument], edges: Sequence[SchemaEdge]) -> list[str]:
    selected = {document.table_name for document in documents}
    visible = [
        edge for edge in edges if edge.source_table in selected and edge.target_table in selected
    ]
    return [_join_line(edge) for edge in sorted(visible, key=lambda edge: edge.constraint_name)]


def _join_line(edge: SchemaEdge) -> str:
    if len(edge.source_columns) != len(edge.target_columns):
        raise ValueError(f"edge {edge.constraint_name} has mismatched columns")
    pairs = [
        f"{edge.source_table}.{source} = {edge.target_table}.{target}"
        for source, target in zip(edge.source_columns, edge.target_columns, strict=True)
    ]
    return "join " + " AND ".join(pairs)


@dataclass
class _Outcome:
    seeds: list[str]
    expanded: list[str]
    edges: list[SchemaEdge]
    connected: bool
    tokens: int
    code: str | None = None
    message: str | None = None


def expand_schema(
    documents: Sequence[TableDocument],
    edges: Sequence[SchemaEdge],
    seeds: Sequence[str],
    *,
    max_path_edges: int = DEFAULT_MAX_PATH_EDGES,
    max_total_tables: int = DEFAULT_MAX_TOTAL_TABLES,
    max_schema_tokens: int = DEFAULT_MAX_SCHEMA_TOKENS,
    token_counter: TokenCounter | None = None,
    low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE,
) -> GraphExpansionResult:
    """扩展种子表。预算不足时只丢弃低排名的额外种子，不把必需的两张表压成一张。"""

    if max_path_edges < 1 or max_total_tables < 1 or max_schema_tokens < 1:
        raise ValueError("graph budgets must be positive")
    if not 0 <= low_confidence_threshold <= 1:
        raise ValueError("low confidence threshold must be between 0 and 1")
    active = _unique(seeds)
    if not active:
        raise ValueError("at least one seed table is required")

    counter = token_counter or EstimatedTokenCounter()
    dropped: list[str] = []
    while True:
        outcome = _expand_once(
            documents,
            edges,
            active,
            max_path_edges=max_path_edges,
            max_total_tables=max_total_tables,
            max_schema_tokens=max_schema_tokens,
            token_counter=counter,
            low_confidence_threshold=low_confidence_threshold,
        )
        warnings = [f"已舍弃低排名种子 {name}" for name in dropped]
        if outcome.connected:
            return _result(outcome, truncated=bool(dropped), warnings=warnings)
        if outcome.code == "budget_exceeded" and len(active) > 2:
            dropped.append(active[-1])
            active = active[:-1]
            continue
        truncated = bool(dropped) or outcome.code == "budget_exceeded"
        return _result(outcome, truncated=truncated, warnings=warnings)


def _result(outcome: _Outcome, *, truncated: bool, warnings: list[str]) -> GraphExpansionResult:
    diagnostic = None
    if outcome.code is not None:
        diagnostic = GraphDiagnostic(
            code=_failure_code(outcome.code),
            message=outcome.message or outcome.code,
            seeds=list(outcome.seeds),
        )
    return GraphExpansionResult(
        seed_tables=list(outcome.seeds),
        expanded_tables=list(outcome.expanded),
        edges=list(outcome.edges),
        connected=outcome.connected,
        context_tokens=outcome.tokens,
        context_truncated=truncated,
        warnings=warnings,
        diagnostic=diagnostic,
    )


def _failure_code(code: str) -> GraphFailureCode:
    if code == "no_path":
        return "no_path"
    if code == "path_too_deep":
        return "path_too_deep"
    if code == "budget_exceeded":
        return "budget_exceeded"
    if code == "low_confidence_only":
        return "low_confidence_only"
    raise ValueError(f"unknown graph failure: {code}")


def _expand_once(
    documents: Sequence[TableDocument],
    edges: Sequence[SchemaEdge],
    seeds: Sequence[str],
    *,
    max_path_edges: int,
    max_total_tables: int,
    max_schema_tokens: int,
    token_counter: TokenCounter,
    low_confidence_threshold: float,
) -> _Outcome:
    by_name = {document.table_name: document for document in documents}
    missing = [seed for seed in seeds if seed not in by_name]
    if missing:
        raise ValueError(f"unknown seed tables: {', '.join(missing)}")
    for edge in edges:
        if edge.source_table not in by_name or edge.target_table not in by_name:
            raise ValueError(f"edge {edge.constraint_name} references an unknown table")

    junction = {name: document.is_junction for name, document in by_name.items()}
    usable, blocked = _partition_edges(edges, low_confidence_threshold)
    usable_graph = _undirected_graph(by_name, usable)
    full_graph = _undirected_graph(by_name, edges)

    def tokens_for(names: Sequence[str]) -> int:
        return token_counter.count(render_schema_context([by_name[name] for name in names], usable))

    def fits(names: Sequence[str]) -> bool:
        unique_names = list(dict.fromkeys(names))
        within_tables = len(unique_names) <= max_total_tables
        within_tokens = tokens_for(unique_names) <= max_schema_tokens
        return within_tables and within_tokens

    selected = list(seeds)
    if not fits(selected):
        return _fail(
            seeds,
            tokens_for(selected),
            "budget_exceeded",
            "种子表本身已超过表数量或 token 预算",
        )

    for left, right in _pairs(selected):
        common = _junction_neighbors(usable_graph, junction, left) & _junction_neighbors(
            usable_graph, junction, right
        )
        for name in sorted(common):
            if name in selected:
                continue
            candidate = [*selected, name]
            if fits(candidate):
                selected.append(name)

    while not _seeds_connected(usable_graph, selected, seeds):
        candidates = _candidate_paths(
            usable_graph,
            selected,
            seeds,
            max_path_edges,
        )
        fitting = [path for path in candidates if fits([*selected, *_new_nodes(path, selected)])]
        if fitting:
            best = min(fitting, key=lambda path: _rank(path, selected, junction, usable))
            for name in _new_nodes(best, selected):
                selected.append(name)
            continue
        return _diagnose(
            usable_graph,
            full_graph,
            selected,
            seeds,
            max_path_edges,
            max_total_tables,
            tokens_for,
            blocked,
        )

    return _Outcome(
        seeds=list(seeds),
        expanded=[name for name in selected if name not in set(seeds)],
        edges=_induced_edges(usable, selected),
        connected=True,
        tokens=tokens_for(selected),
    )


def _diagnose(
    usable_graph: nx.Graph,
    full_graph: nx.Graph,
    selected: Sequence[str],
    seeds: Sequence[str],
    max_path_edges: int,
    max_total_tables: int,
    tokens_for: Callable[[Sequence[str]], int],
    blocked: Sequence[SchemaEdge],
) -> _Outcome:
    codes: list[str] = []
    for left, right in _disconnected_pairs(usable_graph, selected, seeds):
        usable_distance = _distance(usable_graph, left, right)
        if usable_distance is None:
            if _distance(full_graph, left, right) is None:
                codes.append("no_path")
            else:
                codes.append("low_confidence_only")
        elif usable_distance > max_path_edges:
            codes.append("path_too_deep")
        else:
            codes.append("budget_exceeded")
    code = _dominant_failure(codes)
    messages = {
        "no_path": "种子表之间不存在可用路径",
        "path_too_deep": "所有可用路径都超过最大深度",
        "budget_exceeded": (
            f"必需路径超过预算：最多 {max_total_tables} 张表，且不能拆开路径中的中间节点"
        ),
        "low_confidence_only": "连通路径只依赖低置信度边，不能进入自动扩展",
    }
    if blocked and code == "low_confidence_only":
        messages[code] = "连通路径只依赖低置信度隐式边，不能进入自动扩展"
    return _fail(seeds, tokens_for(list(seeds)), code, messages[code])


def _dominant_failure(codes: Sequence[str]) -> str:
    for code in ("no_path", "low_confidence_only", "path_too_deep", "budget_exceeded"):
        if code in codes:
            return code
    return "no_path"


def _fail(seeds: Sequence[str], tokens: int, code: str, message: str) -> _Outcome:
    return _Outcome(
        seeds=list(seeds),
        expanded=[],
        edges=[],
        connected=False,
        tokens=tokens,
        code=code,
        message=message,
    )


def _partition_edges(
    edges: Sequence[SchemaEdge],
    threshold: float,
) -> tuple[list[SchemaEdge], list[SchemaEdge]]:
    usable: list[SchemaEdge] = []
    blocked: list[SchemaEdge] = []
    for edge in edges:
        if edge.confidence < threshold:
            blocked.append(edge)
        else:
            usable.append(edge)
    return usable, blocked


def _undirected_graph(
    documents: Mapping[str, TableDocument],
    edges: Sequence[SchemaEdge],
) -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(documents)
    for edge in edges:
        graph.add_edge(edge.source_table, edge.target_table)
    return graph


def _junction_neighbors(
    graph: nx.Graph,
    junction: Mapping[str, bool],
    table: str,
) -> set[str]:
    return {neighbor for neighbor in graph.neighbors(table) if junction.get(neighbor, False)}


def _pairs(names: Sequence[str]) -> list[tuple[str, str]]:
    return [
        (names[left], names[right])
        for left in range(len(names))
        for right in range(left + 1, len(names))
    ]


def _seeds_connected(graph: nx.Graph, selected: Sequence[str], seeds: Sequence[str]) -> bool:
    if len(seeds) <= 1:
        return True
    induced = graph.subgraph(selected)
    components = {
        node: index
        for index, component in enumerate(nx.connected_components(induced))
        for node in component
    }
    return len({components[seed] for seed in seeds}) == 1


def _disconnected_pairs(
    graph: nx.Graph,
    selected: Sequence[str],
    seeds: Sequence[str],
) -> list[tuple[str, str]]:
    induced = graph.subgraph(selected)
    components = {
        node: index
        for index, component in enumerate(nx.connected_components(induced))
        for node in component
    }
    return [
        (left, right)
        for left, right in _pairs(list(seeds))
        if components[left] != components[right]
    ]


def _candidate_paths(
    graph: nx.Graph,
    selected: Sequence[str],
    seeds: Sequence[str],
    max_path_edges: int,
) -> list[tuple[str, ...]]:
    found: list[tuple[str, ...]] = []
    selected_set = set(selected)
    for left, right in _disconnected_pairs(graph, selected, seeds):
        distance = _distance(graph, left, right)
        if distance is None or distance > max_path_edges:
            continue
        found.extend(
            path
            for path in _simple_paths(graph, left, right, max_path_edges)
            if _new_nodes(path, selected_set)
        )
    return found


def _simple_paths(
    graph: nx.Graph,
    source: str,
    target: str,
    max_edges: int,
) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []
    stack: list[tuple[str, tuple[str, ...]]] = [(source, (source,))]
    while stack:
        node, path = stack.pop()
        if len(path) - 1 >= max_edges:
            continue
        neighbors = sorted(graph.neighbors(node), reverse=True)
        for neighbor in neighbors:
            if neighbor in path:
                continue
            extended = (*path, neighbor)
            if neighbor == target:
                paths.append(extended)
            else:
                stack.append((neighbor, extended))
    return paths


def _distance(graph: nx.Graph, source: str, target: str) -> int | None:
    if source not in graph or target not in graph:
        return None
    try:
        length = nx.shortest_path_length(graph, source, target)
    except nx.NetworkXNoPath:
        return None
    return int(length)


def _new_nodes(path: Sequence[str], selected: Sequence[str] | set[str]) -> list[str]:
    selected_set = selected if isinstance(selected, set) else set(selected)
    return [node for node in path if node not in selected_set]


def _rank(
    path: tuple[str, ...],
    selected: Sequence[str],
    junction: Mapping[str, bool],
    edges: Sequence[SchemaEdge],
) -> tuple[int, int, float, tuple[str, ...]]:
    weight = 0.0
    for index in range(len(path) - 1):
        weight += _step_weight(edges, path[index], path[index + 1])
    junction_count = sum(1 for node in path if junction.get(node, False))
    return (len(_new_nodes(path, selected)), -junction_count, weight, path)


def _step_weight(edges: Sequence[SchemaEdge], left: str, right: str) -> float:
    weights = [
        edge.weight for edge in edges if {edge.source_table, edge.target_table} == {left, right}
    ]
    if not weights:
        raise ValueError(f"missing edge between {left} and {right}")
    return min(weights)


def _induced_edges(edges: Sequence[SchemaEdge], selected: Sequence[str]) -> list[SchemaEdge]:
    selected_set = set(selected)
    induced = [
        edge
        for edge in edges
        if edge.source_table in selected_set and edge.target_table in selected_set
    ]
    return sorted(induced, key=lambda edge: edge.constraint_name)


def _unique(seeds: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(seeds))
