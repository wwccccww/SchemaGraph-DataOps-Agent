"""从预测 SQL 提取可诊断结构。不读取 Gold，解析失败也不抛出。"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.observability.tracing import sql_hash


@dataclass(frozen=True)
class PredictionShape:
    """一条预测 SQL 的结构摘要。SQL 原文只进入本地评测报告。"""

    sql: str | None
    sql_hash: str
    referenced_tables: tuple[str, ...]
    projections: tuple[str, ...]
    joins: tuple[str, ...]
    predicates: tuple[str, ...]
    group_by: tuple[str, ...]
    aggregations: tuple[str, ...]
    order_by: tuple[str, ...]
    parse_error: str | None

    @classmethod
    def empty(cls, *, sql: str | None = None, parse_error: str | None = None) -> PredictionShape:
        return cls(
            sql=sql,
            sql_hash=sql_hash(sql) if sql else "",
            referenced_tables=(),
            projections=(),
            joins=(),
            predicates=(),
            group_by=(),
            aggregations=(),
            order_by=(),
            parse_error=parse_error,
        )

    def as_json(self) -> dict[str, object]:
        return {
            "sql": self.sql,
            "sql_hash": self.sql_hash,
            "referenced_tables": list(self.referenced_tables),
            "projections": list(self.projections),
            "joins": list(self.joins),
            "predicates": list(self.predicates),
            "group_by": list(self.group_by),
            "aggregations": list(self.aggregations),
            "order_by": list(self.order_by),
            "parse_error": self.parse_error,
        }


def describe_sql(sql: str | None) -> PredictionShape:
    """解析一条预测 SQL。空文本和语法错误返回带说明的空结构。"""

    if sql is None or sql.strip() == "":
        return PredictionShape.empty(parse_error="SQL 为空")
    try:
        statements = sqlglot.parse(sql, read="postgres", error_level=sqlglot.ErrorLevel.RAISE)
    except SqlglotError:
        return PredictionShape.empty(sql=sql, parse_error="SQL 无法解析")
    expressions = [statement for statement in statements if statement is not None]
    if len(expressions) != 1:
        return PredictionShape.empty(sql=sql, parse_error="只允许单条语句")
    expression = expressions[0]
    tables = _tables(expression)
    if not isinstance(expression, exp.Query):
        return PredictionShape(
            sql=sql,
            sql_hash=sql_hash(sql),
            referenced_tables=tables,
            projections=(),
            joins=(),
            predicates=(),
            group_by=(),
            aggregations=(),
            order_by=(),
            parse_error="不是只读查询",
        )
    select = expression if isinstance(expression, exp.Select) else expression.find(exp.Select)
    if not isinstance(select, exp.Select):
        return PredictionShape.empty(sql=sql, parse_error="SQL 没有投影")
    return PredictionShape(
        sql=sql,
        sql_hash=sql_hash(sql),
        referenced_tables=tables,
        projections=_projections(select),
        joins=_joins(expression),
        predicates=_predicates(select),
        group_by=_group_by(select),
        aggregations=_aggregations(select),
        order_by=_order_by(select),
        parse_error=None,
    )


def _tables(expression: exp.Expr) -> tuple[str, ...]:
    cte_names = {cte.alias for cte in expression.find_all(exp.CTE) if cte.alias}
    names = {table.name for table in expression.find_all(exp.Table) if table.name not in cte_names}
    return tuple(sorted(names))


def _projections(select: exp.Select) -> tuple[str, ...]:
    names: list[str] = []
    for expression in select.expressions:
        name = expression.alias_or_name
        if not isinstance(name, str) or name == "":
            name = expression.sql(dialect="postgres")
        names.append(name)
    return tuple(names)


def _joins(expression: exp.Expr) -> tuple[str, ...]:
    rendered: list[str] = []
    for join in expression.find_all(exp.Join):
        target = join.this
        name = target.name if isinstance(target, exp.Table) else target.sql(dialect="postgres")
        condition = join.args.get("on")
        on_sql = condition.sql(dialect="postgres") if isinstance(condition, exp.Expression) else ""
        kind = " ".join(part for part in (join.side, join.kind or "JOIN") if part)
        rendered.append(f"{kind} {name} ON {on_sql}".strip())
    return tuple(rendered)


def _predicates(select: exp.Select) -> tuple[str, ...]:
    clauses: list[str] = []
    where = select.args.get("where")
    if isinstance(where, exp.Where):
        clauses.append(f"WHERE {where.this.sql(dialect='postgres')}")
    having = select.args.get("having")
    if isinstance(having, exp.Having):
        clauses.append(f"HAVING {having.this.sql(dialect='postgres')}")
    return tuple(clauses)


def _group_by(select: exp.Select) -> tuple[str, ...]:
    group = select.args.get("group")
    if not isinstance(group, exp.Group):
        return ()
    return tuple(expression.sql(dialect="postgres") for expression in group.expressions)


def _aggregations(select: exp.Select) -> tuple[str, ...]:
    names: list[str] = []
    for projection in select.expressions:
        names.extend(agg.sql_name().lower() for agg in projection.find_all(exp.AggFunc))
    return tuple(dict.fromkeys(names))


def _order_by(select: exp.Select) -> tuple[str, ...]:
    order = select.args.get("order")
    if not isinstance(order, exp.Order):
        return ()
    rendered: list[str] = []
    for expression in order.expressions:
        direction = "DESC" if expression.args.get("desc") else "ASC"
        rendered.append(f"{expression.this.sql(dialect='postgres')} {direction}")
    return tuple(rendered)
