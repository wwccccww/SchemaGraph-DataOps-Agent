"""SQLGlot 全 AST 只读门禁。解析失败时拒绝，不降级为关键字检查。"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.sandbox.errors import ExecutionError, make_error

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}")
_QUERY_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except, exp.Values)
_STRUCTURAL = (exp.And, exp.Or, exp.Not, exp.Exists, exp.Cast, exp.TryCast, exp.Case, exp.If)
_FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Copy,
    exp.Command,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Set,
    exp.Grant,
    exp.Revoke,
    exp.Analyze,
    exp.Describe,
    exp.Show,
    exp.Use,
    exp.Lock,
    exp.Pragma,
    exp.Install,
    exp.Cache,
    exp.Uncache,
    exp.LoadData,
)
# SQLGlot 的内部类型名和 PostgreSQL 渲染出的函数名并不总是相同。
# 门禁按渲染后的函数名审计，不把内部名加入白名单。
_SURFACE_FUNCTION_NAMES: dict[type[exp.Expression], str] = {
    exp.TimestampTrunc: "date_trunc",
    exp.TimeToStr: "to_char",
}
_ALLOWED_FUNCTIONS = frozenset(
    {
        "abs",
        "age",
        "array_agg",
        "array_length",
        "array_lower",
        "array_ndims",
        "array_position",
        "array_to_string",
        "array_upper",
        "ascii",
        "avg",
        "bit_length",
        "bool_and",
        "bool_or",
        "btrim",
        "cardinality",
        "ceil",
        "ceiling",
        "char_length",
        "character_length",
        "chr",
        "clock_timestamp",
        "coalesce",
        "concat",
        "concat_ws",
        "count",
        "cume_dist",
        "current_database",
        "current_date",
        "current_schema",
        "current_setting",
        "current_time",
        "current_timestamp",
        "current_user",
        "date",
        "date_part",
        "date_trunc",
        "degrees",
        "dense_rank",
        "div",
        "every",
        "exp",
        "extract",
        "first_value",
        "floor",
        "format",
        "generate_series",
        "generate_subscripts",
        "greatest",
        "initcap",
        "json_agg",
        "json_array_length",
        "json_typeof",
        "jsonb_agg",
        "jsonb_array_length",
        "jsonb_typeof",
        "lag",
        "last_value",
        "lead",
        "least",
        "left",
        "length",
        "ln",
        "localtime",
        "localtimestamp",
        "log",
        "log10",
        "lower",
        "ltrim",
        "max",
        "md5",
        "min",
        "mod",
        "now",
        "nth_value",
        "ntile",
        "nullif",
        "num_nonnulls",
        "num_nulls",
        "octet_length",
        "percent_rank",
        "percentile_cont",
        "percentile_disc",
        "pg_typeof",
        "pi",
        "position",
        "power",
        "quote_ident",
        "quote_literal",
        "quote_nullable",
        "radians",
        "random",
        "rank",
        "replace",
        "reverse",
        "right",
        "round",
        "row_number",
        "rtrim",
        "session_user",
        "sign",
        "split_part",
        "sqrt",
        "starts_with",
        "statement_timestamp",
        "stddev",
        "stddev_pop",
        "stddev_samp",
        "string_agg",
        "string_to_array",
        "strpos",
        "substr",
        "substring",
        "sum",
        "to_char",
        "to_date",
        "to_number",
        "to_timestamp",
        "transaction_timestamp",
        "translate",
        "trim",
        "trunc",
        "unnest",
        "upper",
        "var_pop",
        "var_samp",
        "variance",
        "version",
        "width_bucket",
    }
)


@dataclass(frozen=True)
class GateDecision:
    """门禁结果。accepted 时 sql 是 AST 重新渲染的单条语句。"""

    sql: str
    error: ExecutionError | None


def allowed_read_only_functions() -> frozenset[str]:
    """返回只读函数白名单。

    只有 Gold SQL 已经使用、并且本身只读的函数才可以加入。
    不能因为模型写出了未知函数就放行。
    """

    return _ALLOWED_FUNCTIONS


def check_read_only_sql(sql: str, *, dialect: str = "postgres") -> GateDecision:
    """遍历整棵 AST。失败时不得把原始 SQL 发给数据库。"""

    if dialect not in {"postgres", "sqlite"}:
        return GateDecision(sql="", error=_reject("syntax_error", "不支持的 SQL 方言"))
    if sql.strip() == "":
        return GateDecision(sql="", error=_reject("syntax_error", "SQL 为空"))
    try:
        statements = sqlglot.parse(sql, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)
    except SqlglotError:
        return GateDecision(sql="", error=_reject("syntax_error", "SQL 无法解析"))
    expressions = [statement for statement in statements if statement is not None]
    if len(expressions) != 1:
        return GateDecision(sql="", error=_reject("multi_statement", "只允许单条语句"))
    expression = expressions[0]
    if not isinstance(expression, _QUERY_ROOTS):
        return GateDecision(sql="", error=_reject("not_read_only", "只允许只读 SELECT"))
    for node in expression.walk():
        if isinstance(node, _FORBIDDEN):
            return GateDecision(sql="", error=_reject("not_read_only", "只允许只读 SELECT"))
        if isinstance(node, exp.Select) and (node.args.get("into") or node.args.get("locks")):
            return GateDecision(sql="", error=_reject("not_read_only", "只允许只读 SELECT"))
        if isinstance(node, exp.Func) and not isinstance(node, _STRUCTURAL):
            rejected = _reject_function(node)
            if rejected is not None:
                return GateDecision(sql="", error=rejected)
    recursive = _recursive_cte_error(expression)
    if recursive is not None:
        return GateDecision(sql="", error=recursive)
    return GateDecision(sql=expression.sql(dialect=dialect), error=None)


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return node.name.lower()
    for kind, surface in _SURFACE_FUNCTION_NAMES.items():
        if isinstance(node, kind):
            return surface
    return node.sql_name().lower()


def _reject_function(node: exp.Func) -> ExecutionError | None:
    name = _function_name(node)
    schema = _schema_name(node)
    if schema not in {None, "pg_catalog"} or name not in _ALLOWED_FUNCTIONS:
        if _IDENTIFIER.fullmatch(name) is None:
            return _reject("disallowed_function", "函数不在允许列表中")
        return _reject("disallowed_function", f"函数不在允许列表中: {name}")
    return None


def _recursive_cte_error(expression: exp.Expression) -> ExecutionError | None:
    """自身引用却没有 WITH RECURSIVE 时，在查询数据库前拒绝。"""

    for clause in expression.find_all(exp.With):
        if clause.args.get("recursive"):
            continue
        for cte in clause.find_all(exp.CTE):
            name = cte.alias
            body = cte.this
            if not isinstance(name, str) or not isinstance(body, exp.Expression):
                continue
            if any(table.name == name for table in body.find_all(exp.Table)):
                return _reject(
                    "recursive_cte_missing",
                    (
                        f"CTE {name} 在定义内引用了自身。"
                        "补上 WITH RECURSIVE，或者改成对目标值的非递归等值过滤"
                    ),
                )
    return None


def _schema_name(node: exp.Func) -> str | None:
    parent = node.parent
    if not isinstance(parent, exp.Dot) or parent.expression is not node:
        return None
    left = parent.this
    if isinstance(left, exp.Identifier):
        return left.name.lower()
    return "<qualified>"


def _reject(category: str, message: str) -> ExecutionError:
    return make_error(
        category=category,
        message=message,
        exception_type="SqlGateRejection",
        retryable=True,
    )
