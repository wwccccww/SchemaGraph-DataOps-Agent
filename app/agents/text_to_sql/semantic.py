"""执行成功后的静态语义复核。

只看问题、当前 SQL、已选 Schema 和执行规模。不读取 Gold SQL、Gold 结果、
required_tables 或难度。复核通过就结束；失败时由自愈组把发现交给修复 Prompt。
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.evaluation.sql_shape import describe_sql
from app.retrieval.dynamic import entity_core, lexical_seed_tiers
from app.schemas.catalog import SchemaEdge, TableDocument

# 自建快照上正常查询的计划行数停留在几百以内。更高的估计更像笛卡尔积或丢掉了连接条件。
HUGE_PLAN_ROWS = 100_000
_ATTRIBUTE_WORDS = ("折扣率", "省份", "名称", "编号", "金额", "数量")
_GRAIN_WORDS = ("每个", "各")
_FANOUT_AGGREGATES = frozenset({"sum", "avg", "count"})


@dataclass(frozen=True)
class SemanticFinding:
    """一条可放进修复 Prompt 的复核发现。"""

    category: str
    message: str


def check_semantics(
    *,
    question: str,
    sql: str,
    documents: Sequence[TableDocument],
    edges: Sequence[SchemaEdge],
    selected_tables: Sequence[str],
    row_count: int | None = None,
    truncated: bool = False,
    max_rows: int | None = None,
    plan_rows: float | None = None,
) -> tuple[SemanticFinding, ...]:
    """返回按类别排序的发现。没有发现表示这条 SQL 可以通过复核。"""

    findings: list[SemanticFinding] = []
    shown = _shown_documents(documents, selected_tables)
    shape = describe_sql(sql)
    if shape.parse_error is None and question.strip():
        try:
            expression = sqlglot.parse_one(sql, read="postgres")
        except SqlglotError:
            expression = None
        if isinstance(expression, exp.Expression):
            catalog = {document.table_name.lower() for document in shown}
            _check_entities(question, shape.referenced_tables, shown, findings)
            _check_projection(question, expression, shown, findings)
            _check_joins(expression, edges, catalog, findings)
            _check_grain(question, expression, edges, catalog, findings)
    _check_results(
        findings,
        row_count=row_count,
        truncated=truncated,
        max_rows=max_rows,
        plan_rows=plan_rows,
    )
    unique = list(dict.fromkeys(findings))
    return tuple(sorted(unique, key=lambda item: (item.category, item.message)))


def _shown_documents(
    documents: Sequence[TableDocument],
    selected_tables: Sequence[str],
) -> tuple[TableDocument, ...]:
    selected = {name.lower() for name in selected_tables}
    return tuple(document for document in documents if document.table_name.lower() in selected)


def _named_entities(question: str, documents: Sequence[TableDocument]) -> tuple[str, ...]:
    entities = [document for document in documents if not document.is_junction]
    if not entities or question.strip() == "":
        return ()
    tiers = lexical_seed_tiers(question, entities)
    cores = {document.table_name: core for document in entities if (core := entity_core(document))}
    names: list[str] = []
    for name, tier in tiers.items():
        core = cores.get(name)
        if tier >= 2 and core is not None and not _shadowed(core, question, cores):
            names.append(name)
    return tuple(sorted(names))


def _shadowed(core: str, question: str, cores: Mapping[str, str]) -> bool:
    """短实体词只作为更长实体词的省略说法出现时，不单独要求那张表。"""

    others = [
        other for other in cores.values() if len(other) > len(core) and other.startswith(core)
    ]
    if not others or core not in question:
        return False
    start = 0
    found = False
    while True:
        index = question.find(core, start)
        if index < 0:
            break
        found = True
        after = question[index + len(core) :]
        if not any(_core_continues(other, core, after) for other in others):
            return False
        start = index + len(core)
    return found


def _core_continues(other: str, core: str, after: str) -> bool:
    rest = other[len(core) :]
    if after.startswith(rest):
        return True
    return any(after.startswith(rest[-size:]) for size in range(2, len(rest)))


def _check_entities(
    question: str,
    referenced: Sequence[str],
    documents: Sequence[TableDocument],
    findings: list[SemanticFinding],
) -> None:
    used = {name.lower() for name in referenced}
    for name in _named_entities(question, documents):
        if name.lower() not in used:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    f"问句点名的表 {name} 没有出现在 SQL 中",
                )
            )


def _check_projection(
    question: str,
    expression: exp.Expression,
    documents: Sequence[TableDocument],
    findings: list[SemanticFinding],
) -> None:
    projected = _projected_columns(expression)
    for part in _requested_parts(question):
        if _attribute_requested(part):
            for word in _ATTRIBUTE_WORDS:
                if word in part and not _projects_attribute(question, word, projected, documents):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            f"问句要求返回{word}，投影里没有对应的列",
                        )
                    )
            continue
        for name in _named_entities(part, documents):
            if not _projects_table(name, projected, documents):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        f"问句要求返回{part}，投影里没有 {name} 的列",
                    )
                )


def _requested_parts(question: str) -> tuple[str, ...]:
    if "查询" not in question or question.startswith("统计"):
        return ()
    tail = question.rsplit("查询", 1)[-1]
    if "的" in tail:
        tail = tail.rsplit("的", 1)[-1]
    return tuple(part.strip() for part in re.split(r"[、，,和与及]", tail) if part.strip())


def _attribute_requested(part: str) -> bool:
    return any(word in part for word in _ATTRIBUTE_WORDS)


def _projects_attribute(
    question: str,
    word: str,
    projected: set[tuple[str | None, str]],
    documents: Sequence[TableDocument],
) -> bool:
    if ("*", "*") in projected:
        return True
    named = {name.lower() for name in _named_entities(question, documents)}
    candidates = [
        (document.table_name.lower(), column.name.lower())
        for document in documents
        if not document.is_junction and (not named or document.table_name.lower() in named)
        for column in document.columns
        if _column_matches_attribute(column.name, column.comment, word)
    ]
    if not candidates:
        return True
    return any(_column_projected(table, column, projected) for table, column in candidates)


def _column_matches_attribute(name: str, comment: str | None, word: str) -> bool:
    if word == "编号" and name.lower().endswith("_id"):
        return True
    if word == "名称" and name.lower().endswith("_name"):
        return True
    return _comment_has(comment, word)


def _comment_has(comment: str | None, word: str) -> bool:
    if comment is None:
        return False
    head = comment.split("，", 1)[0].split(",", 1)[0]
    if head.startswith(("关联", "所属", "归属", "父级", "是否")):
        return False
    return word in head


def _projects_table(
    table: str,
    projected: set[tuple[str | None, str]],
    documents: Sequence[TableDocument],
) -> bool:
    if ("*", "*") in projected:
        return True
    names = {
        column.name.lower()
        for document in documents
        if document.table_name.lower() == table.lower()
        for column in document.columns
    }
    for source, column in projected:
        if source == table.lower() or (source is None and column in names):
            return True
    return False


def _column_projected(
    table: str,
    column: str,
    projected: set[tuple[str | None, str]],
) -> bool:
    return (table, column) in projected or (None, column) in projected


def _projected_columns(expression: exp.Expression) -> set[tuple[str | None, str]]:
    select = expression if isinstance(expression, exp.Select) else expression.find(exp.Select)
    if not isinstance(select, exp.Select):
        return set()
    aliases = _scope_aliases(select)
    projected: set[tuple[str | None, str]] = set()
    for projection in select.expressions:
        if isinstance(projection, exp.Star) or any(
            isinstance(node, exp.Star) for node in projection.walk()
        ):
            projected.add(("*", "*"))
            continue
        for column in projection.find_all(exp.Column):
            if _nested_select(column, select):
                continue
            projected.add(_projected_ref(column, aliases))
    return projected


def _projected_ref(column: exp.Column, aliases: Mapping[str, str]) -> tuple[str | None, str]:
    name = column.name.lower()
    if not column.table:
        return None, name
    return aliases.get(column.table.lower()), name


@dataclass(frozen=True)
class _Origin:
    """一列能追溯到的物理列。无法证明时 proven 为假。"""

    columns: frozenset[tuple[str, str]]
    proven: bool
    via_cte: bool


_Lineage = dict[str, dict[str, frozenset[tuple[str, str]] | None]]


def _check_joins(
    expression: exp.Expression,
    edges: Sequence[SchemaEdge],
    catalog: set[str],
    findings: list[SemanticFinding],
) -> None:
    accepted = _fk_pairs(edges)
    lineage: _Lineage = {}
    _fill_lineage(expression, catalog, lineage)
    for select in expression.find_all(exp.Select):
        aliases = _scope_aliases(select)
        joins = select.args.get("joins")
        if not isinstance(joins, list):
            continue
        for join in joins:
            if isinstance(join, exp.Join):
                _check_join(join, aliases, accepted, catalog, lineage, findings)


def _check_join(
    join: exp.Join,
    aliases: Mapping[str, str],
    accepted: set[frozenset[tuple[str, str]]],
    catalog: set[str],
    lineage: _Lineage,
    findings: list[SemanticFinding],
) -> None:
    target = join.this
    if not isinstance(target, exp.Table):
        return
    target_name = target.name.lower()
    if target_name not in catalog and target_name not in lineage:
        return
    condition = join.args.get("on")
    if not isinstance(condition, exp.Expression) or _is_true(condition):
        findings.append(SemanticFinding("cartesian_product", f"{target.name} 的 JOIN 没有连接条件"))
        return
    equalities = [node for node in condition.find_all(exp.EQ) if isinstance(node, exp.EQ)]
    matched = False
    recorded = False
    saw_unverified = False
    for equality in equalities:
        left = _origin_of(equality.left, aliases, catalog, lineage)
        right = _origin_of(equality.right, aliases, catalog, lineage)
        if left is None or right is None:
            continue
        if not left.proven or not right.proven:
            saw_unverified = True
            continue
        pairs = [
            frozenset({one, other})
            for one in left.columns
            for other in right.columns
            if one != other
        ]
        if any(pair in accepted for pair in pairs):
            matched = True
            continue
        if not pairs:
            continue
        recorded = True
        if left.via_cte or right.via_cte:
            findings.append(
                SemanticFinding(
                    "join_not_on_graph",
                    f"{target.name} 的 JOIN 沿 CTE 血缘不是外键",
                )
            )
            continue
        pair = pairs[0]
        first, second = sorted(pair)
        findings.append(
            SemanticFinding(
                "join_not_on_graph",
                f"JOIN 条件 {first[0]}.{first[1]} = {second[0]}.{second[1]} 不是外键",
            )
        )
    if matched or recorded:
        return
    if saw_unverified:
        findings.append(
            SemanticFinding(
                "join_unverified",
                f"{target.name} 的 JOIN 经过 CTE，血缘不能证明外键",
            )
        )
        return
    findings.append(
        SemanticFinding(
            "join_not_on_graph",
            f"{target.name} 的 JOIN 条件没有落在外键上",
        )
    )


def _fill_lineage(node: exp.Expression, catalog: set[str], lineage: _Lineage) -> None:
    clause = node.args.get("with_")
    if not isinstance(clause, exp.With):
        return
    for cte in clause.expressions:
        if isinstance(cte, exp.CTE) and isinstance(cte.this, exp.Expression):
            _fill_lineage(cte.this, catalog, lineage)
            _record_cte(cte, catalog, lineage)


def _record_cte(cte: exp.CTE, catalog: set[str], lineage: _Lineage) -> None:
    name = cte.alias
    body = cte.this
    if not isinstance(name, str) or name == "" or not isinstance(body, exp.Expression):
        return
    found: dict[str, set[tuple[str, str]]] = {}
    unknown: set[str] = set()
    for select in _union_selects(body):
        aliases = _scope_aliases(select)
        for projection in select.expressions:
            key = _output_name(projection)
            if key is None:
                continue
            origins = _projection_origins(projection, select, aliases, catalog, lineage)
            if origins is None:
                if key not in found:
                    unknown.add(key)
                continue
            unknown.discard(key)
            found.setdefault(key, set()).update(origins)
    lineage[name.lower()] = {
        **{key: frozenset(value) for key, value in found.items()},
        **{key: None for key in unknown},
    }


def _projection_origins(
    projection: exp.Expression,
    select: exp.Select,
    aliases: Mapping[str, str],
    catalog: set[str],
    lineage: _Lineage,
) -> frozenset[tuple[str, str]] | None:
    columns = [
        column
        for column in projection.find_all(exp.Column)
        if isinstance(column, exp.Column) and not _nested_select(column, select)
    ]
    if not columns:
        return None
    found: set[tuple[str, str]] = set()
    for column in columns:
        origin = _origin_of(column, aliases, catalog, lineage)
        if origin is None or not origin.proven or not origin.columns:
            return None
        found.update(origin.columns)
    return frozenset(found)


def _output_name(projection: exp.Expression) -> str | None:
    name = projection.alias_or_name
    if isinstance(name, str) and name != "":
        return name.lower()
    return None


def _union_selects(node: exp.Expression) -> list[exp.Select]:
    if isinstance(node, exp.Select):
        return [node]
    if isinstance(node, exp.Union):
        found: list[exp.Select] = []
        left = node.this
        right = node.expression
        if isinstance(left, exp.Expression):
            found.extend(_union_selects(left))
        if isinstance(right, exp.Expression):
            found.extend(_union_selects(right))
        return found
    select = node.find(exp.Select)
    if isinstance(select, exp.Select):
        return [select]
    return []


def _origin_of(
    node: exp.Expr,
    aliases: Mapping[str, str],
    catalog: set[str],
    lineage: _Lineage,
) -> _Origin | None:
    if not isinstance(node, exp.Column) or not node.table:
        return None
    table = aliases.get(node.table.lower())
    if table is None:
        return None
    if table in catalog:
        return _Origin(frozenset({(table, node.name.lower())}), True, False)
    info = lineage.get(table)
    if info is None:
        return None
    stored = info.get(node.name.lower()) if node.name.lower() in info else None
    if node.name.lower() not in info or stored is None:
        return _Origin(frozenset(), False, True)
    return _Origin(stored, True, True)


def _column_ref(
    node: exp.Expr,
    aliases: Mapping[str, str],
    catalog: set[str],
) -> tuple[str, str] | None:
    origin = _origin_of(node, aliases, catalog, {})
    if origin is None or not origin.proven or len(origin.columns) != 1 or origin.via_cte:
        return None
    return next(iter(origin.columns))


def _fk_pairs(edges: Sequence[SchemaEdge]) -> set[frozenset[tuple[str, str]]]:
    pairs: set[frozenset[tuple[str, str]]] = set()
    for edge in edges:
        if len(edge.source_columns) != len(edge.target_columns):
            continue
        for source, target in zip(edge.source_columns, edge.target_columns, strict=True):
            pairs.add(
                frozenset(
                    {
                        (edge.source_table.lower(), source.lower()),
                        (edge.target_table.lower(), target.lower()),
                    }
                )
            )
    return pairs


def _is_true(node: exp.Expression) -> bool:
    current = node
    while isinstance(current, exp.Paren):
        current = current.this
    return isinstance(current, exp.Boolean) and current.this is True


def _check_grain(
    question: str,
    expression: exp.Expression,
    edges: Sequence[SchemaEdge],
    catalog: set[str],
    findings: list[SemanticFinding],
) -> None:
    links = _many_to_one(edges)
    for select in expression.find_all(exp.Select):
        aliases = _scope_aliases(select)
        tables = set(aliases.values())
        for aggregate in _owned_aggs(select):
            if isinstance(aggregate.this, exp.Distinct | exp.Star):
                continue
            if aggregate.sql_name().lower() not in _FANOUT_AGGREGATES:
                continue
            one_sides = {
                table
                for column in aggregate.find_all(exp.Column)
                if (ref := _column_ref(column, aliases, catalog)) is not None
                for table, _name in (ref,)
            }
            for many, one in links:
                if many in tables and one in tables and one in one_sides:
                    findings.append(
                        SemanticFinding(
                            "aggregation_grain",
                            f"聚合了 {one} 的列，同时连接了会放大行数的 {many}",
                        )
                    )
                    break
    if any(word in question for word in _GRAIN_WORDS):
        outer = expression if isinstance(expression, exp.Select) else expression.find(exp.Select)
        if (
            isinstance(outer, exp.Select)
            and _owned_aggs(outer)
            and not isinstance(outer.args.get("group"), exp.Group)
        ):
            findings.append(
                SemanticFinding(
                    "aggregation_grain",
                    "问句要求分开统计，但 SQL 没有 GROUP BY",
                )
            )


def _many_to_one(edges: Sequence[SchemaEdge]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (edge.source_table.lower(), edge.target_table.lower())
        for edge in edges
        if edge.source_columns and edge.target_columns
    )


def _owned_aggs(select: exp.Select) -> list[exp.AggFunc]:
    found: list[exp.AggFunc] = []
    for projection in select.expressions:
        found.extend(
            aggregate
            for aggregate in projection.find_all(exp.AggFunc)
            if isinstance(aggregate, exp.AggFunc) and not _nested_select(aggregate, select)
        )
    return found


def _nested_select(node: exp.Expr, stop: exp.Select) -> bool:
    parent = node.parent
    while parent is not None and parent is not stop:
        if isinstance(parent, exp.Select):
            return True
        parent = parent.parent
    return False


def _scope_aliases(select: exp.Select) -> dict[str, str]:
    mapping: dict[str, str] = {}
    source = select.args.get("from_")
    if isinstance(source, exp.From):
        _remember(source.this, mapping)
    joins = select.args.get("joins")
    if isinstance(joins, list):
        for join in joins:
            if isinstance(join, exp.Join):
                _remember(join.this, mapping)
    return mapping


def _remember(node: exp.Expression, mapping: dict[str, str]) -> None:
    if not isinstance(node, exp.Table) or not node.name:
        return
    mapping[node.alias_or_name.lower()] = node.name.lower()
    mapping[node.name.lower()] = node.name.lower()


def _reaches_row_limit(row_count: int | None, max_rows: int | None) -> bool:
    return row_count is not None and max_rows is not None and max_rows > 0 and row_count >= max_rows


def _check_results(
    findings: list[SemanticFinding],
    *,
    row_count: int | None,
    truncated: bool,
    max_rows: int | None,
    plan_rows: float | None,
) -> None:
    if row_count == 0:
        findings.append(SemanticFinding("empty_result", "查询结果为空"))
    elif truncated or _reaches_row_limit(row_count, max_rows):
        findings.append(SemanticFinding("result_too_large", "结果行数达到上限"))
    if plan_rows is not None and plan_rows >= HUGE_PLAN_ROWS:
        findings.append(
            SemanticFinding(
                "explain_cardinality",
                f"执行计划估计约 {plan_rows:.0f} 行，超过 {HUGE_PLAN_ROWS} 行",
            )
        )
