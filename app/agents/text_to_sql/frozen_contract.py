"""冻结语义契约进入 Generic Prompt。不是 Gold SQL，与 cases.yaml 一并发布。"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.evaluation.sql_shape import PredictionShape, describe_sql
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
_ALIAS = re.compile(
    r'\bAS\s+(?:"([^"]+)"|([A-Za-z_][A-Za-z0-9_]*))',
    re.IGNORECASE,
)


def format_frozen_semantic_contract(contract: SemanticContract) -> str:
    lines = [
        "冻结语义契约（与问句一并发布，不含 Gold SQL）：",
        f"最终 SELECT 列名（AS 别名）应覆盖：{'、'.join(contract.projections)}",
    ]
    if contract.group_keys:
        lines.append(f"GROUP BY 键：{'、'.join(contract.group_keys)}")
        lines.append(
            "投影列顺序建议与 GROUP BY 键一致"
            + ("，并写 ORDER BY。" if "order_sensitive=true" in contract.filters else "。")
        )
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
    core_tables = _core_tables(contract.filters)
    if core_tables and "audit_tables_strict=true" in contract.filters:
        audited = {name.lower() for name in core_tables}
        extra = sorted(name for name in referenced if name.lower() not in audited)
        if extra:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    f"只能使用冻结审计表（{'、'.join(core_tables)}），请移除：{'、'.join(extra)}",
                )
            )
    elif (
        core_tables
        and "promotion" not in core_tables
        and "promotion_channel=dmail" not in contract.filters
        and "promotion" in referenced
    ):
        findings.append(
            SemanticFinding(
                "missing_entity",
                "冻结审计表清单不含 promotion，问句未要求促销时不要 JOIN promotion",
            )
        )
    for table in _tables_for_projections(contract.projections):
        if table.lower() not in referenced:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    f"冻结契约投影需要表 {table} 出现在 SQL 中",
                )
            )
    aliases = {name.lower() for name in _select_aliases(sql)}
    projected_blob = " ".join(described.projections).lower()
    missing_aliases = [
        name
        for name in contract.projections
        if name.lower() not in aliases and name.lower() not in projected_blob
    ]
    if missing_aliases:
        shown = "、".join(missing_aliases[:12])
        suffix = "…" if len(missing_aliases) > 12 else ""
        findings.append(
            SemanticFinding(
                "projection_mismatch",
                f"冻结契约要求输出列 {shown}{suffix}，请用 AS 别名逐列投影（SQLite 含空格时用双引号）",
            )
        )
    elif "order_sensitive=true" in contract.filters and described.projections:
        alias_order = [name.lower() for name in described.projections]
        expected = [name.lower() for name in contract.projections]
        if alias_order != expected:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    f"输出列顺序应为 {'、'.join(contract.projections)}，"
                    f"当前为 {'、'.join(described.projections)}",
                )
            )
    for name in contract.projections:
        column = _PROJECTION_COLUMNS.get(name)
        if column is None:
            continue
        base = column.split(".")[-1].lower()
        lowered = sql.lower()
        if base not in lowered and name.lower() not in lowered:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    f"列 {name} 应使用 {column}，不要用其它 surrogate 列代替",
                )
            )
        if name == "item_category" and "i_category_id" in lowered and "i_category" not in lowered:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "item_category 应使用 item.i_category，不要用 i_category_id",
                )
            )
    primary = _primary_fact(contract.filters)
    if primary is not None:
        wrong = _wrong_channel_facts(primary, referenced)
        if primary.lower() in referenced:
            if wrong:
                findings.append(
                    SemanticFinding(
                        "missing_entity",
                        f"问句渠道对应 {primary}，不要同时使用 {wrong} 等其它渠道事实表",
                    )
                )
        elif wrong:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    f"问句渠道对应 {primary}，不要改用 {wrong} 等其它渠道事实表",
                )
            )
        else:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    f"冻结契约要求主事实表 {primary} 出现在 SQL 中",
                )
            )
    if contract.group_keys and described.aggregations:
        outer = next((scope for scope in described.scopes if scope.name == "outer"), None)
        group_by = outer.group_by if outer is not None else described.group_by
        grouped = " ".join(group_by).lower()
        proj_norm = {_normalize_label(name) for name in described.projections}
        for key in contract.group_keys:
            kn = _normalize_label(key)
            if kn in proj_norm and any(kn == _normalize_label(g) for g in group_by):
                continue
            if key.lower() in grouped or kn in grouped.replace("_", ""):
                continue
            if key.lower() not in aliases:
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        f"聚合查询外层 GROUP BY 需包含维度 {key}（可与 AS 别名一致）",
                    )
                )
    if _window_and_group_by_same_select(sql, dialect=dialect):
        findings.append(
            SemanticFinding(
                "projection_mismatch",
                "窗口函数（RANK 等）与 GROUP BY 不要写在同一 SELECT 层；用 CTE 先算基础列，外层再 RANK/ORDER BY",
            )
        )
    if "inventory_sold_items=subquery" in contract.filters and "store" in referenced:
        audited = {name.lower() for name in core_tables} if core_tables else set()
        if "store" not in audited:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    "门店卖过过滤用 store_sales 子查询即可，不要 JOIN store 表",
                )
            )
    if "promotion_via_item_sk_subquery=true" in contract.filters:
        lowered = sql.lower()
        if re.search(r"\bjoin\s+promotion\b", lowered) or (
            " ss_promo_sk" in lowered and "p_channel_dmail" in lowered
        ):
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    "直邮促销商品用 store_sales.ss_item_sk IN (SELECT p_item_sk FROM promotion "
                    "WHERE p_channel_dmail='Y' AND p_item_sk IS NOT NULL)，不要 JOIN promotion 事实行",
                )
            )
        elif "ss_item_sk" in lowered and "in (select" not in lowered and "in(select" not in lowered.replace(" ", ""):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "直邮促销过滤需 ss_item_sk IN (SELECT p_item_sk FROM promotion WHERE p_channel_dmail='Y')",
                )
            )
    cte_name = _sk_heavy_cte_without_dimensions(described, contract.group_keys)
    if cte_name is not None:
        keys = "、".join(contract.group_keys[:6])
        findings.append(
            SemanticFinding(
                "projection_mismatch",
                f"CTE {cte_name} 不要仅按多个 *_sk 预聚合；外层应按维度 {keys} 汇总",
            )
        )
    if "multi_channel_union=true" in contract.filters:
        sales = [name for name in core_tables if name.endswith("_sales")]
        if len(sales) >= 2:
            hits = sum(1 for name in sales if name.lower() in referenced)
            if hits >= 2 and "union" not in sql.lower():
                findings.append(
                    SemanticFinding(
                        "missing_entity",
                        f"多渠道请用 UNION ALL 分渠道汇总（{'、'.join(sales)}），不要在同一 SELECT 中同时 JOIN 多个渠道事实表",
                    )
                )
    return tuple(findings)


def _normalize_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _group_label_token(expression: str) -> str:
    normalized = expression.replace('"', " ").replace("`", " ")
    parts = re.findall(r"[a-z_][a-z0-9_]*", normalized.lower())
    return parts[-1] if parts else normalized.strip()


def _sk_heavy_cte_without_dimensions(
    described: PredictionShape,
    group_keys: Sequence[str],
) -> str | None:
    if not group_keys or not described.scopes:
        return None
    dim_keys = {_normalize_label(key) for key in group_keys}
    for scope in described.scopes:
        if scope.name == "outer" or not scope.aggregations:
            continue
        sk_groups = sum(1 for item in scope.group_by if "_sk" in item.lower())
        if sk_groups < 2 or len(scope.group_by) < 3:
            continue
        group_norm = {_normalize_label(_group_label_token(item)) for item in scope.group_by}
        if not dim_keys & group_norm:
            return scope.name
    return None


def _window_and_group_by_same_select(sql: str, *, dialect: str) -> bool:
    try:
        parsed = sqlglot.parse_one(sql, read=dialect)
    except SqlglotError:
        return False
    if parsed is None:
        return False
    for select in parsed.find_all(exp.Select):
        if not select.args.get("group"):
            continue
        for expression in select.expressions:
            if expression.find(exp.Window) is not None:
                return True
    return False


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
    names: list[str] = []
    for quoted, plain in _ALIAS.findall(sql):
        name = quoted or plain
        if name:
            names.append(name)
    return tuple(dict.fromkeys(names))


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
        if item == "inventory_sold_items=subquery":
            hints.append(
                "只保留门店卖过的商品：inventory.inv_item_sk IN (SELECT ss_item_sk FROM store_sales "
                "JOIN date_dim ON … WHERE d_year=2001) 或等价 CTE；不必 JOIN store 维表。"
            )
        if item == "promotion_via_item_sk_subquery=true":
            hints.append(
                "直邮促销过滤使用 ss_item_sk IN (SELECT p_item_sk FROM promotion WHERE p_channel_dmail='Y')，"
                "不要 JOIN promotion 到 store_sales。"
            )
        if item.startswith("primary_fact="):
            table = item.split("=", 1)[1]
            hints.append(f"主事实表必须是 {table}（FROM/JOIN），不要换成其它渠道事实表。")
        if item.startswith("primary_facts="):
            tables = item.split("=", 1)[1]
            hints.append(f"问句涉及多渠道，需覆盖事实表：{tables}")
        if item.startswith("core_tables="):
            tables = item.split("=", 1)[1]
            hints.append(f"必须 JOIN 或 FROM 这些表：{tables}")
            hints.append("不要 JOIN 上述清单以外的其它业务表。")
            if "promotion" not in {part.strip() for part in tables.split(",")}:
                hints.append("清单不含 promotion 时不要额外 JOIN promotion。")
        if item == "order_sensitive=true":
            hints.append("问句要求排序，最终 SQL 需包含 ORDER BY。")
        if item.startswith("anchor_date="):
            day = item.split("=", 1)[1]
            hints.append(f"相对日期/校龄计算使用 anchor {day}，不要用 date('now') 或 julianday('now')。")
        if item == "returns_vs_sales=separate_cte":
            hints.append(
                "退货与销售需分 CTE 按各自事实表+date_dim 过滤后再 JOIN，"
                "不要仅用 item/store 键硬拼 promotion 或跨事实笛卡尔积。"
            )
        if item == "multi_channel_union=true":
            hints.append(
                "多渠道销售须分渠道 CTE（各事实表+date_dim 过滤年份）用 UNION ALL 合并，"
                "再 JOIN item 按 channel/item_category/sales_year 汇总；不要单条 SQL 同时 JOIN 多个 *_sales。"
            )
    return tuple(hints)


def _wrong_channel_facts(primary: str, referenced: set[str]) -> str | None:
    if not primary.endswith("_sales") and not primary.endswith("_returns"):
        return None
    prefix = primary.split("_", 1)[0]
    for name in referenced:
        if name == primary.lower():
            continue
        if (name.endswith("_sales") or name.endswith("_returns")) and not name.startswith(prefix):
            return name
    return None


def _core_tables(filters: Sequence[str]) -> tuple[str, ...]:
    for item in filters:
        if item.startswith("core_tables="):
            return tuple(part.strip() for part in item.split("=", 1)[1].split(",") if part.strip())
    return ()
