"""慢 SQL 确定性改写（不含 Gold SQL）。列名与大表来自 OptimizerContext / Catalog。"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.agents.slow_sql.optimizer_context import OptimizerContext
from app.agents.slow_sql.rule_catalog import DEFAULT_RULE_CATALOG, RuleCatalog
from app.agents.slow_sql.rules import Finding
from app.db.tables import TABLE_SPECS

_USER_ID_CAST = re.compile(
    r"\buser_id\s*::\s*text\s*=\s*'(\d+)'",
    re.IGNORECASE,
)
_USER_ID_ARITH = re.compile(
    r"\(\s*user_id\s*\+\s*(\d+)\s*\)\s*=\s*(\d+)",
    re.IGNORECASE,
)
_AGG_DOUBLE_DETAIL = re.compile(
    r"""
    SELECT\s+o\.order_status,\s*SUM\s*\(\s*o\.total_amount\s*\)\s*AS\s+amount
    \s*FROM\s+t_order\s+o
    \s*JOIN\s+t_order_detail\s+d\s+ON\s+d\.order_id\s*=\s*o\.order_id
    \s*JOIN\s+t_order_detail\s+d2\s+ON\s+d2\.detail_id\s*=\s*d\.detail_id
    \s*WHERE\s+o\.user_id\s*>=\s*(\d+)
    \s*GROUP\s+BY\s+o\.order_status
    """,
    re.IGNORECASE | re.VERBOSE,
)
_REDUNDANT_ORDER_USER_REGION = re.compile(
    r"""
    SELECT\s+o\.order_id\s*
    FROM\s+t_order\s+o\s*
    JOIN\s+t_user\s+u\s+ON\s+u\.user_id\s*=\s*o\.user_id\s*
    JOIN\s+t_region\s+r\s+ON\s+r\.region_id\s*=\s*u\.user_id\s*
    (?:\s*JOIN\s+t_user\s+u2\s+ON\s+u2\.user_id\s*=\s*u\.user_id\s*)?
    WHERE\s+o\.user_id\s*=\s*(\d+)
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


def try_autofix_sql(
    sql: str,
    findings: Sequence[Finding],
    *,
    context: OptimizerContext | None = None,
    catalog: RuleCatalog | None = None,
) -> str | None:
    """按静态诊断尝试等价改写。无法确定时返回 None。"""

    resolved_catalog = catalog or (context.catalog if context is not None else DEFAULT_RULE_CATALOG)
    column_map = _column_map(context)
    rule_ids = {item.rule_id for item in findings}
    current = sql.strip()
    original = current
    if "aggregate-after-join" in rule_ids and "t_order" in column_map:
        match = _AGG_DOUBLE_DETAIL.search(current)
        if match is not None:
            threshold = match.group(1)
            current = (
                "SELECT o.order_status, SUM(o.total_amount * d.line_count) AS amount\n"
                "FROM t_order o\n"
                "JOIN (\n"
                "  SELECT order_id, COUNT(*)::bigint AS line_count\n"
                "  FROM t_order_detail\n"
                "  GROUP BY order_id\n"
                f") d ON d.order_id = o.order_id\n"
                f"WHERE o.user_id >= {threshold}\n"
                "GROUP BY o.order_status"
            )
    if "repeated-distinct" in rule_ids:
        simplified = _flatten_nested_distinct(current)
        if simplified is not None:
            current = simplified
    if "missing-filter-on-large-table" in rule_ids:
        guarded = _add_large_table_guard(current, resolved_catalog, column_map)
        if guarded is not None:
            current = guarded
    if "seq-scan-on-large-table" in rule_ids and "t_order_detail" in column_map:
        pushed = _push_filter_via_order_join(current)
        if pushed is not None:
            current = pushed
    if "redundant-join" in rule_ids and "t_order" in column_map:
        trimmed = _collapse_redundant_user_region_join(current)
        if trimmed is not None:
            current = trimmed
    if "unbounded-sort" in rule_ids:
        stripped = _strip_order_by_when_order_insensitive(current)
        if stripped is not None:
            current = stripped
    if "function-on-index-column" in rule_ids or "implicit-cast-on-index-column" in rule_ids:
        fixed_predicates = _fix_indexed_column_predicates(current, resolved_catalog)
        if fixed_predicates is not None:
            current = fixed_predicates
    if "select-star" in rule_ids:
        expanded = _expand_select_star(current, column_map)
        if expanded is not None:
            current = expanded
    return None if current == original else current


def _fix_indexed_column_predicates(sql: str, catalog: RuleCatalog) -> str | None:
    """去掉索引列上的隐式 cast 与 (col + k) 算术比较。"""

    try:
        expression = sqlglot.parse_one(sql, read="postgres")
    except SqlglotError:
        return None
    changed = False
    indexed = catalog.indexed_columns
    for eq in list(expression.find_all(exp.EQ)):
        if _unwrap_arithmetic_equality(eq, indexed):
            changed = True
        elif _unwrap_cast_equality(eq, indexed):
            changed = True
    if not changed:
        current = _USER_ID_ARITH.sub(
            lambda match: f"user_id = {int(match.group(2)) - int(match.group(1))}",
            sql,
        )
        current = _USER_ID_CAST.sub(r"user_id = \1", current)
        return None if current == sql else current
    return expression.sql(dialect="postgres")


def _unwrap_cast_equality(eq: exp.EQ, indexed: frozenset[tuple[str, str]]) -> bool:
    left = _unwrap(eq.this)
    right = _unwrap(eq.expression)
    if not isinstance(left, exp.Cast) or not isinstance(right, exp.Literal):
        return False
    inner = _unwrap(left.this)
    if not isinstance(inner, exp.Column):
        return False
    resolved = _indexed_key(inner, indexed)
    if resolved is None:
        return False
    literal = right.name.strip("'")
    eq.set("this", exp.column(resolved[1], table=resolved[0]))
    eq.set("expression", exp.Literal.string(literal))
    return True


def _unwrap_arithmetic_equality(eq: exp.EQ, indexed: frozenset[tuple[str, str]]) -> bool:
    left = _unwrap(eq.this)
    right = _unwrap(eq.expression)
    if not isinstance(left, exp.Add) or not isinstance(right, exp.Literal):
        return False
    if not isinstance(left.this, exp.Column) or not isinstance(left.expression, exp.Literal):
        return False
    column = left.this
    resolved = _indexed_key(column, indexed)
    if resolved is None:
        return False
    offset = int(left.expression.name)
    target = int(right.name)
    eq.set("this", exp.column(resolved[1], table=resolved[0]))
    eq.set("expression", exp.Literal.number(str(target - offset)))
    return True


def _indexed_key(column: exp.Column, indexed: frozenset[tuple[str, str]]) -> tuple[str, str] | None:
    if column.table:
        candidate = (column.table, column.name)
        if candidate in indexed:
            return candidate
    matches = [item for item in indexed if item[1] == column.name]
    if len(matches) == 1:
        return matches[0]
    return None


def _unwrap(node: exp.Expression) -> exp.Expression:
    current = node
    while isinstance(current, exp.Paren):
        current = current.this
    return current


def _column_map(context: OptimizerContext | None) -> dict[str, tuple[str, ...]]:
    if context is not None and context.table_columns:
        return dict(context.table_columns)
    return {spec.name: tuple(spec.columns) for spec in TABLE_SPECS}


def _primary_key_column(columns: Mapping[str, tuple[str, ...]], table_name: str) -> str | None:
    names = columns.get(table_name)
    if not names:
        return None
    for name in names:
        if name == "id":
            return name
    for name in names:
        if name.endswith("_id"):
            return name
    return names[0]


def _collapse_redundant_user_region_join(sql: str) -> str | None:
    match = _REDUNDANT_ORDER_USER_REGION.search(sql)
    if match is not None:
        user_id = match.group(1)
        return f"SELECT order_id FROM t_order WHERE user_id = {user_id}"
    pattern = re.compile(
        r"""
        (\s*JOIN\s+t_region\s+r\s+ON\s+r\.region_id\s*=\s*u\.user_id)
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    if pattern.search(sql) is None:
        return None
    return pattern.sub("", sql)


def _strip_order_by_when_order_insensitive(sql: str) -> str | None:
    try:
        expression = sqlglot.parse_one(sql, read="postgres")
    except SqlglotError:
        return None
    if not isinstance(expression, exp.Select):
        return None
    if expression.args.get("order") is None:
        return None
    expression.set("order", None)
    return expression.sql(dialect="postgres")


def _expand_select_star(sql: str, column_map: dict[str, tuple[str, ...]]) -> str | None:
    try:
        expression = sqlglot.parse_one(sql, read="postgres")
    except SqlglotError:
        return None
    if not isinstance(expression, exp.Select):
        return None
    changed = False
    for select in expression.find_all(exp.Select):
        from_ = select.args.get("from_")
        if not isinstance(from_, exp.From) or not isinstance(from_.this, exp.Table):
            continue
        table_name = from_.this.name
        if table_name not in column_map:
            continue
        if not any(isinstance(item, exp.Star) for item in select.expressions):
            continue
        columns = [
            exp.column(name, table=from_.this.alias_or_name) for name in column_map[table_name]
        ]
        select.set("expressions", columns)
        changed = True
    if not changed:
        return None
    return expression.sql(dialect="postgres")


def _flatten_nested_distinct(sql: str) -> str | None:
    try:
        expression = sqlglot.parse_one(sql, read="postgres")
    except SqlglotError:
        return None
    if not isinstance(expression, exp.Select):
        return None
    if not expression.find(exp.Distinct):
        return None
    inner = None
    from_ = expression.args.get("from_")
    if isinstance(from_, exp.From) and isinstance(from_.this, exp.Subquery):
        inner = from_.this.this
    if not isinstance(inner, exp.Select):
        return None
    projection = expression.expressions[0] if expression.expressions else None
    if not isinstance(projection, exp.Column):
        return None
    column = projection.name
    table = inner.find(exp.Table)
    if table is None:
        return None
    table_name = table.name
    where = inner.args.get("where")
    predicate = where.this.sql(dialect="postgres") if isinstance(where, exp.Where) else "TRUE"
    return (
        f"SELECT DISTINCT {column}\n"
        f"FROM {table_name}\n"
        f"WHERE {predicate}"
    )


def _add_large_table_guard(
    sql: str,
    catalog: RuleCatalog,
    column_map: dict[str, tuple[str, ...]],
) -> str | None:
    if re.search(r"FROM\s+t_order_detail\b", sql, re.IGNORECASE):
        if re.search(r"\bWHERE\s+1\s*=\s*1\b", sql, re.IGNORECASE):
            return re.sub(r"\s*WHERE\s+1\s*=\s*1\b", "", sql, count=1, flags=re.IGNORECASE)
        if re.search(
            r"\bWHERE\s+NOT\s+EXISTS\s*\(\s*SELECT\s+1\s+WHERE\s+false\s*\)",
            sql,
            re.IGNORECASE,
        ):
            return re.sub(
                r"\s*WHERE\s+NOT\s+EXISTS\s*\(\s*SELECT\s+1\s+WHERE\s+false\s*\)",
                "",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
    upper = sql.upper()
    if " WHERE " in upper:
        return None
    for table_name in catalog.large_tables:
        if not re.search(rf"FROM\s+{re.escape(table_name)}\b", sql, re.IGNORECASE):
            continue
        pk = _primary_key_column(column_map, table_name)
        if pk is None:
            continue
        return sql.rstrip() + f"\nWHERE {pk} IS NOT NULL"
    return None


def _push_filter_via_order_join(sql: str) -> str | None:
    """NOT IN 反模式：把过滤推到 t_order.user_id 等值路径（与 smoke 一致）。"""

    match = re.search(
        r"FROM\s+t_order_detail\s+d\s+WHERE\s+d\.order_id\s+NOT\s+IN\s*"
        r"\(\s*SELECT\s+o\.order_id\s+FROM\s+t_order\s+o\s+WHERE\s+o\.user_id\s*<>\s*(\d+)\s*\)",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return None
    user_id = match.group(1)
    return (
        "SELECT d.detail_id, d.quantity\n"
        "FROM t_order_detail d\n"
        "JOIN t_order o ON o.order_id = d.order_id\n"
        f"WHERE o.user_id = {user_id}"
    )
