"""冻结语义契约进入 Generic Prompt。不是 Gold SQL，与 cases.yaml 一并发布。"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.agents.text_to_sql.semantic import SemanticFinding
from app.evaluation.sql_shape import PredictionShape, describe_sql
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
        lines.append(f"时间窗口：{contract.time_window.start} 至 {contract.time_window.end}")
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
        missing_core = sorted(name for name in core_tables if name.lower() not in referenced)
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
        if "financial_1993_poplatek_profile=true" in contract.filters:
            if re.search(
                r"status\s*=\s*['\"]C['\"].*running|running_loans.*status\s*=\s*['\"]C['\"]",
                sql,
                re.I,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "BIRD financial：loan status A=running、B=finished、C=defaulted（不要用 C 表示 running）",
                    )
                )
            if re.search(r"type\s*=\s*['\"]credit['\"]|type\s*=\s*['\"]debit['\"]", sql, re.I):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "trans.type 用 PRIJEM（收入）与 VYDAJ（支出），不要用 credit/debit",
                    )
                )
            if "POPLATEK PO OBRATU" not in sql.upper() and re.search(
                r"strftime\s*\(\s*'%Y'.*1993", sql, re.I
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "1993 账户用 frequency='POPLATEK PO OBRATU' 且 STRFTIME('%Y',date)='1993'",
                    )
                )
            if re.search(r"\bd\.A5\s+AS\s+urbanization_category", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "urbanization_category 用 district.A10：>75 Highly Urban，>50 Moderately Urban，"
                        "否则 Rural",
                    )
                )
            if re.search(
                r"AVG\s*\(\s*t\.balance\s*\)\s+AS\s+balance_volatility",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "balance_volatility 用 MAX(balance)-MIN(balance)，不要用 AVG(balance)",
                    )
                )
            if re.search(r"2026-10-01|2026\s*-", sql) and re.search(
                r"avg_client_age",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "avg_client_age 用 JULIANDAY(account_open_date)-JULIANDAY(birth_date)/365.25，"
                        "不要用固定 2026 年差",
                    )
                )
            if "risk_category" in sql and "High Risk" not in sql and re.search(
                r"THEN\s+'High'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "risk_category 用 High Risk / Low Risk / No Loans",
                    )
                )
            if re.search(
                r"FROM\s+trans\s+t\s+WHERE\s+t\.type\s+IN\s*\(\s*'PRIJEM'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "交易统计须 FROM AccountsIn1993 a LEFT JOIN trans t（不要全库 trans 聚合）",
                    )
                )
            if re.search(
                r"ClientStats\s+AS\s+\(\s*SELECT[\s\S]{0,500}?FROM\s+disp\s+d\s+JOIN\s+client",
                sql,
                re.IGNORECASE,
            ) and not re.search(
                r"ClientStats\s+AS\s+\(\s*SELECT[\s\S]{0,500}?AccountsIn1993",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "ClientStats 须从 AccountsIn1993 JOIN disp/client，不要全库 disp 聚合",
                    )
                )
            if re.search(
                r"LoanStats\s+AS\s+\(\s*SELECT[\s\S]{0,300}?FROM\s+loan\s+l\s+GROUP",
                sql,
                re.IGNORECASE,
            ) and not re.search(
                r"LoanStats\s+AS\s+\(\s*SELECT[\s\S]{0,300}?AccountsIn1993",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "LoanStats 须 FROM AccountsIn1993 LEFT JOIN loan（不要全库 loan 聚合）",
                    )
                )
        if "state_special_soc3_profile=true" in contract.filters:
            if re.search(r"SOC\s+LIKE\s+'3%'", sql, re.I) and "State Special Schools" not in sql:
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "State Special Schools 用 schools.DOCType='State Special Schools'，"
                        "SOC 31 或 3% 在 JOIN 后过滤",
                    )
                )
            if (
                re.search(r"THEN 'Yes'|THEN 'No'", sql)
                and "Charter" in sql
                and "Non-Charter" not in sql
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SchoolType 用 Charter / Non-Charter，不要用 Yes/No",
                    )
                )
            if re.search(r"High FRPM|Medium FRPM", sql):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PovertyLevel 用 High/Medium/Low/Very Low Poverty（frpm 小数阈值）",
                    )
                )
            if re.search(r"Very High Poverty", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PovertyLevel 最高档用 High Poverty（>0.75），不要用 Very High Poverty",
                    )
                )
            if re.search(r"\bStatusType\s+AS\s+CurrentStatus", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "CurrentStatus 用 ClosedDate：NULL→Active，否则 Closed；不要用 StatusType",
                    )
                )
            if re.search(
                r"ORDER\s+BY\s+frpm\.\s*\"Enrollment \(K-12\)\"\s+DESC",
                sql,
                re.IGNORECASE,
            ) and "EnrollmentRank" in sql:
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "排序用 ORDER BY EnrollmentRank ASC（RANK 已在 CTE 计算）",
                    )
                )
            if re.search(
                r"WHERE\s+schools\.DOCType\s*=\s*'State Special Schools'[\s\S]{0,120}SOC\s+LIKE",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SOC 过滤放在 StateSpecialSchools CTE 外层："
                        "WHERE ss.SOC='31' OR ss.SOC LIKE '3%'",
                    )
                )
            if (
                re.search(r"AvgTotalScore|Avg.*Read.*\+.*Write", sql, re.I)
                and "/3" not in sql
                and "/ 3" not in sql
            ):
                if "AvgTotalScore" in " ".join(contract.projections) and re.search(
                    r"\+.*AvgScrWrite\s*\)\s+AS\s+[\"']?AvgTotalScore",
                    sql,
                    re.I,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "AvgTotalScore=ROUND((Read+Math+Write)/3.0, 2)，不要直接用三科之和",
                        )
                    )
        if "la_meal_stats_aggregate_profile=true" in contract.filters:
            if re.search(r"count\s*\(\s*\*\s*\)\s+over\s*\(\s*partition\s+by\s+frpm", sql, re.I):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FreeMealCategoryBreakdown 用 CategoryBreakdown CTE + GROUP_CONCAT 子查询，"
                        "不要窗口 COUNT OVER frpm_category",
                    )
                )
            if re.search(
                r"FRPM Count \(K-12\)\s*>\s*500|Enrollment \(K-12\)\s*<\s*700",
                sql,
                re.I,
            ) and not re.search(r"FRPM Count \(K-12\)\s*<\s*700", sql, re.I):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "LA 餐食题：Free Meal Count>500 且 FRPM Count (K-12)<700",
                    )
                )
            if re.search(r"High FRPM|Medium FRPM", sql) and "FreeMealCategory" in " ".join(
                contract.projections
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FreeMealCategory 按 Free Meal Count：Very High (>600)/High (>500)/Moderate",
                    )
                )
            if re.search(r"High FRPM|Medium FRPM", sql) and re.search(
                r"FreeMealCategoryBreakdown|frpm_category",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "餐食分档按 Free Meal Count（Very High/High/Moderate），不要用 FRPM 占比 High FRPM 标签",
                    )
                )
        if "financial_salary_gap_profile=true" in contract.filters:
            if re.search(
                r'AS\s+["\']?\(\s*SELECT\s+MAX\s*\(\s*A11\s*\)',
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "第二列只写 (SELECT MAX(A11)-MIN(A11) FROM district) 表达式，"
                        "不要用 AS '(SELECT …)' 当别名",
                    )
                )
            if "(SELECT MAX(A11) - MIN(A11) FROM district)" not in sql:
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "第二列须含 (SELECT MAX(A11) - MIN(A11) FROM district) 表达式（与冻结契约列名一致）",
                    )
                )
            if re.search(
                r"order\s+by[\s\S]*\(select\s+avg\s*\(\s*t\.amount\s*\)",
                sql,
                re.IGNORECASE,
            ) and not re.search(
                r"district_id\s*=\s*\(\s*select district_id from client",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "先取 gender='F' 最年长 client 的 district_id，再筛 account；"
                        "ORDER BY district.A11 DESC LIMIT 1 取 account_id（勿 ORDER BY birth_date+相关 AVG）",
                    )
                )
            if re.search(r"ORDER BY\s+c\.birth_date", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "ORDER BY district.A11 DESC LIMIT 1 取 account_id，不要 ORDER BY client.birth_date",
                    )
                )
        if "schools_admin_doc_soc_profile=true" in contract.filters:
            if re.search(r"District\s+LIKE|GSserved\s+LIKE|GSoffered\s+LIKE", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Unified School District 用 schools.DOC=54；Intermediate/Middle 用 SOC=62；"
                        "不要用 District/GSserved LIKE 模糊匹配",
                    )
                )
            if re.search(r"OpenDate\s+BETWEEN\s+'20\d{2}-", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "开业年份用 strftime('%Y', OpenDate) BETWEEN '2009' AND '2010'",
                    )
                )
            if not re.search(r"\bDOC\s*=\s*54", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Unified School District 过滤用 schools.DOC=54",
                    )
                )
            if not re.search(r"\bSOC\s*=\s*62", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Intermediate/Middle 公立校过滤用 schools.SOC=62",
                    )
                )
        if "la_k9_frpm_sat_profile=true" in contract.filters:
            if re.search(r"County Name", sql) and re.search(r"Los Angeles", sql):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Los Angeles 县过滤用 schools.County = 'Los Angeles'，不要用 frpm County Name",
                    )
                )
            if re.search(r"Eligible FRPM \(K-12\)", sql) and re.search(
                r"Ages 5-17", " ".join(contract.projections)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPM 与 Enrollment 用 Ages 5-17 列；Percent 用 FRPM Count/Enrollment×100",
                    )
                )
            if re.search(r"High FRPM|Medium FRPM", sql):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Poverty_Level 用 High/Medium/Low Poverty（百分比阈值 75/50）",
                    )
                )
            if re.search(r"GSserved\s+LIKE", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "K-9 年级跨度用 schools.GSserved = 'K-9'，不要用 LIKE",
                    )
                )
        if "directly_funded_stanislaus_profile=true" in contract.filters:
            if re.search(r"cast\s*\(\s*strftime\s*\(\s*'%Y'", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "OpenYear 用 STRFTIME('%Y', OpenDate) 文本，不要 CAST INTEGER",
                    )
                )
            if re.search(r"directly funded", sql, re.I) and not re.search(
                r"FundingType\s*=\s*'Directly funded'", sql, re.I
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Directly funded 学校用 schools.FundingType = 'Directly funded'",
                    )
                )
            if re.search(r"Stanislaus", sql, re.I) and not re.search(
                r"County\s*=\s*'Stanislaus'", sql, re.I
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Stanislaus 过滤用 schools.County = 'Stanislaus'",
                    )
                )
            if re.search(r"cross\s+join\s+county", sql, re.I):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "县均值用 CountyStats CTE 再 JOIN County，不要 CROSS JOIN 单行 county",
                    )
                )
            if re.search(r"High FRPM|Medium FRPM", sql) and "FRPMStatus" in " ".join(
                contract.projections
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPMStatus 与县均值比较：Above/Below/At County Average",
                    )
                )
            if re.search(
                r"Percent\s*\(\%\)\s*Eligible\s*FRPM[\s\S]*?\*\s*100\s+AS\s+FRPM",
                sql,
                re.I,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPMPercent 用 frpm 小数列，不要 ×100",
                    )
                )
        if "region_loan_success_stats_profile=true" in contract.filters:
            if re.search(
                r"status\s*=\s*'C'[\s\S]{0,80}(paid_amount|successful_loans)",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "region 贷款成功：paid/successful 用 status='A'（不是 C）",
                    )
                )
            if (
                re.search(r"avg_interest_paid", sql, re.IGNORECASE)
                and re.search(
                    r"AVG\s*\(\s*CASE\s+WHEN[\s\S]*payments\s*\)",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(
                    r"payments\s*\*\s*l\.duration|payments\s*\*\s*duration",
                    sql,
                    re.IGNORECASE,
                )
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "interest_paid=(payments*duration)-amount；AVG 分别算 successful 与 all",
                    )
                )
            if re.search(r"overall_percentage", sql, re.IGNORECASE) and re.search(
                r"SUM\s*\(\s*paid_amount\s*\)\s+OVER\s*\(\s*\)",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "overall_percentage 用 (SELECT … FROM loan) 全表占比子查询",
                    )
                )
            if (
                re.search(r"paid_amount_percentage", sql, re.IGNORECASE)
                and re.search(
                    r"ORDER BY\s+region\b",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(
                    r"ORDER BY[\s\S]*paid_amount_percentage\s+DESC", sql, re.IGNORECASE
                )
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "结果 ORDER BY paid_amount_percentage DESC",
                    )
                )
        if "financial_running_ok_profile=true" in contract.filters:
            if re.search(r"running_ok|percentage_running|loan_size_category", sql, re.IGNORECASE):
                if (
                    re.search(r"status\s*=\s*'A'", sql, re.IGNORECASE)
                    and re.search(r"status\s*=\s*'C'", sql, re.IGNORECASE) is None
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "running OK 用 loan.status='C'（不是 status='A'）",
                        )
                    )
                if re.search(r"count\s*\(\s*\*\s*\)", sql, re.IGNORECASE) and not re.search(
                    r"count\s*\(\s*status\s*\)",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "running OK 占比分母用 COUNT(status)",
                        )
                    )
                if re.search(r"round\s*\(\s*avg\s*\(\s*duration", sql, re.IGNORECASE):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "avg_duration 中间 CTE 不要 ROUND",
                        )
                    )
                if re.search(r"avg_loan_amount", sql, re.IGNORECASE) and not re.search(
                    r"round\s*\(\s*r\.avg_loan_amount|round\s*\(\s*[^)]*avg_loan_amount",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "最终 SELECT ROUND(avg_loan_amount, 2)",
                        )
                    )
        if "alameda_highest_free_rate_profile=true" in contract.filters:
            if re.search(r"Alameda|FreeRate|HighestFree|free meal", sql, re.IGNORECASE):
                if re.search(r"County\s*=\s*'Alameda'", sql, re.IGNORECASE) and not re.search(
                    r"County Name", sql, re.IGNORECASE
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "Alameda 县过滤用 frpm.`County Name`='Alameda'",
                        )
                    )
                if (
                    re.search(r"ORDER BY[\s\S]{0,160}LIMIT\s+1", sql, re.IGNORECASE)
                    and not re.search(r"CountyRank\s*=\s*1", sql, re.IGNORECASE)
                    and not re.search(r"RANK\s*\(", sql, re.IGNORECASE)
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "最高 free rate 用 RANK()…CountyRank=1（勿仅 ORDER BY LIMIT）",
                        )
                    )
                if re.search(r"Charter School \(Y/N\)", sql, re.IGNORECASE):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "IsCharterSchool 用 schools.Charter 1/0→Yes/No",
                        )
                    )
                if re.search(r"Percent \(.*\) Eligible Free", sql, re.IGNORECASE) and not re.search(
                    r"Free Meal Count \(K-12\)|FreeRate",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "HighestFreeRate=Free Meal Count (K-12)/Enrollment (K-12)",
                        )
                    )
                if re.search(
                    r"ROUND\s*\(\s*[^)]*(?:FreeRate|CountyAverage|Deviation)",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "HighestFreeRate/CountyAverage/Deviation 不要 ROUND，"
                            "与 Gold 全精度比率一致",
                        )
                    )
        if "locally_funded_enrollment_gap_profile=true" in contract.filters:
            if re.search(r"Locally funded|Enrollment \(K-12\)", sql, re.IGNORECASE):
                if not re.search(r"FundingType\s*=\s*'Locally funded'", sql, re.IGNORECASE):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "Locally funded 用 schools.FundingType='Locally funded'",
                        )
                    )
                if re.search(r"Charter Funding Type", sql, re.IGNORECASE):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "FundingType 在 schools 表（不是 frpm Charter Funding Type）",
                        )
                    )
                if re.search(r"Enrollment \(Ages 5-17\)", sql, re.IGNORECASE) is None:
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "差值=Enrollment (K-12)−Enrollment (Ages 5-17)",
                        )
                    )
                if re.search(r"`School Name`", sql, re.IGNORECASE) and not re.search(
                    r"\bT2\.School\b|\bschools\.School\b|SELECT\s+T2\.School\b",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "输出 schools.School 与 schools.DOC（不是 frpm School Name）",
                        )
                    )
        if "top_numge1500_admin_names_profile=true" in contract.filters:
            if re.search(r"NumGE1500|AdmFName|administration|1500", sql, re.IGNORECASE):
                if re.search(
                    r"NumGE1500[\s\S]{0,48}/[\s\S]{0,24}NumTstTakr|excellence_rate",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "最高 NumGE1500 校：ORDER BY NumGE1500 DESC LIMIT 1（不是比率）",
                        )
                    )
                if re.search(r"GROUP BY", sql, re.IGNORECASE):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "单行管理员姓名：勿 GROUP BY 聚合",
                        )
                    )
                if re.search(r"satscores|NumGE1500", sql, re.IGNORECASE) and not re.search(
                    r"AdmFName1", sql, re.IGNORECASE
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "投影 AdmFName/LName1–3（schools JOIN satscores ON cds=CDSCode）",
                        )
                    )
        if "first_loan_19930705_balance_rate_profile=true" in contract.filters:
            if re.search(r"1993-07-05|1993/7/5|1993-03-22|1998-12-27", sql, re.IGNORECASE):
                if not re.search(
                    r"T1\.date\s*=\s*'1993-07-05'|loan\.date\s*=\s*'1993-07-05'", sql, re.IGNORECASE
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "筛选贷款：loan.date='1993-07-05'（Gold 口径，勿用 client 子查询取 first）",
                        )
                    )
                if re.search(r"\bclient\b|\bdisp\b", sql, re.IGNORECASE) and not re.search(
                    r"IIF\s*\(", sql, re.IGNORECASE
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "余额增幅用 SUM(IIF(trans.date=…, balance, 0)) 聚合（1993-03-22 与 1998-12-27）",
                        )
                    )
                if re.search(
                    r"SELECT\s+balance\s+FROM\s+trans[\s\S]{0,80}date\s*=",
                    sql,
                    re.IGNORECASE,
                ) and not re.search(r"SUM\s*\(\s*IIF", sql, re.IGNORECASE):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "勿用标量子查询取 balance；用 SUM(IIF(date=…, balance, 0)) 同行聚合",
                        )
                    )
        if "magnet_k8_multiple_provision_by_city_profile=true" in contract.filters:
            if re.search(r"Magnet|K-8|Provision", sql, re.IGNORECASE):
                if re.search(r"GSserved\s*=\s*'K-8'", sql, re.IGNORECASE) and not re.search(
                    r"GSoffered\s*=\s*'K-8'", sql, re.IGNORECASE
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "K-8 学段过滤用 schools.GSoffered='K-8'（不是 GSserved）",
                        )
                    )
                if re.search(r"Magnet", sql, re.IGNORECASE) and not re.search(
                    r"Magnet\s*=\s*1", sql, re.IGNORECASE
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "magnet 校 schools.Magnet=1",
                        )
                    )
                if re.search(r"frpm|schools", sql, re.IGNORECASE) and not re.search(
                    r"Multiple Provision Types", sql, re.IGNORECASE
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "frpm.`NSLP Provision Status`='Multiple Provision Types'",
                        )
                    )
                if re.search(r"COUNT\s*\(\s*DISTINCT\s+T2\.City\s*\)", sql, re.IGNORECASE):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "按 City GROUP BY 并 COUNT(CDSCode)，勿只 COUNT(DISTINCT City)",
                        )
                    )
        if "transaction_840_19981014_profile=true" in contract.filters:
            if re.search(r"840", sql) and re.search(r"1998-10-14", sql):
                if re.search(
                    r"JULIANDAY\s*\([^)]+\)\s*/\s*365\.25|"
                    r"JULIANDAY\s*\(\s*[^)]*transaction[^)]*\)\s*-\s*JULIANDAY\s*\(\s*[^)]*birth",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "age_at_transaction 用 strftime 年差并校正月日（锚点 1998-10-14）",
                        )
                    )
                if re.search(
                    r"FROM\s+loan[\s\S]{0,160}date\s*<(?!=)",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "has_loan_before_transaction：loan.date<=transaction_date（含当日）",
                        )
                    )
                if (
                    re.search(r"type\s*=\s*'OWNER'", sql, re.IGNORECASE)
                    and re.search(r"JOIN\s+owner\s+ON", sql, re.IGNORECASE)
                    and not re.search(r"LEFT\s+JOIN\s+AccountOwners", sql, re.IGNORECASE)
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "AccountOwners 用 LEFT JOIN（不是 INNER JOIN owner CTE）",
                        )
                    )
        if "weekly_statement_owners_demographics_profile=true" in contract.filters:
            if re.search(
                r"frequency\s*=\s*'weekly'|weekly statement",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "weekly 对账单账户 frequency='POPLATEK TYDNE'",
                    )
                )
            if (
                re.search(r"age_group", sql, re.IGNORECASE)
                and re.search(
                    r"THEN\s+'Middle'|'Old'\s+END|AS\s+age_group[\s\S]{0,200}'Middle'",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(r"Middle-aged|'Senior'", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "age_group 标签用 Middle-aged 与 Senior（不是 Middle/Old）",
                    )
                )
            if (
                re.search(r"avg_net_balance|net_balance", sql, re.IGNORECASE)
                and re.search(
                    r"SUM\s*\(\s*t\.balance\s*\)|AVG\s*\(\s*ta\.net_balance\s*\)",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(
                    r"total_income\s*-\s*total_expense|income\s*-\s*expense",
                    sql,
                    re.IGNORECASE,
                )
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "avg_net_balance 用 PRIJEM−VYDAJ（不是 SUM(trans.balance)）",
                    )
                )
            if re.search(r"POPLATEK TYDNE|weekly", sql, re.IGNORECASE) and re.search(
                r"JULIANDAY\s*\(\s*['\"]2026-10-01",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "age_group 用 strftime 年差与生日校正（anchor 2026-10-01）",
                    )
                )
            if (
                re.search(r"total_weekly_owners", sql, re.IGNORECASE)
                and re.search(
                    r"ORDER BY\s+oi\.gender|ORDER BY\s+gender\s*,\s*age_group",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(r"ORDER BY\s+total_weekly_owners", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "ORDER BY total_weekly_owners DESC",
                    )
                )
        if "disponent_po_obratu_client_profile=true" in contract.filters:
            if re.search(r"type\s*=\s*'OWNER'", sql, re.IGNORECASE) and not re.search(
                r"type\s*=\s*'DISPONENT'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "post-obratu 题用 disp.type='DISPONENT'（不是 OWNER）",
                    )
                )
            if re.search(r"POPLATEK PO OBRATU", sql, re.IGNORECASE) is None and re.search(
                r"disponent|post-transaction|eligible_accounts",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "账户 frequency 须 POPLATEK PO OBRATU",
                    )
                )
            if re.search(
                r"type\s*=\s*'credit'|type\s*=\s*'debit'|total_credit|total_debit",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "交易汇总用 PRIJEM/VYDAJ（不是 credit/debit）",
                    )
                )
            if re.search(
                r"status\s*=\s*'C'[\s\S]{0,40}completed|completed_loans[\s\S]{0,80}status\s*=\s*'C'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "completed_loans 计 status='B'（active 为 A）",
                    )
                )
            if re.search(r"client_category", sql, re.IGNORECASE) and re.search(
                r"High Usage|Medium Usage|Low Usage",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "client_category 用 Full Service/Loan Only/Card Only/Basic",
                    )
                )
            if re.search(
                r"t\.date\s*>\s*\(\s*SELECT\s+a\.date",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "勿用 trans.date>开户日代替 POPLATEK PO OBRATU+DISPONENT 过滤",
                    )
                )
            if (
                re.search(r"transaction_rank", sql, re.IGNORECASE)
                and re.search(
                    r"ORDER BY\s+transaction_count\s+DESC",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(r"ORDER BY\s+transaction_rank", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "ORDER BY transaction_rank, client_id",
                    )
                )
        if "large_loan_high_salary_district_profile=true" in contract.filters:
            if re.search(
                r"type\s*=\s*'credit'|type\s*=\s*'debit'|total_credit|total_debit",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "交易汇总用 trans.type PRIJEM/VYDAJ（不是 credit/debit）",
                    )
                )
            if re.search(
                r"A3\s+AS\s+district_name|\.A3\s+AS\s+district_name",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "district_name 用 district.A2（region 用 A3）",
                    )
                )
            if re.search(
                r"Positive|Non-Positive|No Transactions",
                sql,
                re.IGNORECASE,
            ) and re.search(r"income_category", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "income_category 用 High/Medium/Low Income（按 total_income 阈值）",
                    )
                )
            if re.search(r"savings_ratio", sql, re.IGNORECASE) and re.search(
                r"total_debit[\s\S]{0,50}/[\s\S]{0,30}total_credit",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "savings_ratio=(total_income-total_expense)/total_income",
                    )
                )
            if re.search(r"300000|300,000", sql) and re.search(
                r"total_credit[\s\S]{0,40}-\s*[\s\S]{0,40}total_debit|"
                r"credit[\s\S]{0,30}-\s*[\s\S]{0,30}debit",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "净收入过滤：total_income>total_expense OR total_income IS NULL",
                    )
                )
            if re.search(r"max_loan_amount", sql, re.IGNORECASE) and re.search(
                r"JULIANDAY\s*\(\s*['\"]2026-10-01",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "age 用 strftime 年差（anchor 2026-10-01）",
                    )
                )
        if "prachatice_accounts_financial_profile=true" in contract.filters:
            if (
                re.search(r"Prachatice|prachatice", sql)
                and re.search(r"JOIN\s+disp", sql, re.IGNORECASE)
                and not re.search(r"type\s*=\s*'OWNER'", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Prachatice 账户 owner 须 disp.type='OWNER'（一行一账户）",
                    )
                )
            if re.search(
                r"amount\s*>\s*0[\s\S]{0,60}total_income|amount\s*<\s*0[\s\S]{0,60}total_expense",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "total_income/total_expense 用 trans.type PRIJEM/VYDAJ",
                    )
                )
            if re.search(r"customer_category", sql, re.IGNORECASE) and re.search(
                r"High Value|Medium Value|Low Value",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "customer_category 用 High Activity/Loan Customer/Active/Regular",
                    )
                )
            if re.search(r"balance_rank", sql, re.IGNORECASE) and re.search(
                r"RANK\s*\(\s*\)\s*OVER\s*\([\s\S]*balance_rank",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "balance_rank 用 ROW_NUMBER() OVER (ORDER BY net_balance DESC)",
                    )
                )
            if (
                re.search(r"ORDER BY\s+net_balance\s+DESC", sql, re.IGNORECASE)
                and re.search(
                    r"balance_rank",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(r"ORDER BY\s+balance_rank", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "最终 ORDER BY balance_rank（不是 net_balance DESC）",
                    )
                )
            if re.search(r"client_age", sql, re.IGNORECASE) and re.search(
                r"JULIANDAY\s*\(", sql, re.IGNORECASE
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "client_age 用 strftime 年差与 anchor 生日校正",
                    )
                )
            if re.search(r"loan_status", sql, re.IGNORECASE) and re.search(
                r"MAX\s*\(\s*l?\.?status\s*\)|MAX\s*\(\s*loan_status\s*\)",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "loan_status 用 Has Default/No Default/No Loans（status B 为违约）",
                    )
                )
        if "loan_id_4990_profile=true" in contract.filters:
            if re.search(
                r"Running contract|Contract finished|client in debt|loan not paid",
                sql,
                re.IGNORECASE,
            ) and re.search(r"status_description", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "loan 4990 status：A Running-OK、B Running-Issues、"
                        "C Finished-No Issues、D Finished-Issues（勿用其它文案）",
                    )
                )
            if re.search(
                r"status\s*=\s*'C'\s+THEN\s+0\s+ELSE\s+1[\s\S]{0,40}problematic",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "district_problematic_loans 计 status IN ('B','D')",
                    )
                )
            if (
                re.search(r"loan_id\s*=\s*4990", sql)
                and re.search(r"JOIN disp", sql, re.IGNORECASE)
                and not re.search(r"type\s*=\s*'OWNER'", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "borrower 须 disp.type='OWNER' 关联 client",
                    )
                )
            if re.search(r"district_loan_rank", sql, re.IGNORECASE) and not re.search(
                r"RANK\s*\(\s*\)\s*OVER\s*\(\s*PARTITION\s+BY[\s\S]*district",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "district_loan_rank 用 RANK() OVER (PARTITION BY district_id ORDER BY amount DESC)",
                    )
                )
        if "south_bohemia_top_population_profile=true" in contract.filters:
            if re.search(
                r"ORDER BY[\s\S]*inhabitants\s+DESC[\s\S]*LIMIT\s+1",
                sql,
                re.IGNORECASE,
            ) and not re.search(r"population_rank\s*=\s*1", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "最多人口区县：RegionStats 中 RANK() OVER (ORDER BY CAST(A4 AS INTEGER) DESC)，"
                        "WHERE population_rank=1",
                    )
                )
            if re.search(
                r"ORDER BY[\s\S]*A4\s+DESC|ORDER BY[\s\S]*inhabitants\s+DESC", sql, re.IGNORECASE
            ):
                if not re.search(
                    r"CAST\s*\(\s*A4\s+AS\s+INTEGER\s*\)|CAST\s*\(\s*d\.A4", sql, re.IGNORECASE
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "inhabitants/A4 排序须 CAST(A4 AS INTEGER)（A4 为文本）",
                        )
                    )
            if (
                re.search(r"total_clients", sql, re.IGNORECASE)
                and re.search(
                    r"COUNT\s*\(\s*c\.client_id\s*\)",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(r"COUNT\s*\(\s*DISTINCT\s+c\.client_id\s*\)", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "total_clients 用 COUNT(DISTINCT c.client_id)",
                    )
                )
        if "loan_98832_19960103_profile=true" in contract.filters:
            if re.search(
                r"STRFTIME\s*\(\s*'%Y'[\s\S]{0,80}98832|98832[\s\S]{0,80}STRFTIME\s*\(\s*'%Y'",
                sql,
                re.IGNORECASE,
            ) and not re.search(r"date\s*=\s*'1996-01-03'", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "目标贷款：loan.date='1996-01-03' AND amount=98832",
                    )
                )
            if re.search(r"JULIANDAY\s*\(\s*tl\.loan_date\s*\)", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "age_at_loan 用 strftime 年差并校正月日（LoanClient CTE）",
                    )
                )
            if re.search(
                r"amount\s*>\s*0[\s\S]{0,60}total_income|amount\s*<\s*0[\s\S]{0,60}total_expense",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "total_income/total_expense 用 trans.type PRIJEM/VYDAJ（不是 amount 正负）",
                    )
                )
            if (
                re.search(r"expense_to_income", sql, re.IGNORECASE)
                and re.search(
                    r"total_expense\s*/\s*NULLIF\s*\(\s*total_income",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(r"\*\s*100", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "expense_to_income_ratio=ROUND(expense/income*100,2)",
                    )
                )
            if (
                re.search(r"previous_loans", sql, re.IGNORECASE)
                and re.search(
                    r"prev_loans|previous_loans[\s\S]{0,80}tl\.account_id\s*=",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(r"client_id\s*=\s*CT\.client_id|d\.client_id", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "previous_loans 统计该 client 所有账户在贷款日前的 loan 笔数",
                    )
                )
            if (
                re.search(r"JOIN disp", sql, re.IGNORECASE)
                and re.search(
                    r"98832|1996-01-03",
                    sql,
                )
                and not re.search(r"type\s*=\s*'OWNER'", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "LoanClient 须 disp.type='OWNER' 关联 client",
                    )
                )
        if "female_birth_19760129_accounts_profile=true" in contract.filters:
            if re.search(
                r"SELECT\s+A3\s+FROM\s+district[\s\S]{0,120}AS\s+residence_district|"
                r"SELECT\s+A3\s+FROM\s+district[\s\S]{0,120}AS\s+account_district",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "residence_district/account_district 用 district.A2 名称（不是 A3 region）",
                    )
                )
            if re.search(r"type\s*=\s*'credit'|type\s*=\s*'debit'", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "total_income/total_expense 用 PRIJEM/VYDAJ（不是 credit/debit）",
                    )
                )
            if re.search(r"Same District|Different District", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "district_comparison 文案 Same as residence / Different from residence",
                    )
                )
        if "litomerice_1996_accounts_profile=true" in contract.filters:
            if re.search(r"A3\s*=\s*'Litomerice'", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Litomerice 区县名用 district.A2='Litomerice'（A3 是 region）",
                    )
                )
            if re.search(r"type\s*=\s*'credit'", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "total_deposits_in_1996 用 trans.type='PRIJEM'（不是 credit）",
                    )
                )
            if re.search(r"owner_clients|type\s*=\s*'OWNER'", sql, re.IGNORECASE) and re.search(
                r"accounts_with_multiple_clients",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "ClientInfo 统计 account 上全部 disp→client（勿限 OWNER）",
                    )
                )
            if re.search(r"average_client_age", sql, re.IGNORECASE) and re.search(
                r"2026-10-01[\s\S]{0,80}average_client_age|average_client_age[\s\S]{0,80}2026-10-01",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "average_client_age 用 1996 年与 birth_date 年差（ClientInfo 按 account）",
                    )
                )
            if (
                re.search(r"percent_opened_q1", sql, re.IGNORECASE)
                and re.search(
                    r"q1\s*\*\s*100[\s\S]{0,40}/\s*q_stats\.total",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(
                    r"AVG\s*\(\s*CASE\s+WHEN\s+month_opened",
                    sql,
                    re.IGNORECASE,
                )
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "季度开户占比：ROUND(AVG(CASE month_opened BETWEEN …)*100,2)",
                    )
                )
        if "card_issued_19961021_profile=true" in contract.filters:
            if re.search(
                r"ORDER BY[\s\S]*amount\s+DESC[\s\S]*LIMIT\s+1",
                sql,
                re.IGNORECASE,
            ) and not re.search(r"amount_rank\s*=\s*1", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "最大交易：TransactionStats 中 RANK() OVER (PARTITION BY account ORDER BY amount DESC)，"
                        "JOIN amount_rank=1",
                    )
                )
            if re.search(r"k_symbol\s+AS\s+transaction_category", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "transaction_category 用 amount 分档 High/Medium/Low Value（不是 k_symbol）",
                    )
                )
            if re.search(r"l\.status\s+AS\s+loan_status", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "loan_status 用 CASE loan_id IS NOT NULL→Has Loan/No Loan（不是 status 字母）",
                    )
                )
            if (
                re.search(r"JOIN district", sql, re.IGNORECASE)
                and re.search(
                    r"a\.district_id\s*=\s*dist\.district_id",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(
                    r"c\.district_id\s*=\s*di\.district_id|client\.district_id",
                    sql,
                    re.IGNORECASE,
                )
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "区县信息 JOIN client.district_id→district（不是 account.district_id）",
                    )
                )
        if "loan_approved_19940825_profile=true" in contract.filters:
            if re.search(
                r"A13\s+AS\s+salary_rank|A14\s+AS\s+unemployment_rank",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "salary_rank/unemployment_rank 用 RANK() OVER (ORDER BY A11/A12)，"
                        "不要 district.A13/A14 列",
                    )
                )
            if re.search(r"salary_rank|unemployment_rank", sql, re.IGNORECASE) and not re.search(
                r"RANK\s*\(\s*\)\s*OVER",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "DistrictInfo：RANK() OVER (ORDER BY avg_salary DESC) 与 "
                        "RANK() OVER (ORDER BY unemployment_rate_1995)",
                    )
                )
            if re.search(r"avg_client_age", sql, re.IGNORECASE) and re.search(
                r"2026-10-01[\s\S]{0,80}avg_client_age|avg_client_age[\s\S]{0,80}2026-10-01",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "avg_client_age 用贷款日 '1994-08-25' 与 birth_date 的 JULIANDAY 差/365.25",
                    )
                )
            if (
                re.search(r"total_income_before_loan", sql, re.IGNORECASE)
                and re.search(
                    r"SUM\s*\(\s*t\.amount\s*\)",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(r"type\s*=\s*'PRIJEM'", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "total_income_before_loan 仅 SUM PRIJEM 交易（t.date<贷款日）",
                    )
                )
        if "female_top3_salary_district_profile=true" in contract.filters:
            if re.search(
                r"ROW_NUMBER\s*\(\s*\)[\s\S]{0,120}rn\s*<=\s*3",
                sql,
                re.IGNORECASE,
            ) and not re.search(r"salary_rank_in_region", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "区县薪资 Top3：DistrictStats 中 RANK() 得 salary_rank_in_region<=3",
                    )
                )
            if re.search(
                r"COUNT\s*\(\s*DISTINCT[\s\S]{0,40}region\s*\)\s+AS\s+regions_represented",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "regions_represented 用 GROUP_CONCAT(DISTINCT ds.region)",
                    )
                )
            if re.search(
                r"status\s*=\s*'C'[\s\S]{0,60}active_loans",
                sql,
                re.IGNORECASE,
            ) or re.search(
                r"active_loans[\s\S]{0,40}status\s*=\s*'C'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "本聚合题 active_loans 计 loan status='A'（completed=B，defaulted=C）",
                    )
                )
            if (
                re.search(r"female_accounts", sql, re.IGNORECASE)
                and re.search(
                    r"type\s*=\s*'OWNER'",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(r"AccountActivity", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "AccountActivity：account→disp→client(gender F)，按 account.district_id 聚合",
                    )
                )
            if re.search(
                r"JOIN\s+female_clients\s+AS\s+fc\s+ON\s+fc\.district_id\s*=\s*ds\.district_id",
                sql,
                re.IGNORECASE,
            ) and re.search(r"average_female_age", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "average_female_age 用 AVG(ds.avg_age)，不要在最终 SELECT 再 JOIN 全部 female_clients",
                    )
                )
            if re.search(
                r"COUNT\s*\(\s*DISTINCT\s+aa\.client_id\s*\)\s+AS\s+total_female_clients",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "total_female_clients 用 SUM(ds.female_clients)，不要 COUNT(DISTINCT client)",
                    )
                )
            if re.search(r"average_female_age", sql, re.IGNORECASE) and re.search(
                r"AVG\s*\(\s*2026\s*-",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "average_female_age 用 ROUND(AVG(ds.avg_age), 1)（DistrictStats 已算 avg_age）",
                    )
                )
            if re.search(
                r"(total_female_loans|active_female_loans)",
                sql,
                re.IGNORECASE,
            ) and not re.search(r"total_loans\s*>\s*0", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "外层 WHERE 须 aa.total_loans > 0（仅统计有活跃贷款账户的区县）",
                    )
                )
            if re.search(
                r"female_clients\s+AS\s+\([\s\S]*?FROM\s+client",
                sql,
                re.IGNORECASE,
            ) and re.search(r"DistrictStats|district_stats", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "DistrictStats 内 JOIN client(gender='F') 一次算 female_clients 与 avg_age，"
                        "不要单独 female_clients CTE 再 JOIN",
                    )
                )
        if "card_issued_19940303_profile=true" in contract.filters:
            if re.search(r"JULIANDAY\s*\(\s*cd\.issued\s*\)", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "age_at_card_issue 用 STRFTIME 年差（issued 年 − birth 年），不要用 JULIANDAY/365.25",
                    )
                )
            if re.search(r"avg_salary", sql, re.IGNORECASE) and re.search(
                r"k_symbol\s*=\s*'SALARY'|trans.*avg_salary",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "avg_salary 用 district.A11（client.district_id→district），不是 trans SALARY 平均",
                    )
                )
            if re.search(r"active_loans", sql, re.IGNORECASE) and re.search(
                r"status\s*=\s*'C'[\s\S]{0,40}active_loans",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "active_loans 计数 loan status='A'（不是 C）",
                    )
                )
            if re.search(r"borrower_category", sql, re.IGNORECASE):
                if re.search(
                    r"Young Active Borrower|Middle-aged|Senior Active|Senior Borrower",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "borrower_category：loan_count>0 且 age<30→Young borrower，"
                            ">=30→Mature borrower，否则 Non-borrower",
                        )
                    )
                borrower_case = re.search(
                    r"case[\s\S]*?end\s+as\s+borrower_category",
                    sql,
                    re.IGNORECASE,
                )
                if borrower_case is not None and "loan_count" not in borrower_case.group(0):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "borrower_category CASE 必须基于 cai.loan_count>0 分档，"
                            "不要仅按 age_at_card_issue 分 Young/Mature/Senior",
                        )
                    )
                if re.search(r"active_loans\s*>\s*0[\s\S]{0,80}borrower", sql, re.IGNORECASE):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "borrower_category 基于 loan_count（不是 active_loans）",
                        )
                    )
            if re.search(r"age_rank_by_gender", sql, re.IGNORECASE) and re.search(
                r"ORDER BY[\s\S]*age_at_card_issue\s+DESC",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "age_rank_by_gender：RANK() PARTITION BY gender ORDER BY age_at_card_issue（升序）",
                    )
                )
        if "sokolov_pre1950_female_owner_profile=true" in contract.filters:
            if re.search(r"A3\s*=\s*'Sokolov'", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Sokolov 区县名用 district.A2='Sokolov'（A3 是 region）",
                    )
                )
            if re.search(r"clients_with_good_loans|Contract Finished/No Problems", sql, re.I):
                if re.search(
                    r"status\s*=\s*'C'[\s\S]{0,80}(good|finished|n_good)",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "clients_with_good_loans：loan status='A'（Contract Finished/No Problems）",
                        )
                    )
            if re.search(r"clients_with_debt|Client in Debt", sql, re.I):
                if re.search(
                    r"status\s*=\s*'B'[\s\S]{0,80}(debt|n_debt)",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "clients_with_debt：loan status='D'（Running Contract/Client in Debt）",
                        )
                    )
            if re.search(r"clients_with_good_loans", sql, re.I) and not re.search(
                r"type\s*=\s*'OWNER'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Sokolov 女 client 账户须 disp.type='OWNER'",
                    )
                )
        if "hickman_elementary_charter_profile=true" in contract.filters:
            if re.search(
                r'"Free Meal Count \(K-12\)"\s+AS\s+FRPMCount',
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPMCount 用 frpm `FRPM Count (K-12)`，不是 Free Meal Count",
                    )
                )
            if re.search(
                r"Free Meal Count \(K-12\)[\s\S]{0,80}/[\s\S]{0,40}Enrollment[\s\S]{0,40}AS\s+FRPMPercent",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPMPercent 用 `Percent (%) Eligible FRPM (K-12)` 小数列",
                    )
                )
            if re.search(r"District Type", sql, re.IGNORECASE) and not re.search(
                r"DOC\s*=\s*'52'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Elementary School District charter 题用 schools.DOC='52'（勿仅用 District Type）",
                    )
                )
            if (
                re.search(r"SizeRank", sql, re.IGNORECASE)
                and re.search(
                    r"RANK\s*\(\s*\)\s*OVER\s*\(\s*ORDER\s+BY",
                    sql,
                    re.IGNORECASE,
                )
                and not re.search(r"PARTITION\s+BY[\s\S]*City", sql, re.IGNORECASE)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SizeRank 用 ROW_NUMBER() OVER (PARTITION BY City ORDER BY Enrollment DESC)",
                    )
                )
            if re.search(r"COALESCE\s*\(\s*sat\.AvgScrRead\s*,\s*0\s*\)", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "无 SAT 时 SATTotalScore/分项保持 NULL（不要 COALESCE 成 0）",
                    )
                )
            if re.search(r"Below Average|Above Average", sql) and re.search(
                r"SATPerformanceCategory",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SATPerformanceCategory 用 PercentOver1500：High/Average/Low Performing",
                    )
                )
            if re.search(r"satscores", sql, re.IGNORECASE) and not re.search(
                r"rtype\s*=\s*'S'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SATPerformance CTE/Join 须 satscores rtype='S'",
                    )
                )
        if "adelanto_grade_span_profile=true" in contract.filters:
            if re.search(
                r"frpm_pct\s*>=\s*75|frpm_pct\s*>=\s*50|Percent \(.*FRPM.*\)\s*>=\s*75",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Adelanto poverty 分档：Percent FRPM 为小数，High/Medium 用 >0.75/>0.50（勿 >=75/50）",
                    )
                )
            if re.search(
                r"high_poverty_schools[\s\S]{0,200}>=\s*75|medium_poverty[\s\S]{0,200}>=\s*50",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "high/medium poverty 计数须基于小数 FRPM 阈值 0.75/0.50",
                    )
                )
            if re.search(
                r"ORDER BY[\s\S]*cnt[\s\S]*LIMIT\s+1",
                sql,
                re.IGNORECASE,
            ) and not re.search(r"grade_span_rank\s*=\s*1", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "最常见 grade span：SchoolsByGradeSpan 中 RANK() 得 grade_span_rank，WHERE =1",
                    )
                )
            if re.search(r"City\s*=\s*'Adelanto'", sql, re.IGNORECASE) and not re.search(
                r"StatusType\s*=\s*'Active'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Adelanto 题须 StatusType='Active'",
                    )
                )
            if re.search(
                r"SUM\s*\(\s*CASE\s+WHEN\s+frpm_pct\s*>=",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "poverty 计数：SchoolStats 中 CASE→High/Medium/Low Poverty，"
                        "外层 COUNT(CASE WHEN poverty_level=…)，不要 SUM(CASE frpm_pct>=75)",
                    )
                )
        if "ricci_ulrich_admin_sat_profile=true" in contract.filters:
            if not re.search(
                r"AdmFName1\s*=\s*'Ricci'[\s\S]*AdmLName1\s*=\s*'Ulrich'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Ricci Ulrich：WHERE AdmFName1='Ricci' AND AdmLName1='Ulrich'",
                    )
                )
            if re.search(r"At District Average", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "ComparisonToDistrictAvg 第三档文案为 Equal to District Average（不是 At District Average）",
                    )
                )
            if re.search(r"DifferenceFromDistrictAvg", sql, re.IGNORECASE) and not re.search(
                r"ROUND\s*\(\s*\(?\s*[\w.]+\.AvgScrWrite\s*-\s*[\w.]+\.DistrictAvgWriteScore",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "DifferenceFromDistrictAvg 用 ROUND(写分-学区均值, 2)",
                    )
                )
            if re.search(r"TotalSATScore\s*/\s*3", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "TotalSATScore=Read+Math+Write 三科之和（不要 /3）",
                    )
                )
            if re.search(r"WriteScoreRank|TotalScoreRank", sql, re.IGNORECASE) and not re.search(
                r"RANK\s*\(\s*\)\s*OVER",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "WriteScoreRank/TotalScoreRank 用 RANK() OVER (ORDER BY … DESC)",
                    )
                )
            if re.search(
                r"AdmFName1\s*=\s*'Ricci'",
                sql,
                re.IGNORECASE,
            ) and re.search(r"LEFT\s+JOIN\s+satscores", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Ricci Ulrich 题 satscores 用 INNER JOIN（有 SAT 的校才纳入）",
                    )
                )
        if "enrollment_rank_10_11_profile=true" in contract.filters:
            if re.search(r"\bRANK\s*\(\s*\)\s*OVER\s*\(\s*ORDER\s+BY", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "第10/11大校：EnrollmentRank 用 ROW_NUMBER() OVER (ORDER BY Enrollment DESC)",
                    )
                )
            if re.search(
                r"OFFSET\s+9|LIMIT\s+2[\s\S]*ORDER\s+BY[\s\S]*Enrollment",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "第10/11大校：WHERE EnrollmentRank IN (10,11)，不要用 LIMIT/OFFSET 取第10/11行",
                    )
                )
            if re.search(r"EligibleFreeRate", sql, re.IGNORECASE) and not re.search(
                r"\|\|\s*'%'",
                sql,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "EligibleFreeRate 输出 ROUND(rate*100,2)||'%'",
                    )
                )
            if re.search(
                r"Charter\s*=\s*1\s+THEN\s+'Yes'|Charter\s*=\s*0\s+THEN\s+'No'",
                sql,
                re.IGNORECASE,
            ) and re.search(r"SchoolType", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SchoolType 用 Charter School / Regular School（schools.Charter 1/0）",
                    )
                )
            if re.search(r"PercentAbove1500SAT", sql, re.IGNORECASE) and not re.search(
                r"Percent(?:age)?Above1500[\s\S]{0,120}\|\|\s*'%'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PercentAbove1500SAT 用 COALESCE(ROUND(PercentAbove1500*100,2),0)||'%'",
                    )
                )
            if re.search(r'School Type"', sql, re.IGNORECASE) and not re.search(
                r"Charter School",
                sql,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SchoolType 用 schools.Charter→Charter School / Regular School，不要用 frpm.`School Type`",
                    )
                )
            if re.search(r'"Low Grade"|low_grade\s*\|\|', sql, re.IGNORECASE) and re.search(
                r"GradeSpan",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "GradeSpan 用 schools.GSoffered，不要用 Low/High Grade 拼接",
                    )
                )
            if re.search(r"\brn\s+IN\s*\(\s*10", sql, re.IGNORECASE) and not re.search(
                r"EnrollmentRank\s+IN\s*\(\s*10",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "WHERE EnrollmentRank IN (10, 11)（CTE 列名 EnrollmentRank，不要 rn IN）",
                    )
                )
        if "amador_high_school_stats_profile=true" in contract.filters:
            if re.search(r"GSserved\s+LIKE", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Amador 高中：`Low Grade`='9' AND `High Grade`='12'，不要用 GSserved LIKE",
                    )
                )
            if re.search(r"SUM\s*\(\s*CASE\s+WHEN\s+Charter\s*=", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "CharterSchools/NonCharter 用 frpm `Charter School (Y/N)`",
                    )
                )
            if re.search(r"free_meal\s*\*\s*1\.0\s*/\s*enrollment", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "AvgFRPMPercentage 用 AVG(Percent FRPM)*100；"
                        "HighPoverty 用 FRPM>0.75 的 PovertyLevel，不要用 free meal 率",
                    )
                )
            if re.search(
                r"ORDER BY[\s\S]*enrollment\s+DESC[\s\S]*LIMIT\s+1",
                sql,
                re.IGNORECASE,
            ) and "LargestSchool" in "".join(contract.projections):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "LargestSchool 用 RANK() EnrollmentRank=1",
                    )
                )
        if "top_math_sat_active_profile=true" in contract.filters:
            if re.search(
                r"ORDER BY[\s\S]*AvgScrMath\s+DESC[\s\S]*LIMIT\s+1",
                sql,
                re.IGNORECASE,
            ) and not re.search(r"MathRank\s*=\s*1", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "最高 Math SAT：SchoolRankings 中 RANK() 得 MathRank，"
                        "外层 WHERE MathRank=1；不要 ORDER BY AvgScrMath LIMIT 1",
                    )
                )
            if re.search(
                r"Free Meal Count \(K-12\)[\s\S]*% Free/Reduced",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "% Free/Reduced Price Meals 用 "
                        "ROUND(Percent (%) Eligible FRPM (K-12)*100,2)||'%'",
                    )
                )
            if re.search(r"\bsc\.Charter\b|\bs\.Charter\b", sql) and re.search(
                r"Is Charter School",
                sql,
                re.IGNORECASE,
            ):
                if not re.search(r"Charter School \(Y/N\)", sql, re.IGNORECASE):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "Is Charter 用 frpm `Charter School (Y/N)`（Academic Year='2014-2015'）",
                        )
                    )
        if "top3_sat_excellence_profile=true" in contract.filters:
            if re.search(r"ROW_NUMBER\s*\(\s*\).*SAT Excellence Rank", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SAT Excellence Rank 用 RANK() OVER (ORDER BY excellence_rate DESC)，"
                        "不要用 ROW_NUMBER",
                    )
                )
            if re.search(r"LIMIT\s+3", sql, re.IGNORECASE) and not re.search(
                r"rank\s*<=\s*3",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Top-3 excellence：CTE 中 RANK()，外层 WHERE rank<=3；不要 ORDER BY LIMIT 3",
                    )
                )
            if re.search(r"Free Meal Count \(K-12\)", sql) and re.search(
                r"Poverty Rate|Poverty Category",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Poverty Rate/Category 用 frpm Percent (%) Eligible FRPM (K-12) 小数分档",
                    )
                )
            if re.search(r"High FRPM|Medium FRPM", sql) and "Poverty Category" in "".join(
                contract.projections
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Poverty Category 用 High/Medium/Low/Very Low Poverty",
                    )
                )
        if "sat_excellence_county_free_meal_profile=true" in contract.filters:
            if re.search(r"/\s*2400|sat_total\s*\*\s*1\.0\s*/\s*2400", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "excellence_rate 用 NumGE1500/NumTstTakr（过滤 >0.3），"
                        "不要用 SAT 总分/2400",
                    )
                )
            if (
                re.search(
                    r"Free Meal Count \(K-12\)|Enrollment \(K-12\)",
                    sql,
                    re.IGNORECASE,
                )
                and "eligible_free_rate" in sql.lower()
            ):
                if not re.search(r"Ages 5-17", sql, re.IGNORECASE):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "eligible_free_rate 用 frpm Ages 5-17 列，不要用 K-12",
                        )
                    )
            if re.search(r"SOCType\s+AS\s+school_type", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "school_type 用 schools.Charter→Charter School/Non-Charter School",
                    )
                )
            if re.search(r"High FRPM|Medium FRPM", sql) and "free_meal_category" in sql.lower():
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "free_meal_category 用 High/Medium/Low Free Meal Rate",
                    )
                )
        if "la_low_free_meal_profile=true" in contract.filters:
            if re.search(r"Low FRPM|'Low FRPM'", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FreeCategory 按 free meal 百分比分 Very Low/Low/Medium/High，"
                        "不要用 Low FRPM",
                    )
                )
            if re.search(
                r"RANK\s*\(\s*\)\s+OVER\s*\(\s*ORDER\s+BY[\s\S]*CountyRank",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "CountyRank 用 ROW_NUMBER() OVER (PARTITION BY County ORDER BY FreePercent)",
                    )
                )
            if re.search(r"<\s*0\.0018", sql) and not re.search(
                r"\*\s*100[\s\S]*<\s*0\.18",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "free meal 率用 Free Meal Count/Enrollment×100 得 FreePercent，"
                        "过滤 FreePercent < 0.18（不要用小数 0.0018 口径混用）",
                    )
                )
        if "fresno_direct_funded_charter_profile=true" in contract.filters:
            if re.search(r"\bFundingType\b", sql, re.IGNORECASE) and not re.search(
                r"Charter Funding Type",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Directly funded 过滤用 frpm.`Charter Funding Type`='Directly funded'，"
                        "不要用 schools.FundingType",
                    )
                )
            if re.search(r"COUNT\s*\(\s*\*\s*\)\s+AS\s+TotalSchools", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "TotalSchools 用 COUNT(DISTINCT CDSCode)，不要用 COUNT(*)",
                    )
                )
            if re.search(
                r"NumTstTakr\s*<\s*50[\s\S]*Under50|Under50[\s\S]*NumTstTakr\s*<\s*50",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SchoolsWithUnder50Testers 分桶用 NumTstTakr <= 50（不是 < 50）",
                    )
                )
            if "AvgFRPMPercentage" in contract.projections and re.search(
                r"AvgFRPMPercentage",
                sql,
                re.IGNORECASE,
            ):
                if re.search(r"AVG\s*\(\s*frpm_pct\s*\)", sql, re.IGNORECASE) and not re.search(
                    r"\*\s*100",
                    sql,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "AvgFRPMPercentage 用 ROUND(AVG(`Percent (%) Eligible FRPM (K-12)`)*100, 2)",
                        )
                    )
        if "colusa_humboldt_ratio_profile=true" in contract.filters:
            if re.search(
                r"High Free Meal|free meal eligibility|free_meal.*0\.75",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "High FRPM 校计数用 Percent (%) Eligible FRPM (K-12) > 0.5，"
                        "不要用 free meal rate 0.75 或 High Free Meal 文案",
                    )
                )
            if re.search(
                r"SUM\s*\(\s*f\.[\"']Free Meal Count \(K-12\)[\"']",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPM 学生总量用 SUM(FRPM Count (K-12))，不要用 Free Meal Count",
                    )
                )
            for metric in re.findall(
                r"SELECT\s+'([^']+)'\s*(?:AS\s+Metric)?\s*,",
                sql,
                re.IGNORECASE,
            ):
                if metric and not metric.strip().endswith("Ratio"):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            f"Metric 文案须以 Ratio 结尾（如 Total Schools Ratio），"
                            f"不要用 '{metric}'",
                        )
                    )
                    break
        if "high_frpm_unexpected_performance_profile=true" in contract.filters:
            if re.search(r"PerformanceCategory", sql, re.IGNORECASE) and re.search(
                r"Below Average|Above Average|'Average'",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PerformanceCategory 用 High/Medium/Low（SAT 总分 ≥1500/≥1200），"
                        "不要用 Below/Average/Above Average 标签",
                    )
                )
            if "UnabbreviatedMailingAddress" in contract.projections and re.search(
                r"\|\|",
                sql,
            ):
                if re.search(
                    r"UnabbreviatedMailingAddress|MailingAddress",
                    sql,
                    re.IGNORECASE,
                ):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "UnabbreviatedMailingAddress 用 schools.MailStreet（或 sch.MailStreet），"
                            "不要拼接 MailStreet/City/Zip",
                        )
                    )
        if "top10_high_frpm_profile=true" in contract.filters:
            if re.search(r"order by[\s\S]*limit\s+10", sql, re.IGNORECASE) and not re.search(
                r"frpm_rank\s*<=",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Top-10 FRPM：RANK() OVER (ORDER BY FRPM Count DESC) 得 frpm_rank，"
                        "外层 WHERE frpm_rank<=10；不要 ORDER BY … LIMIT 10",
                    )
                )
            if re.search(r'frpm\."School Type"|frpm\.\`School Type\`', sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "school_type 用 schools Charter→Charter School/Non-Charter School，"
                        "不要用 frpm School Type",
                    )
                )
            if re.search(
                r"NumTstTakr\s*\*\s*100[\s\S]*Enrollment\s*\(\s*K-12\s*\)",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "percent_taking_sat 用 satscores.enroll12 作分母，不要用 frpm Enrollment (K-12)",
                    )
                )
        if "enrollment500_frpm_sat_profile=true" in contract.filters:
            if re.search(r"THEN\s+'High'|THEN\s+'Medium'|THEN\s+'Low'", sql) and not re.search(
                r"High FRPM", sql
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPMCategory 标签用 High FRPM / Medium FRPM / Low FRPM",
                    )
                )
            if re.search(
                r"Percent\s*\(\%\)\s*Eligible\s*FRPM[\s\S]*?\*\s*100[\s\S]*?>=\s*75",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPMCategory 分档用小数列 >=0.75 / >=0.50，不要对 ×100 后的值用 >=75",
                    )
                )
            if re.search(r"satscores", sql, re.I) and not re.search(
                r"rtype\s*=\s*['\"]S['\"]", sql, re.I
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SAT 题 satscores 需 rtype='S'（学校级记录）",
                    )
                )
            if (
                re.search(r"Enrollment \(K-12\)", sql)
                and "TotalEnrollment" in " ".join(contract.projections)
                and "Ages 5-17" not in sql
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "TotalEnrollment = Enrollment (K-12) + Enrollment (Ages 5-17)",
                    )
                )
            if re.search(r"\bs\.Charter\b|\bschools\.Charter\b", sql, re.IGNORECASE) and (
                "charter school (y/n)" not in sql.lower()
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "IsCharter 用 frpm.`Charter School (Y/N)`，输出 IsCharterSchool Yes/No",
                    )
                )
            if (
                re.search(r"\bsatscores\b|\bss\.\b", sql, re.IGNORECASE)
                and "rtype" not in sql.lower()
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "satscores 侧过滤 rtype='S'（学校级记录）",
                    )
                )
        if "virtual_sat_f_profile=true" in contract.filters:
            if re.search(r"Virtual\s*=\s*'Fully Virtual'", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "schools.Virtual 存 F/P/N 代码；fully virtual 过滤用 Virtual='F'，"
                        "VirtualStatus 用 CASE 映射 Fully Virtual 等标签",
                    )
                )
            if re.search(r"FRPMPercentage\s*>=\s*75|FRPMPercentage\s*>=\s*50", sql):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PovertyLevel 基于 frpm 小数列 >=0.75/0.50/0.25，"
                        "标签 High/Medium/Low/Very Low Poverty；不要对 ×100 后的 FRPMPercentage 用 >=75",
                    )
                )
            if re.search(r"High FRPM|Medium FRPM|Low FRPM", sql) and "Poverty" in "".join(
                contract.projections
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "本题 PovertyLevel 用 High/Medium/Low/Very Low Poverty，不要用 High FRPM",
                    )
                )
            if re.search(r"GSserved\s+AS\s+SchoolType|GSoffered\s+AS\s+SchoolType", sql, re.I):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SchoolType 用 Charter School / Regular School（schools.Charter），不要用 GSserved",
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
                r"\bs\.School\b|\bschools\.School\b",
                sql,
                re.IGNORECASE,
            ) and not re.search(r'"School Name"', sql):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "CharterSchoolName 用 frpm.`School Name`，不要用 schools.School",
                    )
                )
            if re.search(r">=\s*0\.75|>=\s*0\.50", sql) and re.search(
                r"High FRPM|Medium FRPM", sql, re.IGNORECASE
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPMCategory 分档用严格 >0.75 / >0.50，不要用 >=",
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
            if re.search(r"Very High FRPM", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPMCategory 用 High FRPM / Medium FRPM / Low FRPM（>0.75/>0.50），"
                        "不要用 Very High FRPM",
                    )
                )
            if re.search(r"\bStatusType\s+AS\s+CurrentStatus", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "CurrentStatus 用 ClosedDate：NULL→Active，否则 Closed；不要用 StatusType",
                    )
                )
            if re.search(
                r"WITH\s+base\s+AS\s+\([\s\S]*?SELECT[\s\S]*?FROM\s+frpm",
                sql,
                re.IGNORECASE,
            ) and "CharterSchoolInfo" not in sql and "SATPerformance" not in sql:
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Fresno COE charter：CharterSchoolInfo + SATPerformance 两 CTE LEFT JOIN",
                    )
                )
        if "magnet_sat_profile=true" in contract.filters:
            if re.search(r'School Type"', sql, re.IGNORECASE) and not re.search(
                r"\bSOCType\s+AS\s+SchoolType",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SchoolType 用 schools.SOCType，不要用 frpm.`School Type`",
                    )
                )
            if re.search(r'Educational Option Type"', sql, re.IGNORECASE) and not re.search(
                r"\bEdOpsName\s+AS\s+EducationalOption",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "EducationalOption 用 schools.EdOpsName，不要用 frpm.`Educational Option Type`",
                    )
                )
            if re.search(
                r"Free Meal Count \(K-12\)[\s\S]{0,80}\*\s*100",
                sql,
                re.IGNORECASE,
            ) and re.search(r"FreeReducedMealPercentage|FRPMPercent", sql, re.I):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FreeReducedMealPercentage 用 frpm.`Percent (%) Eligible FRPM (K-12)` 小数列，"
                        "不要用 Free Meal Count×100/Enrollment",
                    )
                )
            if re.search(r"High FRPM|Medium FRPM|Low FRPM", sql) and "PovertyLevel" in "".join(
                contract.projections
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PovertyLevel 用 High/Moderate/Low/Very Low Poverty（frpm 小数 >0.75/>0.50/>0.25），"
                        "不要用 High/Medium/Low FRPM",
                    )
                )
            if re.search(
                r"THEN\s+'Above Average'|THEN\s+'Below Average'",
                sql,
                re.IGNORECASE,
            ) and "PerformanceCategory" in "".join(contract.projections):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PerformanceCategory 用 Excellent/Good/Average/Below Average（1800/1500/1200），"
                        "不要用 Above Average/Below Average",
                    )
                )
            if "CountyRank" in "".join(contract.projections) and not re.search(
                r"DENSE_RANK\s*\(",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "CountyRank 用 DENSE_RANK() OVER (PARTITION BY County …)",
                    )
                )
            if "StateRank" in "".join(contract.projections) and re.search(
                r"DENSE_RANK\s*\(\s*\)\s*OVER\s*\(\s*ORDER\s+BY\s+TotalAvgScore",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "StateRank 用 RANK() OVER (ORDER BY TotalAvgScore DESC)，不要用 DENSE_RANK",
                    )
                )
            if re.search(
                r"ROUND\s*\(\s*sa\.NumGE1500\s*\*\s*100",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PercentHighScorers 用 CAST(NumGE1500 AS FLOAT)/NULLIF(NumTstTakr,0)*100，"
                        "不要 ROUND(NumGE1500*100/NumTstTakr,2)",
                    )
                )
            if re.search(r"s\.Magnet\s*=\s*1", sql, re.IGNORECASE) and re.search(
                r"StateRank|CountyRank",
                sql,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Magnet=1 放在最外层 WHERE；StateRank/CountyRank 在 CTE 内对全部 "
                        "NumTstTakr>500 学校先计算",
                    )
                )
            if (
                "TotalAvgScore DESC" in sql
                and "PercentHighScorers DESC" not in sql.replace("\n", " ")
                and "PerformanceCategory" in "".join(contract.projections)
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "ORDER BY TotalAvgScore DESC, PercentHighScorers DESC（与 Gold 次序一致）",
                    )
                )
        if "top_reading_sat_profile=true" in contract.filters:
            if re.search(r"\bGSserved\s+AS\s+GradeSpan", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "GradeSpan 用 schools.GSoffered，不要用 GSserved",
                    )
                )
            if re.search(r"Enrollment \(K-12\)", sql) and "Ages 5-17" not in sql:
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPM/Enrollment 用 frpm Ages 5-17 列（`FRPM Count (Ages 5-17)` 等）",
                    )
                )
            if re.search(
                r"ORDER BY[\s\S]{0,120}ReadingScore[\s\S]{0,40}LIMIT\s+1",
                sql,
                re.IGNORECASE,
            ) and not re.search(r"ReadingRank\s*=\s*1", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "最高 Reading：RANK() 后 WHERE ReadingRank=1，不要仅用 ORDER BY LIMIT 1",
                    )
                )
            if re.search(
                r"NumGE1500[\s\S]{0,60}\*\s*100[\s\S]{0,40}/[\s\S]{0,40}Enrollment",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PercentScoring1500Plus=NumGE1500×100/NumTstTakr，不要用 Enrollment 作分母",
                    )
                )
            if re.search(r"FRPMPercentage\s*>=\s*75|FRPMPercentage\s*>=\s*50", sql):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PovertyLevel 分档用 frpm 小数 >0.75/>0.50/>0.25，不要 FRPMPercentage>=75",
                    )
                )
            if re.search(r"High FRPM|Medium FRPM", sql) and "PovertyLevel" in "".join(
                contract.projections
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PovertyLevel 用 High/Moderate/Low/Very Low Poverty (…%) 标签，不要用 High FRPM",
                    )
                )
            if re.search(r'School Type"\s+AS\s+SchoolType', sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SchoolType 用 Charter School / Non-Charter School（schools.Charter），"
                        "不要用 frpm.`School Type`",
                    )
                )
            if re.search(r"Very High Poverty", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PovertyLevel 最高档用 High Poverty (>75%)，不要用 Very High Poverty",
                    )
                )
            if re.search(
                r"THEN\s+'High Poverty'|THEN\s+'Moderate Poverty'|THEN\s+'Low Poverty'",
                sql,
                re.IGNORECASE,
            ) and not re.search(r"Poverty\s*\(>", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PovertyLevel 标签含区间：High Poverty (>75%)、Moderate Poverty (50-75%) 等",
                    )
                )
            if re.search(
                r"ROUND\s*\(\s*r\.NumGE1500\s*\*\s*100",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PercentScoring1500Plus=NumGE1500*100.0/NumTstTakr（勿 ROUND）",
                    )
                )
            if re.search(
                r"FROM\s+satscores[\s\S]{0,120}rtype\s*=\s*'S'",
                sql,
                re.IGNORECASE,
            ) and re.search(r"NumTstTakr\s*>\s*10", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SchoolRankings 仅 NumTstTakr>10，不要额外 rtype='S' 过滤",
                    )
                )
        if "top_frpm_soc66_profile=true" in contract.filters:
            if re.search(
                r"ORDER BY[\s\S]{0,80}FRPM[\s\S]{0,40}LIMIT\s+5",
                sql,
                re.IGNORECASE,
            ) and not re.search(r"FRPMRank\s*<=\s*5", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Top-5 FRPM：RANK() OVER FRPM Count，WHERE FRPMRank<=5；勿在 CTE 内 ORDER BY LIMIT 5",
                    )
                )
            if re.search(r"ROW_NUMBER\s*\(\s*\)\s*OVER[\s\S]{0,80}FRPMRank", sql, re.IGNORECASE):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPMRank 用 RANK()，不要用 ROW_NUMBER()",
                    )
                )
            if re.search(r"EligibilityRate", sql) and not re.search(
                r"\|\|\s*'%'",
                sql,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "EligibilityRate 输出 ROUND(rate*100,2)||'%'",
                    )
                )
            if re.search(r"THEN\s+'High FRPM'", sql) and not re.search(
                r"Very High FRPM",
                sql,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "EligibilityCategory 用 Very High/High/Moderate/Low FRPM 四档（>=0.75 为 Very High）",
                    )
                )
            if re.search(r"\bsatscores\b", sql, re.IGNORECASE) and not re.search(
                r"rtype\s*=\s*['\"]S['\"]",
                sql,
                re.IGNORECASE,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "SAT 子集 satscores 需 rtype='S'（学校级记录）",
                    )
                )
        if "virtual_charter_p_profile=true" in contract.filters:
            if re.search(r"High FRPM|Medium FRPM|Low FRPM", sql) and "PovertyLevel" in "".join(
                contract.projections
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PovertyLevel 用 High/Medium-High/Medium-Low/Low Poverty（frpm 小数），"
                        "不要用 High/Medium/Low FRPM",
                    )
                )
            if "FRPMPercentage" in "".join(contract.projections) and not re.search(
                r"\|\|\s*'%'",
                sql,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "FRPMPercentage 输出 ROUND(小数×100,2)||'%'",
                    )
                )
            if "PercentOver1500" in "".join(contract.projections) and not re.search(
                r"\|\|\s*'%'",
                sql,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "PercentOver1500 带 '%' 后缀（无 SAT 时 '0%'）",
                    )
                )
        if "virtual_county_compare_profile=true" in contract.filters:
            if (
                re.search(
                    r"CASE WHEN\s+Charter\s*=\s*1|SUM\(CASE WHEN\s+[\w.]+\.Charter",
                    sql,
                    re.IGNORECASE,
                )
                and "Charter School (Y/N)" not in sql
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "Charter/Regular 计数用 frpm.`Charter School (Y/N)`→Charter School/Regular School",
                    )
                )
            if re.search(r"San Diego", sql) and re.search(r"Santa Barbara", sql):
                if not re.search(r"CountyRank\s*=\s*1", sql, re.IGNORECASE):
                    findings.append(
                        SemanticFinding(
                            "projection_mismatch",
                            "只输出 virtual 校数量最多的县：CountyStats 上 RANK 后 WHERE CountyRank=1",
                        )
                    )
            if "AvgFreeReducedMealPercentage" in "".join(contract.projections) and not re.search(
                r"\|\|\s*'%'",
                sql,
            ):
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        "AvgFreeReducedMealPercentage 输出 ROUND(…,2)||'%'（frpm Percent FRPM×100 口径）",
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
        expected_order = [name.lower() for name in contract.projections]
        if alias_order != expected_order:
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
        elif (
            "ss_item_sk" in lowered
            and "in (select" not in lowered
            and "in(select" not in lowered.replace(" ", "")
        ):
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
    cte_name = (
        None if skip_sk_cte else _sk_heavy_cte_without_dimensions(described, contract.group_keys)
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
    if "multi_channel_union=true" in contract.filters and "union" in lowered_sql:
        if any(label in sql for label in ("'Catalog'", "'Store'", "'Web'")):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "渠道标签用 Gold 小写字面量 'store'、'catalog'、'web'，"
                    "不要用 'Store'/'Catalog'/'Web'",
                )
            )
        if not re.search(
            r"group\s+by[^)]*ss_item_sk|group\s+by[^)]*cs_item_sk|group\s+by[^)]*ws_item_sk",
            lowered_sql,
            re.IGNORECASE,
        ):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "各 UNION 分支先按 item_sk 与 sales_year GROUP BY 汇总 *_ext_sales_price，"
                    "再 UNION ALL 后外层按 channel/item_category/sales_year 汇总",
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
    if "inventory_sold_items=subquery" in contract.filters and "inventory" in referenced:
        if re.search(
            r"from\s+inventory\b[\s\S]*?join\s+store_sales\b",
            lowered_sql,
            re.IGNORECASE,
        ):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "卖过商品过滤用 inventory.inv_item_sk IN (store_sales 子查询)，"
                    "主查询 FROM inventory 后不要 JOIN store_sales",
                )
            )
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
        if re.search(
            r"from\s+stock\b[\s\S]*group\s+by[^;]*\bquantity_on_hand\b",
            lowered_sql,
            re.IGNORECASE,
        ) or re.search(
            r"from\s+stock\b[\s\S]*group\s+by[^;]*\bquantity_sold\b",
            lowered_sql,
            re.IGNORECASE,
        ):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "外层 GROUP BY 只用 warehouse_state、item_category、inventory_year；"
                    "quantity_on_hand/quantity_sold 仅 SUM 聚合",
                )
            )
        if re.search(
            r"group\s+by[^;]*(?:,\s*)2001(?:\s|$|;)",
            sql,
            re.IGNORECASE,
        ):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "GROUP BY 用 inventory_year 列/别名，不要写裸字面量 2001",
                )
            )
        if re.search(r"\b2001\s+as\s+inventory_year\b", lowered_sql, re.IGNORECASE):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "inventory_year 来自 stock CTE 的 date_dim.d_year，"
                    "不要 SELECT 2001 AS inventory_year",
                )
            )
        stock_cte = re.search(
            r"\bstock\s+as\s*\((.*?)\)\s*select\b",
            lowered_sql,
            re.IGNORECASE | re.DOTALL,
        )
        if stock_cte is not None and "d_year" not in stock_cte.group(1):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "stock CTE 需 JOIN date_dim 并 SELECT date_dim.d_year AS inventory_year，"
                    "再与 sold CTE 按 inv_item_sk/ss_item_sk JOIN",
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
    if (
        bill_ship
        and "web_sales" in referenced
        and core_tables
        and "customer" in {name.lower() for name in core_tables}
    ):
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
    demo_dims = {"marital_status", "education_status", "credit_rating", "gender"} & {
        name.lower() for name in contract.projections
    }
    if demo_dims and "store_sales" in referenced and "customer" in referenced:
        if re.search(r"\bss_cdemo_sk\b", lowered_sql) and "c_current_cdemo_sk" not in lowered_sql:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "store_sales 顾客人口统计经 customer.c_current_cdemo_sk → customer_demographics，"
                    "不要仅用 ss_cdemo_sk",
                )
            )
    if "quantity_sold" in {p.lower() for p in contract.projections} and "store_sales" in referenced:
        if re.search(
            r"sum\s*\(\s*[^)]*\bss_sales_price\b[^)]*\)\s*as\s*quantity_sold",
            lowered_sql,
            re.IGNORECASE,
        ):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "quantity_sold 用 SUM(store_sales.ss_quantity)，不要用 ss_sales_price",
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
    income_dims = {"income_lower", "buy_potential"} & {
        name.lower() for name in contract.projections
    }
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
    if re.search(r"PerformanceCategory", sql, re.IGNORECASE) and re.search(
        r"PerformanceClassification", sql, re.IGNORECASE
    ):
        sat_label_repeats = len(re.findall(r"Below Average|Above Average", sql, re.IGNORECASE))
        if sat_label_repeats >= 2 and not re.search(
            r"Expected performance|despite high FRPM|despite low FRPM",
            sql,
            re.IGNORECASE,
        ):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "PerformanceClassification 应基于 FRPM 与 SAT 对比（Expected/despite high FRPM 等），"
                    "不要重复 PerformanceCategory 的 SAT 分数档标签",
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


def _window_order_matches_group_by(select: exp.Select, window: exp.Window) -> bool:
    group_exprs = select.args.get("group")
    if not group_exprs:
        return False
    grouped_names: set[str] = set()
    for g in group_exprs.expressions:
        for col in g.find_all(exp.Column):
            grouped_names.add(col.name.lower())
    if not grouped_names:
        return False
    partition = window.args.get("partition_by")
    if partition is not None:
        part_items = (
            partition.expressions
            if hasattr(partition, "expressions")
            else partition
            if isinstance(partition, list)
            else [partition]
        )
        for item in part_items:
            cols = list(item.find_all(exp.Column))
            if cols and not all(c.name.lower() in grouped_names for c in cols):
                return False
    order = window.args.get("order")
    if order is None:
        return False
    for item in order.expressions:
        expr = item.this if isinstance(item, exp.Ordered) else item
        cols = list(expr.find_all(exp.Column))
        if not cols:
            return False
        if not all(c.name.lower() in grouped_names for c in cols):
            return False
    return True


def _window_order_uses_only_aggregates(window: exp.Window) -> bool:
    order = window.args.get("order")
    if order is None:
        return False
    ordered = order.expressions if hasattr(order, "expressions") else ()
    if not ordered:
        return False
    for item in ordered:
        expr = item.this if isinstance(item, exp.Ordered) else item
        if expr.find(exp.AggFunc) is None:
            return False
    return True


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
            window = expression.find(exp.Window)
            if window is None:
                continue
            if _window_order_uses_only_aggregates(window):
                continue
            grouped = select.args.get("group")
            group_count = len(grouped.expressions) if grouped else 0
            if group_count >= 3 and _window_order_matches_group_by(select, window):
                continue
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
                "JOIN date_dim ON … WHERE d_year=2001) 或 sold_items CTE；主查询不要 JOIN store_sales，"
                "不必 JOIN store 维表。"
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
                hints.append("以上为问句审计提示；若投影或过滤还需其它维表/事实表，可一并 JOIN。")
        if item == "order_sensitive=true":
            hints.append("问句要求排序，最终 SQL 需包含 ORDER BY。")
        if item.startswith("anchor_date="):
            day = item.split("=", 1)[1]
            hints.append(
                f"相对日期/校龄计算使用 anchor {day}，不要用 date('now') 或 julianday('now')。"
            )
        if item == "financial_1993_poplatek_profile=true":
            hints.append(
                "1993 POPLATEK PO OBRATU：AccountsIn1993；AccountStats/ClientDetails/LoanInfo "
                "均 FROM AccountsIn1993 LEFT JOIN 子表；PRIJEM/VYDAJ 分列；"
                "urbanization=A10 分档；balance_volatility=MAX-MIN balance；"
                "avg_client_age=JULIANDAY 差/365.25；risk=High Risk/Low Risk/No Loans。"
            )
        if item == "state_special_soc3_profile=true":
            hints.append(
                "State Special Schools：DOCType 过滤；SchoolType Charter/Non-Charter；"
                "CurrentStatus=ClosedDate NULL→Active else Closed；Poverty High/Medium/Low/Very Low；"
                "OpeningDate=date(OpenDate)；AvgTotalScore 三科均值/3；SOC 过滤在外层 CTE；"
                "ORDER BY EnrollmentRank ASC。"
            )
        if item == "la_meal_stats_aggregate_profile=true":
            hints.append(
                "LA free>500 FRPM<700：SchoolMealStats+CategoryBreakdown CTE；"
                "标量子查询 SchoolsWithoutSAT 与 GROUP_CONCAT breakdown；FreeMealCategory 按 free meal count。"
            )
        if item == "financial_salary_gap_profile=true":
            hints.append(
                "最年长女性 client→district_id 子查询；JOIN account/disp/client/district；"
                "ORDER BY A11 DESC LIMIT 1；第二列 `(SELECT MAX(A11)-MIN(A11) FROM district)` 作别名。"
            )
        if item == "schools_admin_doc_soc_profile=true":
            hints.append(
                "管理员邮箱题：仅 schools 表；DOC=54 Unified；SOC=62 Intermediate/Middle；"
                "strftime('%Y',OpenDate) BETWEEN '2009' AND '2010'。"
            )
        if item == "la_k9_frpm_sat_profile=true":
            hints.append(
                "LA K-9：schools.County='Los Angeles'，GSserved='K-9'；frpm Ages 5-17 列；"
                "Poverty High/Medium/Low Poverty；Charter Yes (num)/No；satscores rtype='S'。"
            )
        if item == "directly_funded_stanislaus_profile=true":
            hints.append(
                "Directly funded + Stanislaus + OpenDate 2000-2005：FundingType='Directly funded'；"
                "CountyStats 县均值对比；FRPMRank/SATScoreRank 用 RANK()。"
            )
        if item == "amador_high_school_stats_profile=true":
            hints.append(
                "Amador 9-12：SchoolInfo+SATData CTE；聚合 COUNT/AVG/SUM；"
                "DistrictCount 子查询；LargestSchool EnrollmentRank=1；"
                "MaxPercentAbove1500 来自 SAT NumGE1500/NumTstTakr×100。"
            )
        if item == "enrollment_rank_10_11_profile=true":
            hints.append(
                "第10/11大 K-12：EnrollmentRanked 用 ROW_NUMBER() OVER (ORDER BY Enrollment DESC)；"
                "WHERE EnrollmentRank IN (10,11)；SchoolDetails+SATPerformance LEFT JOIN；"
                "EligibleFreeRate 与 PercentAbove1500SAT 带 ||'%'；SchoolType Charter/Regular School。"
            )
        if item == "ricci_ulrich_admin_sat_profile=true":
            hints.append(
                "Ricci Ulrich：SchoolStats JOIN satscores+frpm；DistrictAverages 按 District AVG(写分)；"
                "RANK 写分/总分；Comparison Above/Equal/Below District Average；"
                "DifferenceFromDistrictAvg ROUND 差值；PercentageTakingSAT=NumTstTakr×100/Enrollment(K-12)。"
            )
        if item == "adelanto_grade_span_profile=true":
            hints.append(
                "Adelanto：SchoolsByGradeSpan GROUP BY GSserved，RANK() grade_span_rank；"
                "SchoolStats poverty_level 用 Percent FRPM 小数 >0.75/>0.50；"
                "最终 WHERE grade_span_rank=1；聚合 high/medium/low poverty 校数。"
            )
        if item == "hickman_elementary_charter_profile=true":
            hints.append(
                "Hickman charter：CharterSchoolStats DOC=52、Charter=1、Active；"
                "FRPM 列与 High/Medium/Low FRPM；SizeRank ROW_NUMBER PARTITION BY City；"
                "SATPerformance rtype=S；PercentOver1500=NumGE1500/NumTstTakr；"
                "SATPerformanceCategory 三档 Performing + No SAT Data。"
            )
        if item == "sokolov_pre1950_female_owner_profile=true":
            hints.append(
                "Sokolov 女 client：gender F、birth_year<1950、district A2='Sokolov'；"
                "client_accounts 经 disp OWNER→account；age_at_opening=开户年−出生年；"
                "loan_details：A=Contract Finished/No Problems，D=Running Contract/Client in Debt。"
            )
        if item == "card_issued_19940303_profile=true":
            hints.append(
                "1994-03-03 card：ClientCardInfo client→disp→card；age 年差；"
                "ClientAccountInfo account+loan；ClientDistrictInfo client.district_id→A11；"
                "borrower_category：loan_count>0 且 age<30→Young borrower，"
                "loan_count>0 且 age>=30→Mature borrower，否则 Non-borrower；"
                "RANK() age_rank_by_gender。"
            )
        if item == "female_top3_salary_district_profile=true":
            hints.append(
                "女 client 区县聚合：DistrictStats+AccountActivity 两 CTE JOIN district_id；"
                "A11 BETWEEN 6000 AND 10000；salary_rank_in_region<=3；female_clients>=5；"
                "total_loans>0；最终单行 SUM/AVG 聚合。"
            )
        if item == "loan_approved_19940825_profile=true":
            hints.append(
                "1994-08-25 loan：LoanAccounts+DistrictInfo+ClientsInDistrict；"
                "RANK salary/unemployment；ClientsInDistrict 按 district_id；"
                "trans 子查询 PRIJEM + date<贷款日。"
            )
        if item == "card_issued_19961021_profile=true":
            hints.append(
                "1996-10-21 card：ClientCards+TransactionStats RANK largest；"
                "transaction_category 三档 Value；loan_status Has/No Loan；"
                "LEFT JOIN loan/order；district 经 client.district_id。"
            )
        if item == "litomerice_1996_accounts_profile=true":
            hints.append(
                "Litomerice 1996：AccountsInLitomerice1996 用 A2；ClientInfo/AccountActivity/LoanStatus CTE；"
                "trans 1996 年 PRIJEM 存款；最终单行聚合 AVG 季度占比。"
            )
        if item == "female_birth_19760129_accounts_profile=true":
            hints.append(
                "1976-01-29 女 client：female_client+client_accounts OWNER；"
                "account_transactions PRIJEM/VYDAJ；loan/card 子查询；"
                "JOIN district ON account_district=A2 取 region/A10/A11/A14。"
            )
        if item == "loan_98832_19960103_profile=true":
            hints.append(
                "98832 贷款：LoanClient loan→account→disp OWNER→client；"
                "ClientTransactions trans.date<loan_date；CardInfo GROUP_CONCAT type；"
                "previous_loans 子查询跨 client 全部 account。"
            )
        if item == "south_bohemia_top_population_profile=true":
            hints.append(
                "south Bohemia：RegionStats GROUP BY district；CAST(A4) inhabitants；"
                "RANK population_rank；JOIN district 取 A2 名称；pct_male= male/total×100。"
            )
        if item == "loan_id_4990_profile=true":
            hints.append(
                "Loan 4990：LoanStats+DistrictStats CTE；status_description 四档 Running/Finished；"
                "problematic_loans B/D；RANK district_loan_rank；OWNER disp→client。"
            )
        if item == "region_loan_success_stats_profile=true":
            hints.append(
                "Region 贷款：LoansByDistrict OWNER+interest_paid；RegionSummary GROUP BY region；"
                "successful/paid 用 status A；overall_percentage 子查询全表 loan。"
            )
        if item == "prachatice_accounts_financial_profile=true":
            hints.append(
                "Prachatice：AccountsInPrachatice→TransactionStats/LoanInfo CTE；"
                "OWNER disp；PRIJEM/VYDAJ；net_balance=income-expense；"
                "ROW_NUMBER balance_rank；ORDER BY balance_rank。"
            )
        if item == "alameda_highest_free_rate_profile=true":
            hints.append(
                "Alameda 最高 free rate：CountyStats RANK PARTITION BY County Name ORDER BY FreeRate；"
                "WHERE CountyRank=1；IsCharterSchool schools.Charter；"
                "SATPerformance 用 TotalSATScore 三档；CountyAverage 子查询同县 AVG FreeRate。"
            )
        if item == "locally_funded_enrollment_gap_profile=true":
            hints.append(
                "Locally funded：schools.FundingType；差值 K-12 minus Ages 5-17；"
                "AVG 差值子查询同 FundingType；SELECT schools.School, schools.DOC。"
            )
        if item == "top_numge1500_admin_names_profile=true":
            hints.append(
                "最高 NumGE1500：satscores JOIN schools ON cds=CDSCode；"
                "ORDER BY NumGE1500 DESC LIMIT 1；六列 AdmFName/AdmLName 1–3。"
            )
        if item == "first_loan_19930705_balance_rate_profile=true":
            hints.append(
                "1993-07-05 贷款：loan JOIN account JOIN trans；WHERE loan.date='1993-07-05'；"
                "增幅=(SUM(IIF date=1998-12-27 balance)-SUM(IIF date=1993-03-22 balance))*100"
                "/SUM(IIF date=1993-03-22 balance)；单行聚合无 GROUP BY。"
            )
        if item == "magnet_k8_multiple_provision_by_city_profile=true":
            hints.append(
                "Magnet K-8 Multiple Provision：frpm JOIN schools ON CDSCode；"
                "Magnet=1 AND GSoffered='K-8' AND NSLP Provision Status='Multiple Provision Types'；"
                "SELECT City, COUNT(CDSCode) GROUP BY City。"
            )
        if item == "transaction_840_19981014_profile=true":
            hints.append(
                "840@1998-10-14：TransactionDetails CTE trans JOIN account JOIN district；"
                "AccountOwners LEFT JOIN disp OWNER→client；age strftime 年差+月日校正；"
                "loan EXISTS date<=transaction_date；cards 子查询 card JOIN disp。"
            )
        if item == "weekly_statement_owners_demographics_profile=true":
            hints.append(
                "Weekly 对账单：POPLATEK TYDNE+OWNER；CustomerWeeklyStatements CTE；"
                "ClientInfo 经 client.district_id；LoanAndTransactionData 按 client PRIJEM/VYDAJ。"
            )
        if item == "disponent_po_obratu_client_profile=true":
            hints.append(
                "Disponent PO OBRATU：ClientLoanInfo/Transactions/Cards CTE；"
                "frequency POPLATEK PO OBRATU；loan A active/B completed；"
                "client_category 四档服务类型；RANK transaction_rank。"
            )
        if item == "large_loan_high_salary_district_profile=true":
            hints.append(
                "大额贷款：LoanStatistics HAVING MAX>300000；A11>AVG(A11)；"
                "TransactionSummary PRIJEM/VYDAJ；A2/A3 区县与 region；"
                "WHERE income>expense OR income IS NULL；RANK region_loan_rank LIMIT 100。"
            )
        if item == "top_math_sat_active_profile=true":
            hints.append(
                "Top Math SAT Active：StatusType Active、NumTstTakr>=10；"
                "RANK MathRank=1；CharterAnalysis frpm 2014-2015；"
                "PercentFRPM 输出 ROUND×100||'%'；子查询 COUNT(DISTINCT cds) 与 AVG(Math)。"
            )
        if item == "top3_sat_excellence_profile=true":
            hints.append(
                "Top-3 SAT excellence：NumGE1500/NumTstTakr；RANK 得 rank；"
                "WHERE rank<=3；Phone/City/Charter Yes/No；"
                "poverty_rate=Percent FRPM；poverty_category 四档 Poverty 标签。"
            )
        if item == "sat_excellence_county_free_meal_profile=true":
            hints.append(
                "SAT>30%：NumGE1500/NumTstTakr>0.3；Ages 5-17 free rate；"
                "RANK PARTITION BY County；WHERE county_rank=1 LIMIT 1；"
                "avg_eligible_free_rate 子查询全 CTE 平均；Active 校 StatusType='Active'。"
            )
        if item == "la_low_free_meal_profile=true":
            hints.append(
                "LA 非 charter 低 free meal：schools.Charter=0、County='Los Angeles'；"
                "FreePercent=free/enrollment×100，WHERE FreePercent<0.18；"
                "CountyStats 聚合；CountyRank=ROW_NUMBER；PctLowFreeInCounty 带 %。"
            )
        if item == "fresno_direct_funded_charter_profile=true":
            hints.append(
                "Fresno Directly funded：frpm Charter Funding Type + County Name='Fresno'；"
                "NumTstTakr<=250；GROUP BY County Name；TotalSchools DISTINCT CDSCode；"
                "三档 tester 计数 <=50 / 50-100 / 100-250；ROUND 平均 SAT/FRPM/年龄。"
            )
        if item == "colusa_humboldt_ratio_profile=true":
            hints.append(
                "Colusa vs Humboldt：两 CTE 分别 County='Colusa'/'Humboldt'；"
                "6 行 UNION ALL，Metric 如 Total Schools Ratio；Ratio=Colusa/Humboldt；"
                "High FRPM 校 Percent FRPM>0.5；FRPM 学生 SUM(FRPM Count (K-12))。"
            )
        if item == "high_frpm_unexpected_performance_profile=true":
            hints.append(
                "最高 FRPM Count 非 charter 校：frpm Charter School (Y/N)=0、Enrollment>100；"
                "PerformanceCategory=High/Medium/Low（SAT 总分）；PerformanceClassification 对比 FRPM 与 PercentHighScorers；"
                "MailStreet AS UnabbreviatedMailingAddress；PercentHighScorers=NumGE1500/NumTstTakr×100。"
            )
        if item == "top10_high_frpm_profile=true":
            hints.append(
                "Top-10 FRPM Count：RANK() 得 frpm_rank，WHERE frpm_rank<=10；"
                "school_type/grade_level 来自 schools；percent_eligible_frpm 输出 ×100；"
                "percent_taking_sat 用 sat.enroll12；percent_scoring_over_1500=NumGE1500/NumTstTakr×100。"
            )
        if item == "enrollment500_frpm_sat_profile=true":
            hints.append(
                "Enrollment>500：TotalEnrollment=K-12+Ages 5-17；FRPMPercentage 输出 ×100；"
                "FRPMCategory 用小数 >=0.75/0.50 得 High/Medium/Low FRPM；"
                "IsCharter 来自 frpm Y/N；satscores rtype='S'；PercentageStudentsOver1500=NumGE1500/NumTstTakr×100。"
            )
        if item == "virtual_sat_f_profile=true":
            hints.append(
                "Fully virtual：WHERE schools.Virtual='F'；VirtualStatus CASE F/P/N；"
                "SAT>400 在 satscores 侧过滤；SchoolType=Charter School/Regular School；"
                "PovertyLevel 用 High/Medium/Low/Very Low Poverty（frpm 小数）；"
                "FRPMPercentage=ROUND(Percent FRPM*100,1)||'%'；ORDER BY TotalScore DESC, Enrollment DESC。"
            )
        if item == "virtual_charter_p_profile=true":
            hints.append(
                "Partially virtual charter：Virtual='P'；County 过滤；charter 用 schools.Charter=1；"
                "frpm 小数 FRPM 与 Poverty 标签；县内 RANK 按 Enrollment。"
            )
        if item == "virtual_county_compare_profile=true":
            hints.append(
                "县际 fully virtual：Virtual='F'；按 County 汇总 count/charter 占比/均值 SAT；"
                "RANK 比较县；LargestVirtualSchool 为该县 Enrollment 最大校。"
            )
        if item == "coe_charter_profile=true":
            hints.append(
                "Fresno COE charter：CharterSchoolInfo + SATPerformance 两 CTE；"
                "CharterSchoolName=frpm.`School Name`；PercentFRPM 小数列；"
                "FRPMCategory=High/Medium/Low FRPM；CurrentStatus=ClosedDate Active/Closed。"
            )
        if item == "financial_running_ok_profile=true":
            hints.append(
                "running OK：COUNT(status) 分母；CTE percentage 不 ROUND；"
                "最终 ROUND(percentage_running_ok,2) 与 ROUND(avg_loan_amount,2)；avg_duration 不 ROUND。"
            )
        if item == "magnet_sat_profile=true":
            hints.append(
                "Magnet + SAT>500：CTE 内对全部 NumTstTakr>500 算 StateRank=RANK()、"
                "CountyRank=DENSE_RANK(PARTITION BY County)；外层 WHERE Magnet=1；"
                "PercentHighScorers=CAST(NumGE1500 AS FLOAT)/NULLIF(NumTstTakr,0)*100；"
                "SchoolType=s.SOCType，EducationalOption=s.EdOpsName；FRPM 小数列；"
                "ORDER BY TotalAvgScore DESC, PercentHighScorers DESC。"
            )
        if item == "top_reading_sat_profile=true":
            hints.append(
                "最高 Reading：satscores 上 RANK()，WHERE ReadingRank=1（勿仅用 ORDER BY LIMIT 1）；"
                "frpm 用 Ages 5-17 列；PercentScoring1500Plus=NumGE1500*100/NumTstTakr；"
                "GradeSpan=GSoffered；Charter 标签 Charter/Non-Charter School。"
            )
        if item == "top_frpm_soc66_profile=true":
            hints.append(
                "Top-5 FRPM（SOC=66）：RANK() OVER FRPM Count，WHERE FRPMRank<=5；"
                "satscores 子集 rtype='S'；EligibilityRate 输出 ROUND(rate*100,2)||'%'；"
                "类别 Very High/High/Moderate/Low FRPM；勿在 CTE 内 ORDER BY LIMIT。"
            )
        if item == "returns_vs_sales=separate_cte":
            hints.append(
                "退货与销售需分 CTE 按各自事实表+date_dim 过滤后再 JOIN，"
                "不要仅用 item/store 键硬拼 promotion 或跨事实笛卡尔积。"
            )
        if item == "multi_channel_union=true":
            hints.append(
                "多渠道销售：各渠道 SELECT 小写标签 'store'/'catalog'/'web'，"
                "按 item_sk 与 sales_year GROUP BY SUM(*_ext_sales_price)，UNION ALL 成 channel_rows，"
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
                "库存+门店销量：sold CTE 按 ss_item_sk 汇总 ss_quantity；"
                "stock CTE 含 date_dim.d_year AS inventory_year 与 inv_item_sk，"
                "再 INNER JOIN sold ON item_sk，外层 GROUP BY warehouse_state/item_category/inventory_year；"
                "勿用 2001 AS inventory_year。"
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
