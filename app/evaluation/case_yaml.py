"""外部评测用例的 YAML 往返。导入本模块不会访问数据库或网络。"""

from __future__ import annotations

import json

import sqlglot
from sqlglot import exp

from app.schemas.benchmark import BenchmarkCase


def dump_benchmark_cases(cases: list[BenchmarkCase]) -> str:
    """写成可再次解析的 YAML。Gold SQL 放在字面量块中。"""

    lines = ['contract_version: "1.0"', "cases:"]
    for case in cases:
        lines.extend(_emit_case(case))
    return "\n".join(lines) + "\n"


def projection_names(sql: str, *, dialect: str) -> list[str]:
    """取最外层投影名称。名称必须能在没有数据库时确定。"""

    statement = sql.strip().rstrip(";").strip()
    parsed = sqlglot.parse_one(statement, read=dialect)
    if not isinstance(parsed, exp.Expression):
        raise ValueError("gold SQL did not parse")
    select = parsed if isinstance(parsed, exp.Select) else parsed.find(exp.Select)
    if not isinstance(select, exp.Select):
        raise ValueError("gold SQL has no projection")
    names: list[str] = []
    for expression in select.expressions:
        name = expression.alias_or_name
        if not isinstance(name, str) or name == "":
            name = expression.sql(dialect=dialect)
        if name == "":
            raise ValueError("projection has no column name")
        names.append(name)
    if not names:
        raise ValueError("projection is empty")
    return names


def _emit_case(case: BenchmarkCase) -> list[str]:
    payload = case.model_dump(mode="json")
    lines = [f"  - id: {payload['id']}"]
    for key in ("source", "source_version", "database_id", "difficulty", "dialect"):
        lines.append(f"    {key}: {payload[key]}")
    lines.append(f"    question: {json.dumps(payload['question'], ensure_ascii=False)}")
    lines.append("    gold_sql: |-")
    lines.extend(f"      {line}" for line in str(payload["gold_sql"]).split("\n"))
    lines.extend(_emit_list("required_tables", payload["required_tables"]))
    lines.extend(_emit_list("required_junctions", payload["required_junctions"]))
    tolerance = payload["numeric_tolerance"]
    lines.append(f"    order_sensitive: {str(payload['order_sensitive']).lower()}")
    if tolerance is None:
        lines.append("    numeric_tolerance: null")
    else:
        lines.append(f"    numeric_tolerance: {tolerance}")
    lines.extend(_emit_list("expected_columns", payload["expected_columns"]))
    lines.append(f"    anchor_date: {json.dumps(payload['anchor_date'])}")
    lines.extend(_emit_list("tags", payload["tags"]))
    contract = payload.get("semantic_contract")
    if contract is not None:
        lines.extend(_emit_contract(contract))
    return lines


def _emit_contract(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        raise TypeError("semantic_contract")
    lines = ["    semantic_contract:"]
    lines.extend(_emit_list("projections", payload["projections"], indent=6))
    lines.extend(_emit_list("group_keys", payload["group_keys"], indent=6))
    lines.extend(_emit_list("filters", payload["filters"], indent=6))
    lines.append(f"      category_scope: {payload['category_scope']}")
    window = payload["time_window"]
    if window is None:
        lines.append("      time_window: null")
    else:
        if not isinstance(window, dict):
            raise TypeError("time_window")
        lines.append("      time_window:")
        lines.append(f"        start: {json.dumps(window['start'])}")
        lines.append(f"        end: {json.dumps(window['end'])}")
        lines.append(f"        anchor_date: {json.dumps(window['anchor_date'])}")
    dedup = payload["dedup_key"]
    lines.append("      dedup_key: null" if dedup is None else f"      dedup_key: {dedup}")
    return lines


def _emit_list(key: str, values: object, indent: int = 4) -> list[str]:
    if not isinstance(values, list):
        raise TypeError(key)
    pad = " " * indent
    child = " " * (indent + 2)
    if not values:
        return [f"{pad}{key}: []"]
    lines = [f"{pad}{key}:"]
    lines.extend(f"{child}- {json.dumps(item, ensure_ascii=False)}" for item in values)
    return lines
