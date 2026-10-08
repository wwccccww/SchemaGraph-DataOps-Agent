"""慢 SQL 静态规则。规则只读 AST，不连接数据库。"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.agents.slow_sql.rule_catalog import DEFAULT_RULE_CATALOG, RuleCatalog

Severity = Literal["high", "medium", "low"]
_ARITHMETIC = (exp.Add, exp.Sub, exp.Mul, exp.Div, exp.Mod, exp.Neg)
_COMPARISONS = (exp.EQ, exp.NEQ, exp.GT, exp.LT, exp.GTE, exp.LTE, exp.In, exp.Like, exp.ILike)
LARGE_TABLES = DEFAULT_RULE_CATALOG.large_tables
_RULE_ORDER = (
    "select-star",
    "missing-filter-on-large-table",
    "function-on-index-column",
    "implicit-cast-on-index-column",
    "correlated-subquery",
    "aggregate-after-join",
    "unbounded-sort",
    "repeated-distinct",
    "redundant-join",
    "seq-scan-on-large-table",
)


@dataclass(frozen=True)
class Finding:
    """一条诊断。message 是给模型和调用方的固定说明。"""

    rule_id: str
    severity: Severity
    message: str


_FINDINGS: Mapping[str, Finding] = {
    "select-star": Finding("select-star", "medium", "查询使用了 SELECT *"),
    "missing-filter-on-large-table": Finding(
        "missing-filter-on-large-table",
        "high",
        "大表缺少过滤条件",
    ),
    "function-on-index-column": Finding(
        "function-on-index-column",
        "high",
        "索引列上使用了函数或表达式",
    ),
    "implicit-cast-on-index-column": Finding(
        "implicit-cast-on-index-column",
        "high",
        "索引列发生隐式类型转换",
    ),
    "correlated-subquery": Finding("correlated-subquery", "medium", "存在相关子查询"),
    "aggregate-after-join": Finding(
        "aggregate-after-join",
        "high",
        "可提前聚合却在多对多 Join 后聚合",
    ),
    "unbounded-sort": Finding("unbounded-sort", "medium", "排序没有 LIMIT"),
    "repeated-distinct": Finding("repeated-distinct", "medium", "查询重复去重"),
    "redundant-join": Finding("redundant-join", "medium", "存在未使用列的冗余 Join"),
    "seq-scan-on-large-table": Finding(
        "seq-scan-on-large-table",
        "high",
        "大表发生全表扫描",
    ),
}


def diagnose_sql(
    sql: str,
    *,
    catalog: RuleCatalog | None = None,
) -> tuple[Finding, ...]:
    """返回静态规则命中。解析失败时不猜测，交给 SQL 门禁处理。"""

    resolved = catalog or DEFAULT_RULE_CATALOG
    try:
        expression = sqlglot.parse_one(sql, read="postgres")
    except SqlglotError:
        return ()
    flags = {rule_id: False for rule_id in _RULE_ORDER}
    for select in expression.find_all(exp.Select):
        _inspect_select(select, flags, resolved)
    if isinstance(expression, exp.Expression) and _correlated(expression):
        flags["correlated-subquery"] = True
    if len(list(expression.find_all(exp.Distinct))) >= 2:
        flags["repeated-distinct"] = True
    return tuple(_FINDINGS[rule_id] for rule_id in _RULE_ORDER if flags[rule_id])


def finding_for_seq_scan(
    nodes: Sequence[tuple[str, str | None]],
    *,
    catalog: RuleCatalog | None = None,
) -> Finding | None:
    """计划里的大表顺序扫描。Parallel Seq Scan 与 Seq Scan 同样计数。"""

    resolved = catalog or DEFAULT_RULE_CATALOG
    sequential = {"Seq Scan", "Parallel Seq Scan"}
    for node_type, relation in nodes:
        if node_type in sequential and relation in resolved.large_tables:
            return _FINDINGS["seq-scan-on-large-table"]
    return None


def _inspect_select(select: exp.Select, flags: dict[str, bool], catalog: RuleCatalog) -> None:
    tables = _direct_tables(select)
    aliases = _alias_map(tables)
    if any(_is_star(projection) for projection in select.expressions):
        flags["select-star"] = True
    predicates = _predicates(select)
    if _missing_large_table_filter(tables, aliases, predicates, catalog):
        flags["missing-filter-on-large-table"] = True
    if _predicate_match(predicates, aliases, lambda node, aliases: _wraps_indexed_column(node, aliases, catalog)):
        flags["function-on-index-column"] = True
    if _predicate_match(predicates, aliases, lambda node, aliases: _casts_indexed_column(node, aliases, catalog)):
        flags["implicit-cast-on-index-column"] = True
    if _aggregate_after_join(select, tables, aliases, catalog):
        flags["aggregate-after-join"] = True
    if select.args.get("order") is not None and select.args.get("limit") is None:
        flags["unbounded-sort"] = True
    if _redundant_join(select, aliases):
        flags["redundant-join"] = True


def _is_star(projection: exp.Expression) -> bool:
    if isinstance(projection, exp.Star):
        return True
    return isinstance(projection, exp.Column) and isinstance(projection.this, exp.Star)


def _direct_tables(select: exp.Select) -> list[exp.Table]:
    tables: list[exp.Table] = []
    from_ = select.args.get("from_")
    if isinstance(from_, exp.From) and isinstance(from_.this, exp.Table):
        tables.append(from_.this)
    joins = select.args.get("joins")
    if isinstance(joins, list):
        for join in joins:
            if isinstance(join, exp.Join) and isinstance(join.this, exp.Table):
                tables.append(join.this)
    return tables


def _alias_map(tables: Sequence[exp.Table]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for table in tables:
        mapping[table.name] = table.name
        if table.alias:
            mapping[table.alias] = table.name
    return mapping


def _predicates(select: exp.Select) -> list[exp.Expression]:
    nodes: list[exp.Expression] = []
    where = select.args.get("where")
    if isinstance(where, exp.Where):
        nodes.append(where.this)
    joins = select.args.get("joins")
    if isinstance(joins, list):
        for join in joins:
            if isinstance(join, exp.Join):
                on = join.args.get("on")
                if isinstance(on, exp.Expression):
                    nodes.append(on)
    return nodes


def _missing_large_table_filter(
    tables: Sequence[exp.Table],
    aliases: Mapping[str, str],
    predicates: Sequence[exp.Expression],
    catalog: RuleCatalog,
) -> bool:
    referenced = {
        resolved[0]
        for predicate in predicates
        for column in _local_columns(predicate)
        if (resolved := _resolve(column, aliases)) is not None
    }
    return any(
        table.name in catalog.large_tables and table.name not in referenced for table in tables
    )


def _predicate_match(
    predicates: Sequence[exp.Expression],
    aliases: Mapping[str, str],
    matcher: Callable[[exp.Expression, Mapping[str, str]], bool],
) -> bool:
    for predicate in predicates:
        for comparison in _local_comparisons(predicate):
            for operand in _operands(comparison):
                if matcher(operand, aliases):
                    return True
    return False


def _wraps_indexed_column(
    node: exp.Expression,
    aliases: Mapping[str, str],
    catalog: RuleCatalog,
) -> bool:
    current = _unwrap(node)
    if isinstance(current, exp.Column | exp.Cast):
        return False
    if not isinstance(current, (exp.Func, *_ARITHMETIC)):
        return False
    for column in current.find_all(exp.Column):
        if _resolve(column, aliases) in catalog.indexed_columns:
            return True
    return False


def _casts_indexed_column(
    node: exp.Expression,
    aliases: Mapping[str, str],
    catalog: RuleCatalog,
) -> bool:
    current = _unwrap(node)
    if not isinstance(current, exp.Cast):
        return False
    inner = _unwrap(current.this)
    if not isinstance(inner, exp.Column):
        return False
    return _resolve(inner, aliases) in catalog.indexed_columns


def _aggregate_after_join(
    select: exp.Select,
    tables: Sequence[exp.Table],
    aliases: Mapping[str, str],
    catalog: RuleCatalog,
) -> bool:
    if not any(table.name in catalog.child_tables for table in tables):
        return False
    roots: list[exp.Expression] = list(select.expressions)
    having = select.args.get("having")
    if isinstance(having, exp.Expression):
        roots.append(having)
    for root in roots:
        for aggregate in root.find_all(exp.AggFunc):
            if not isinstance(aggregate, exp.Expression) or _inside_nested_query(aggregate, root):
                continue
            for column in aggregate.find_all(exp.Column):
                resolved = _resolve(column, aliases)
                if resolved is not None and resolved[0] not in catalog.child_tables:
                    return True
    return False


def _redundant_join(select: exp.Select, aliases: Mapping[str, str]) -> bool:
    joins = select.args.get("joins")
    if not isinstance(joins, list):
        return False
    for join in joins:
        if not isinstance(join, exp.Join) or not isinstance(join.this, exp.Table):
            continue
        alias = join.this.alias or join.this.name
        if _used_outside(select, join, alias, aliases):
            continue
        on = join.args.get("on")
        if not isinstance(on, exp.Expression) or _equijoin_only(on, alias):
            return True
    return False


def _used_outside(
    select: exp.Select,
    own_join: exp.Join,
    alias: str,
    aliases: Mapping[str, str],
) -> bool:
    roots: list[exp.Expression] = list(select.expressions)
    for key in ("where", "group", "having", "order"):
        node = select.args.get(key)
        if isinstance(node, exp.Expression):
            roots.append(node)
    joins = select.args.get("joins")
    if isinstance(joins, list):
        for join in joins:
            if join is own_join or not isinstance(join, exp.Join):
                continue
            on = join.args.get("on")
            if isinstance(on, exp.Expression):
                roots.append(on)
    for root in roots:
        for column in _local_columns(root):
            if column.table == alias:
                return True
            resolved = _resolve(column, aliases)
            single_table = len(set(aliases.values())) == 1
            if (
                resolved is not None
                and column.table == ""
                and resolved[0] == aliases.get(alias)
                and single_table
            ):
                return True
    return False


def _equijoin_only(on: exp.Expression, alias: str) -> bool:
    for column in _local_columns(on):
        if column.table != alias:
            continue
        if not _paired_with_column(column):
            return False
    return True


def _paired_with_column(column: exp.Column) -> bool:
    parent = column.parent
    while isinstance(parent, exp.Paren):
        parent = parent.parent
    if not isinstance(parent, exp.EQ) or not isinstance(parent.expression, exp.Expression):
        return False
    left = _unwrap(parent.this)
    right = _unwrap(parent.expression)
    if left is column:
        return isinstance(right, exp.Column)
    if right is column:
        return isinstance(left, exp.Column)
    return False


def _correlated(expression: exp.Expression) -> bool:
    for select in expression.find_all(exp.Select):
        local = set(_alias_map(_direct_tables(select)))
        outer: set[str] = set()
        parent = select.parent
        while parent is not None:
            if isinstance(parent, exp.Select):
                outer.update(_alias_map(_direct_tables(parent)))
            parent = parent.parent
        for column in _local_columns(select):
            if column.table and column.table not in local and column.table in outer:
                return True
    return False


def _resolve(column: exp.Column, aliases: Mapping[str, str]) -> tuple[str, str] | None:
    if column.table:
        table = aliases.get(column.table)
        if table is None:
            return None
        return table, column.name
    tables = set(aliases.values())
    if len(tables) == 1:
        return next(iter(tables)), column.name
    return None


def _operands(comparison: exp.Expression) -> list[exp.Expression]:
    if isinstance(comparison, exp.In):
        values = [comparison.this, *comparison.expressions]
        query = comparison.args.get("query")
        if isinstance(query, exp.Expression):
            values.append(query)
        return [value for value in values if isinstance(value, exp.Expression)]
    expression = comparison.args.get("expression")
    if isinstance(expression, exp.Expression):
        return [comparison.this, expression]
    return [comparison.this]


def _local_columns(root: exp.Expression) -> list[exp.Column]:
    return [
        node
        for node in root.find_all(exp.Column)
        if isinstance(node, exp.Column) and not _inside_nested_query(node, root)
    ]


def _local_comparisons(root: exp.Expression) -> list[exp.Expression]:
    return [
        node
        for node in root.walk()
        if isinstance(node, _COMPARISONS) and not _inside_nested_query(node, root)
    ]


def _inside_nested_query(node: exp.Expression, root: exp.Expression) -> bool:
    if node is root:
        return False
    current = node.parent
    while current is not None and current is not root:
        if isinstance(current, exp.Select | exp.Union | exp.Subquery):
            return True
        current = current.parent
    return False


def _unwrap(node: exp.Expression) -> exp.Expression:
    current = node
    while isinstance(current, exp.Paren):
        current = current.this
    return current
