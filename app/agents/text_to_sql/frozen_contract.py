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
    "warehouse_state": "warehouse.w_state",
    "call_center_state": "call_center.cc_state",
    "page_type": "web_page.wp_type",
    "promo_name": "promotion.p_promo_name",
    "carrier": "ship_mode.sm_carrier",
    "return_reason": "reason.r_reason_desc",
    "sales_year": "date_dim.d_year",
    "return_year": "date_dim.d_year",
    "CharterSchoolName": 'frpm."School Name"',
    "PercentFRPM": 'frpm."Percent (%) Eligible FRPM (K-12)"',
    "YearOpened": "STRFTIME('%Y', schools.OpenDate)",
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
        "只输出上述列，不要附加未列出的度量或金额列。",
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
        missing_core = sorted(
            name for name in core_tables if name.lower() not in referenced
        )
        if missing_core:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    f"冻结审计表必须全部 JOIN/FROM：{'、'.join(missing_core)}",
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
    elif core_tables:
        allowed = {name.lower() for name in core_tables}
        if "disp" not in allowed and "disp" in referenced:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    "冻结 core_tables 不含 disp，不要 JOIN disp 或过滤 disp.type",
                )
            )
        if "client" not in allowed and "client" in referenced:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    "冻结 core_tables 不含 client，不要 JOIN client",
                )
            )
        if "coe_charter_profile=true" in contract.filters:
            if re.search(
                r"Percent[\s\S]*?\*\s*100\s+AS\s+PercentFRPM|\*\s*100\s+AS\s+PercentFRPM",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PercentFRPM 使用 frpm 小数列，不要 ×100",
                    )
                )
            if re.search(
                r"cast\s*\(\s*strftime\s*\(\s*'%Y'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "YearOpened 用 STRFTIME('%Y', OpenDate) 文本，不要 CAST INTEGER",
                    )
                )
        slim_loan_path = allowed <= {"account", "loan", "trans"}
        if slim_loan_path and re.search(
            r"\b(?:loan|t\d+)\.status\b|\bstatus\s*=\s*['\"]C['\"]",
            sql,
            re.IGNORECASE,
        ):
            status_in_filters = any("status" in item.lower() for item in contract.filters)
            if not status_in_filters:
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "此题仅需 loan→account→trans，不要加 loan.status 过滤",
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
    elif described.projections:
        expected = {name.lower() for name in contract.projections}
        extra = [name for name in described.projections if name.lower() not in expected]
        if extra:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    f"不要额外输出列 {'、'.join(extra)}；冻结契约仅 "
                    f"{'、'.join(contract.projections)}（问句措辞冲突时以契约为准）",
                )
            )
    if not missing_aliases and "order_sensitive=true" in contract.filters and described.projections:
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
    skip_sk_cte = (
        "multi_channel_union=true" in contract.filters
        or "multi_returns_union=true" in contract.filters
        or "channel_pivot_compare=true" in contract.filters
    )
    cte_name = None if skip_sk_cte else _sk_heavy_cte_without_dimensions(
        described, contract.group_keys
    )
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
    lowered_sql = sql.lower()
    if "sales_amount" in contract.projections and "store_sales" in referenced:
        if re.search(
            r"sum\s*\(\s*[^)]*\bss_sales_price\b[^)]*\)\s*as\s*sales_amount",
            lowered_sql,
            re.IGNORECASE,
        ):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "store_sales 销售金额 SUM 必须用 ss_ext_sales_price AS sales_amount，"
                    "不要用 ss_sales_price",
                )
            )
    if "inventory_sold_qty=join_sold_cte" in contract.filters:
        if re.search(r"group\s+by[^;]*quantity_on_hand", lowered_sql, re.IGNORECASE):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "外层 GROUP BY 只用 warehouse_state、item_category、inventory_year；"
                    "quantity_on_hand/quantity_sold 仅 SUM 聚合",
                )
            )
        if "left join sold" in lowered_sql or "left join sold as" in lowered_sql:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "stock JOIN sold 用 INNER JOIN（按 item_sk），不要 LEFT JOIN",
                )
            )
    if (
        "returns_present=true" in contract.filters
        and "return_amount" in contract.projections
        and re.search(r"inc_tax|_tax\b", lowered_sql)
        and not re.search(
            r"cr_return_amount|wr_return_amt|sr_return_amt|cr_return_amount\b",
            lowered_sql,
        )
    ):
        findings.append(
            SemanticFinding(
                "projection_mismatch",
                "退货金额用 cr_return_amount / wr_return_amt / sr_return_amt 等列，"
                "不要用 *_return_amt_inc_tax 或其它含税列",
            )
        )
    if "channel_pivot_compare=true" in contract.filters:
        if "full outer join" in lowered_sql or (
            "left join" in lowered_sql and "coalesce" in lowered_sql
        ):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "渠道对比 CTE 用 INNER JOIN 对齐维度，"
                    "不要 FULL/LEFT OUTER JOIN 或 COALESCE 填 0",
                )
            )
        if "carrier" in {name.lower() for name in contract.projections}:
            if "sm_ship_mode_sk" in lowered_sql and "sm_carrier" not in lowered_sql:
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "carrier 维度用 ship_mode.sm_carrier，不要 GROUP BY sm_ship_mode_sk",
                    )
                )
        for segment in re.split(r"\bunion\b|(?=\bwith\b)", lowered_sql):
            if "web_sales" in segment and "warehouse" in segment and "catalog_sales" not in segment:
                findings.append(
                    SemanticFinding(
                        "missing_entity",
                        "渠道对比中 web_sales CTE 不要 JOIN warehouse（目录侧可按需 JOIN warehouse）",
                    )
                )
                break
    bill_ship = {"bill_state", "ship_state"} & {name.lower() for name in contract.projections}
    if bill_ship and "web_sales" in referenced and core_tables and "customer" in {
        name.lower() for name in core_tables
    }:
        if "c_current_addr_sk" in lowered_sql and not re.search(
            r"ws_bill_customer_sk\s*=\s*[^.]+\.c_customer_sk|c_customer_sk\s*=\s*[^.]+\.ws_bill_customer_sk",
            lowered_sql,
            re.IGNORECASE,
        ):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "web_sales 关联 customer 用 ws_bill_customer_sk = customer.c_customer_sk，"
                    "不要用 customer.c_current_addr_sk 对接账单地址",
                )
            )
        elif "customer" in referenced and "ws_bill_customer_sk" not in lowered_sql:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    "账单/收货地址过滤时仍需 JOIN customer ON ws_bill_customer_sk = c_customer_sk",
                )
            )
    demo_dims = {"marital_status", "education_status", "credit_rating"} & {
        name.lower() for name in contract.projections
    }
    if demo_dims and "store_sales" in referenced and "customer" in referenced:
        if re.search(r"\bss_cdemo_sk\b", lowered_sql) and "c_current_cdemo_sk" not in lowered_sql:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "store_sales 按教育/信用等汇总时应用 customer.c_current_cdemo_sk → "
                    "customer_demographics，不要仅用 ss_cdemo_sk",
                )
            )
    if demo_dims and "catalog_sales" in referenced and "customer" in referenced:
        if "cs_bill_cdemo_sk" in lowered_sql and "c_current_cdemo_sk" not in lowered_sql:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "catalog_sales 的顾客人口统计经 customer.c_current_cdemo_sk → customer_demographics，"
                    "不要仅用 cs_bill_cdemo_sk",
                )
            )
        if "cs_bill_hdemo_sk" in lowered_sql and "c_current_hdemo_sk" not in lowered_sql:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "收入带经 customer.c_current_hdemo_sk → household_demographics，"
                    "不要仅用 cs_bill_hdemo_sk",
                )
            )
    income_dims = {"income_lower", "buy_potential"} & {name.lower() for name in contract.projections}
    if income_dims and core_tables and "customer" in {name.lower() for name in core_tables}:
        if "ss_hdemo_sk" in lowered_sql and "c_current_hdemo_sk" not in lowered_sql:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "收入带/购买潜力应 JOIN customer 再用 customer.c_current_hdemo_sk "
                    "连接 household_demographics，不要仅用 store_sales.ss_hdemo_sk",
                )
            )
        if "store" in referenced and "store" not in {name.lower() for name in core_tables}:
            if "store_state" not in {name.lower() for name in contract.projections}:
                findings.append(
                    SemanticFinding(
                        "missing_entity",
                        "问句未要求门店州时不要 JOIN store；收入带/购买潜力走 customer→household_demographics",
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
            strict = "audit_tables_strict=true" in filters
            hints.append(f"必须 JOIN 或 FROM 这些表：{tables}")
            if strict:
                hints.append("不要 JOIN 上述清单以外的其它业务表。")
                if "promotion" not in {part.strip() for part in tables.split(",")}:
                    hints.append("清单不含 promotion 时不要额外 JOIN promotion。")
            else:
                hints.append(
                    "以上为问句审计提示；若投影或过滤还需其它维表/事实表，可一并 JOIN。"
                )
        if item == "order_sensitive=true":
            hints.append("问句要求排序，最终 SQL 需包含 ORDER BY。")
        if item.startswith("anchor_date="):
            day = item.split("=", 1)[1]
            hints.append(f"相对日期/校龄计算使用 anchor {day}，不要用 date('now') 或 julianday('now')。")
        if item == "coe_charter_profile=true":
            hints.append(
                "Fresno COE charter：frpm.`District Name` + `Charter School (Y/N)`=1；"
                "CharterSchoolName=frpm.`School Name`；PercentFRPM 用小数列（不×100）；"
                "FRPMCategory 严格 >0.75/>0.50；YearOpened 文本年。"
            )
        if item == "financial_running_ok_profile=true":
            hints.append(
                "running OK：COUNT(status) 分母；CTE percentage 不 ROUND；"
                "最终 ROUND(percentage_running_ok,2) 与 ROUND(avg_loan_amount,2)；avg_duration 不 ROUND。"
            )
        if item == "magnet_sat_profile=true":
            hints.append(
                "Magnet + SAT>500：satscores JOIN schools LEFT JOIN frpm；SchoolType=s.SOCType，"
                "EducationalOption=s.EdOpsName；FreeReducedMealPercentage=frpm Percent FRPM 小数；"
                "PovertyLevel 用 >0.75/>0.50/>0.25 与 High/Moderate/Low/Very Low Poverty；"
                "PerformanceCategory 用 Excellent/Good/Average/Below Average（1800/1500/1200）；"
                "CountyRank 用 DENSE_RANK；外层 WHERE Magnet=1。"
            )
        if item == "top_reading_sat_profile=true":
            hints.append(
                "最高 Reading：satscores 上 RANK()，WHERE ReadingRank=1（勿仅用 ORDER BY LIMIT 1）；"
                "frpm 用 Ages 5-17 列；PercentScoring1500Plus=NumGE1500*100/NumTstTakr；"
                "GradeSpan=GSoffered；Charter 标签 Charter/Non-Charter School。"
            )
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
        if item == "cross_channel_buyers=customer_and_item":
            hints.append(
                "跨渠道顾客：web_sales 侧 CTE 取 (customer_sk, item_sk)，"
                "JOIN store_sales 同一 customer+item 后只 SUM 门店 ss_ext_sales_price。"
            )
        if item == "channel_pivot_compare=true":
            hints.append(
                "渠道对比：各渠道独立 CTE 汇总，INNER JOIN 对齐维度后输出 *_sales_amount 多列；"
                "目录侧可按 Gold 需要 JOIN warehouse，网站侧通常不必 JOIN warehouse。"
            )
        if item == "multi_returns_union=true":
            hints.append(
                "多退货事实：store_returns 与 catalog_returns 等分 CTE UNION ALL 后再按 reason/category 汇总。"
            )
        if item == "birth_year_not_null=true":
            hints.append("出生年份维度需 customer.c_birth_year IS NOT NULL。")
        if item == "inventory_sold_qty=join_sold_cte":
            hints.append(
                "库存+门店销量：sold CTE 按 ss_item_sk 汇总 ss_quantity，"
                "stock CTE 按 warehouse/category/item_sk 汇总 inv_quantity_on_hand，"
                "再 JOIN sold ON item_sk 后外层 SUM quantity_on_hand 与 quantity_sold。"
            )
        if item == "return_linked_sales=item_store_year":
            hints.append(
                "同年同店退货过滤：returned_items CTE 按 (sr_item_sk, sr_store_sk, d_year) 去重，"
                "JOIN store_sales 用 item_sk+store_sk+sales_year，不要用 ticket_number 代替。"
            )
        if item == "returns_present=true":
            hints.append(
                "退货金额用事实表 cr_return_amount / wr_return_amt / sr_return_amt 等 *_return_amount 列，"
                "不要用 *_return_amt_inc_tax 或其它含税列代替。"
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
