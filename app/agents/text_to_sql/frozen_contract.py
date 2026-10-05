"""冻结语义契约进入 Generic Prompt。不是 Gold SQL，与 cases.yaml 一并发布。"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.evaluation.sql_shape import describe_sql
from app.agents.text_to_sql.semantic import SemanticFinding
from app.schemas.benchmark import SemanticContract

_PROJECTION_COLUMNS: dict[str, str] = {
    "item_category": "item.i_category",
    "store_state": "store.s_state",
    "return_reason": "reason.r_reason_desc",
    "sales_year": "date_dim.d_year",
    "return_year": "date_dim.d_year",
}
_PROJECTION_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("item_category", ("item",)),
    ("income_lower", ("income_band", "household_demographics")),
    ("buy_potential", ("household_demographics",)),
    ("marital_status", ("customer_demographics",)),
    ("education_status", ("customer_demographics",)),
    ("call_center", ("call_center",)),
    ("ship_mode", ("ship_mode",)),
    ("web_site", ("web_site",)),
    ("warehouse", ("warehouse",)),
    ("reason", ("reason",)),
    ("promo", ("promotion",)),
)
_ALIAS = re.compile(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)


def format_frozen_semantic_contract(contract: SemanticContract) -> str:
    lines = [
        "冻结语义契约（与问句一并发布，不含 Gold SQL）：",
        f"最终 SELECT 列名（AS 别名）应覆盖：{'、'.join(contract.projections)}",
    ]
    if contract.group_keys:
        lines.append(f"GROUP BY 键：{'、'.join(contract.group_keys)}")
    if contract.filters:
        lines.append(f"过滤语义：{'；'.join(contract.filters)}")
    for name in contract.projections:
        column = _PROJECTION_COLUMNS.get(name)
        if column is not None:
            lines.append(f"列 {name} 优先投影 {column}（AS {name}）")
    for hint in _filter_hints(contract.filters):
        lines.append(hint)
    if contract.time_window is not None:
        lines.append(
            f"时间窗口：{contract.time_window.start} 至 {contract.time_window.end}"
        )
    hinted = _tables_for_projections(contract.projections)
    if hinted:
        lines.append("这些投影通常需要 JOIN 表：" + "、".join(sorted(hinted)))
    return "\n".join(lines)


def check_frozen_semantic_contract(
    contract: SemanticContract,
    sql: str,
    *,
    dialect: str,
) -> tuple[SemanticFinding, ...]:
    """执行后对照冻结契约做结构复核。"""

    described = describe_sql(sql, dialect=dialect)
    referenced = {name.lower() for name in described.referenced_tables}
    findings: list[SemanticFinding] = []
    for table in _tables_for_projections(contract.projections):
        if table.lower() not in referenced:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    f"冻结契约投影需要表 {table} 出现在 SQL 中",
                )
            )
    aliases = {name.lower() for name in _select_aliases(sql)}
    for name in contract.projections:
        if name.lower() not in aliases and name.lower() not in " ".join(
            described.projections
        ).lower():
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    f"冻结契约要求输出列 {name}，请用 AS {name} 投影",
                )
            )
    for name in contract.projections:
        column = _PROJECTION_COLUMNS.get(name)
        if column is None:
            continue
        base = column.split(".")[-1].lower()
        if base not in sql.lower():
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    f"列 {name} 应使用 {column}，不要用其它 surrogate 列代替",
                )
            )
    primary = _primary_fact(contract.filters)
    if primary is not None and primary.lower() not in referenced:
        findings.append(
            SemanticFinding(
                "missing_entity",
                f"冻结契约要求主事实表 {primary} 出现在 SQL 中",
            )
        )
    if contract.group_keys and described.aggregations:
        grouped = " ".join(described.group_by).lower()
        for key in contract.group_keys:
            if key.lower() not in grouped and key.lower() not in aliases:
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        f"聚合查询的 GROUP BY 需包含 {key}",
                    )
                )
    return tuple(findings)


def _tables_for_projections(projections: Sequence[str]) -> tuple[str, ...]:
    names: list[str] = []
    for projection in projections:
        lowered = projection.lower()
        for suffix, tables in _PROJECTION_TABLES:
            if suffix in lowered or lowered.endswith(suffix):
                for table in tables:
                    if table not in names:
                        names.append(table)
    return tuple(names)


def _select_aliases(sql: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_ALIAS.findall(sql)))


def _primary_fact(filters: Sequence[str]) -> str | None:
    for item in filters:
        if item.startswith("primary_fact="):
            return item.split("=", 1)[1]
    return None


def _filter_hints(filters: Sequence[str]) -> tuple[str, ...]:
    hints: list[str] = []
    for item in filters:
        if item == "promotion_channel=dmail":
            hints.append(
                "直邮促销：promotion.p_channel_dmail='Y'，并用 ss_item_sk IN (SELECT p_item_sk FROM promotion ...) 或 ss_promo_sk 关联，不要仅用 item 与 promotion 的笛卡尔 JOIN"
            )
        if item.startswith("primary_fact="):
            table = item.split("=", 1)[1]
            hints.append(f"主事实表必须是 {table}（FROM/JOIN），不要换成其它渠道事实表。")
        if item.startswith("primary_facts="):
            tables = item.split("=", 1)[1]
            hints.append(f"问句涉及多渠道，需覆盖事实表：{tables}")
    return tuple(hints)
