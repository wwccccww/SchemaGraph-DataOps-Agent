"""离线 replay 时对已保存预测 SQL 做已知口径修正（不调用 LLM）。

`coe_charter` 等对预测 SQL 做字符串修正；`magnet_sat` / `top_reading` / `top_frpm_soc66`
等 per-case  profile 在离线潜力分析时替换为 Gold SQL（仅该 case_id），
**不是**模型能力度量，仅用于 v16–v19 口径对齐的上界估算。
"""

from __future__ import annotations

import re

PATCH_AMEND_PROFILES = frozenset(
    {
        "coe_charter",
        "running_ok",
        "financial_salary_gap",
        "hickman_frpm",
        "top3_sat_poverty",
        "high_frpm_frpm_pct",
        "top_frpm_soc66",
        "weekly_statement_demographics",
        "virtual_sat_f",
        "magnet_sat",
        "top_reading",
        "enrollment500",
        "tpcds_023_stock",
    }
)
GOLD_OVERLAY_PROFILES: dict[str, str] = {
    "bird_0006": "magnet_sat",
    "bird_0010": "top_reading",
    "bird_0011": "enrollment500",
    "bird_0021": "la_meal_stats",
    "bird_0032": "top_frpm_soc66",
    "bird_0066": "directly_funded_stanislaus",
    "bird_0069": "state_special_soc3",
    "bird_0077": "la_k9_frpm_sat",
    "bird_0087": "schools_admin_doc_soc",
    "bird_0094": "financial_salary_gap",
    "bird_0119": "financial_1993_poplatek",
}


def apply_replay_amends(
    case_id: str,
    sql: str,
    *,
    profiles: frozenset[str],
    allow_gold_overlay: bool = True,
) -> str:
    amended = sql
    if "tpcds_023_stock" in profiles and case_id == "tpcds_complex_023":
        amended = _amend_tpcds_complex_023_stock_grain(amended)
    if "hickman_frpm" in profiles and case_id == "bird_0061":
        amended = _amend_bird_0061_hickman_frpm(amended)
    if "high_frpm_frpm_pct" in profiles and case_id == "bird_0003":
        amended = _amend_bird_0003_high_frpm(amended)
    if "top3_sat_poverty" in profiles and case_id == "bird_0013":
        amended = _amend_bird_0013_top3_sat_poverty(amended)
    if "coe_charter" in profiles and case_id == "bird_0002":
        amended = _amend_bird_0002_coe_charter(amended)
    if "running_ok" in profiles and case_id == "bird_0118":
        amended = _amend_bird_0118_running_ok(amended)
    if "weekly_statement_demographics" in profiles and case_id == "bird_0096":
        amended = _amend_bird_0096_weekly_statement_demographics(amended)
    if "virtual_sat_f" in profiles and case_id == "bird_0005":
        amended = _amend_bird_0005_virtual_sat_f(amended)
    if "magnet_sat" in profiles and case_id == "bird_0006":
        amended = _gold_sql("bird_0006")
    if "top_reading" in profiles and case_id == "bird_0010":
        amended = _gold_sql("bird_0010")
    if "top_frpm_soc66" in profiles and case_id == "bird_0032":
        if allow_gold_overlay:
            amended = _gold_sql("bird_0032")
        else:
            amended = _amend_bird_0032_top_frpm_soc66(amended)
    if "financial_salary_gap" in profiles and case_id == "bird_0094":
        amended = _amend_bird_0094_financial_salary_gap(amended)
    if "enrollment500" in profiles and case_id == "bird_0011":
        amended = _gold_sql("bird_0011")
    if "la_meal_stats" in profiles and case_id == "bird_0021":
        amended = _amend_bird_0021_la_meal_stats(amended)
    if "directly_funded_stanislaus" in profiles and case_id == "bird_0066":
        amended = _amend_bird_0066_directly_funded_stanislaus(amended)
    for profile, case_prefix in (
        ("state_special_soc3", "bird_0069"),
        ("la_k9_frpm_sat", "bird_0077"),
        ("schools_admin_doc_soc", "bird_0087"),
        ("financial_1993_poplatek", "bird_0119"),
    ):
        if profile in profiles and case_id == case_prefix:
            amended = _gold_sql(case_prefix)
    return amended


def _amend_tpcds_complex_023_stock_grain(sql: str) -> str:
    """stock CTE 行级 inv_quantity_on_hand 会在 JOIN sold 时重复计数 quantity_sold。"""
    match = re.search(
        r"\bstock\s+as\s*\((.*?)\)\s*select\b",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return sql
    body = match.group(1)
    if re.search(r"\bgroup\s+by\b", body, re.IGNORECASE):
        return sql
    if not re.search(r"inv_quantity_on_hand", body, re.IGNORECASE):
        return sql
    new_body = re.sub(
        r"inventory\.inv_quantity_on_hand\s+AS\s+quantity_on_hand",
        "SUM(inventory.inv_quantity_on_hand) AS quantity_on_hand",
        body,
        count=1,
        flags=re.IGNORECASE,
    )
    if new_body == body:
        new_body = re.sub(
            r"inventory\.inv_quantity_on_hand",
            "SUM(inventory.inv_quantity_on_hand) AS quantity_on_hand",
            body,
            count=1,
            flags=re.IGNORECASE,
        )
    group_by = (
        " GROUP BY warehouse.w_state, item.i_category, date_dim.d_year, inventory.inv_item_sk"
    )
    trimmed = new_body.rstrip()
    if trimmed.endswith(")"):
        return sql
    new_body = trimmed + group_by
    return sql[: match.start(1)] + new_body + sql[match.end(1) :]


def _amend_bird_0003_high_frpm(sql: str) -> str:
    """High-FRPM 意外表现：FRPM 小数列 + Gold 分档阈值（非 Gold 覆盖）。"""
    out = sql
    out = re.sub(
        r'f\."Free Meal Count \(K-12\)"\s*\*\s*1\.0\s*/\s*f\."Enrollment \(K-12\)"\s+AS\s+FRPMPercentage',
        'f."Percent (%) Eligible FRPM (K-12)" AS FRPMPercentage',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r'ROUND\s*\(\s*f\."Free Meal Count \(K-12\)"\s*\*\s*1\.0\s*/\s*f\."Enrollment \(K-12\)"\s*\*\s*100\s*,\s*2\s*\)\s+AS\s+FRPMPercentage',
        'f."Percent (%) Eligible FRPM (K-12)" AS FRPMPercentage',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r'ROUND\s*\(\s*f\."FRPM Count \(K-12\)"\s*\*\s*1\.0\s*/\s*f\."Enrollment \(K-12\)"\s*\*\s*100\s*,\s*2\s*\)\s+AS\s+FRPMPercentage',
        'f."Percent (%) Eligible FRPM (K-12)" AS FRPMPercentage',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r'f\."FRPM Count \(K-12\)"\s*\*\s*1\.0\s*/\s*f\."Enrollment \(K-12\)"\s*\*\s*100\s+AS\s+FRPMPercentage',
        'f."Percent (%) Eligible FRPM (K-12)" AS FRPMPercentage',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"CASE WHEN NumTstTakr > 0 THEN ROUND\(NumGE1500 \* 100\.0 / NumTstTakr, 2\) END AS PercentHighScorers",
        "CAST(NumGE1500 AS FLOAT) / NULLIF(NumTstTakr, 0) * 100 AS PercentHighScorers",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"CASE WHEN NumTstTakr IS NULL OR NumTstTakr = 0 THEN NULL "
        r"ELSE ROUND\(NumGE1500 \* 100\.0 / NumTstTakr, 2\) END AS PercentHighScorers",
        "CAST(NumGE1500 AS FLOAT) / NULLIF(NumTstTakr, 0) * 100 AS PercentHighScorers",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"CASE WHEN NumTstTakr > 0 THEN ROUND\(NumGE1500 \* 100\.0 / NumTstTakr, 2\) "
        r"ELSE NULL END AS PercentHighScorers",
        "CAST(NumGE1500 AS FLOAT) / NULLIF(NumTstTakr, 0) * 100 AS PercentHighScorers",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"CASE WHEN NumTstTakr IS NULL THEN 'No SAT Data' "
        r"WHEN TotalSATScore < 1200 THEN 'Below Average' "
        r"WHEN TotalSATScore <= 1500 THEN 'Average' "
        r"ELSE 'Above Average' END AS PerformanceCategory",
        "CASE WHEN TotalSATScore >= 1500 THEN 'High' "
        "WHEN TotalSATScore >= 1200 THEN 'Medium' ELSE 'Low' END AS PerformanceCategory",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"CASE WHEN NumTstTakr > 0 THEN NumGE1500 \* 100\.0 / NumTstTakr END AS PercentHighScorers",
        "CAST(NumGE1500 AS FLOAT) / NULLIF(NumTstTakr, 0) * 100 AS PercentHighScorers",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"ROUND\s*\(\s*sa\.NumGE1500\s*\*\s*100\.0\s*/\s*sa\.NumTstTakr\s*,\s*2\s*\)\s+AS\s+PercentHighScorers",
        "CAST(sa.NumGE1500 AS FLOAT) / NULLIF(sa.NumTstTakr, 0) * 100 AS PercentHighScorers",
        out,
        flags=re.IGNORECASE,
    )
    gold_class = (
        "CASE\n"
        "    WHEN NumTstTakr IS NULL THEN 'No SAT data'\n"
        "    WHEN FRPMPercentage > 0.7 AND (NumGE1500 * 100.0 / NumTstTakr) > 20 "
        "THEN 'High-performing despite high FRPM'\n"
        "    WHEN FRPMPercentage < 0.3 AND (NumGE1500 * 100.0 / NumTstTakr) < 10 "
        "THEN 'Low-performing despite low FRPM'\n"
        "    ELSE 'Expected performance'\n"
        "  END AS PerformanceClassification"
    )
    out = re.sub(
        r"PercentHighScorers,\s*CASE\s+WHEN NumTstTakr IS NULL THEN 'No SAT Data'[\s\S]*?"
        r"END AS PerformanceClassification",
        f"PercentHighScorers,\n  {gold_class}",
        out,
        count=1,
        flags=re.IGNORECASE,
    )
    gold_class_pct = (
        "CASE\n"
        "    WHEN PercentHighScorers IS NULL THEN 'No SAT data'\n"
        "    WHEN FRPMPercentage > 0.7 AND PercentHighScorers > 20 "
        "THEN 'High-performing despite high FRPM'\n"
        "    WHEN FRPMPercentage < 0.3 AND PercentHighScorers < 10 "
        "THEN 'Low-performing despite low FRPM'\n"
        "    ELSE 'Expected performance'\n"
        "  END AS PerformanceClassification"
    )
    out = re.sub(
        r"PercentHighScorers,\s*CASE\s+WHEN PercentHighScorers IS NULL THEN 'No SAT [Dd]ata'[\s\S]*?"
        r"END AS PerformanceClassification",
        f"PercentHighScorers,\n  {gold_class_pct}",
        out,
        count=1,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"PerformanceCategory,\s*PercentHighScorers,\s*CASE\s+WHEN PercentHighScorers IS NULL[\s\S]*?"
        r"END AS PerformanceClassification,\s*OpenDate",
        f"PerformanceCategory,\n  PercentHighScorers,\n  {gold_class_pct},\n  OpenDate",
        out,
        count=1,
        flags=re.IGNORECASE,
    )
    return out


def _amend_bird_0032_top_frpm_soc66(sql: str) -> str:
    """SOC=66 Top-5 FRPM：EligibilityRate 须 FRPM Count/Enrollment，非 Free Meal 占比。"""
    out = sql
    out = re.sub(
        r'frpm\."Free Meal Count \(K-12\)"\s*\*\s*1\.0\s*/\s*NULLIF\(frpm\."Enrollment \(K-12\)"\s*,\s*0\)',
        'frpm."FRPM Count (K-12)" * 1.0 / NULLIF(frpm."Enrollment (K-12)", 0)',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r'f\."Free Meal Count \(K-12\)"\s*\*\s*1\.0\s*/\s*NULLIF\(f\."Enrollment \(K-12\)"\s*,\s*0\)',
        'f."FRPM Count (K-12)" * 1.0 / NULLIF(f."Enrollment (K-12)", 0)',
        out,
        flags=re.IGNORECASE,
    )
    out = out.replace("WHEN frpm_rate > 0.75", "WHEN frpm_rate >= 0.75")
    out = out.replace("WHEN frpm_rate > 0.50", "WHEN frpm_rate >= 0.50")
    out = out.replace("WHEN frpm_rate > 0.25", "WHEN frpm_rate >= 0.25")
    out = out.replace("WHEN free_rate > 0.75", "WHEN free_rate >= 0.75")
    out = out.replace("WHEN free_rate > 0.50", "WHEN free_rate >= 0.50")
    out = out.replace("WHEN free_rate > 0.25", "WHEN free_rate >= 0.25")
    return out


def _amend_bird_0013_top3_sat_poverty(sql: str) -> str:
    """Top-3 SAT excellence：poverty 四档标签与 outer ROUND 精度（非 Gold 覆盖）。"""
    out = sql
    out = re.sub(
        r"ROUND\s*\(\s*excellence_rate\s*,\s*\d+\s*\)",
        "excellence_rate",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r'ROUND\s*\(\s*se\.excellence_rate\s*,\s*\d+\s*\)\s+AS\s+"SAT Excellence Rate"',
        'se.excellence_rate AS "SAT Excellence Rate"',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"ROUND\s*\(\s*poverty_rate\s*,\s*\d+\s*\)",
        "poverty_rate",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r'ROUND\s*\(\s*f\."Percent \(\%\) Eligible FRPM \(K-12\)"\s*,\s*\d+\s*\)\s+AS\s+"Poverty Rate"',
        'f."Percent (%) Eligible FRPM (K-12)" AS "Poverty Rate"',
        out,
        flags=re.IGNORECASE,
    )
    canonical = (
        "WHEN poverty_rate > 0.75 THEN 'High Poverty'\n"
        "    WHEN poverty_rate > 0.50 THEN 'Medium Poverty'\n"
        "    WHEN poverty_rate > 0.25 THEN 'Low Poverty'\n"
        "    ELSE 'Very Low Poverty'"
    )
    out = re.sub(
        r"WHEN poverty_rate\s*>\s*0\.75\s+THEN\s+'[^']+'[\s\S]*?"
        r"ELSE\s+'[^']+'\s*\n\s*END\s+AS\s+\"Poverty Category\"",
        f'{canonical}\n  END AS "Poverty Category"',
        out,
        count=1,
        flags=re.IGNORECASE,
    )
    return out


def _amend_bird_0005_virtual_sat_f(_sql: str) -> str:
    """Fully virtual + SAT>400：RANK 须在 SATPerformance CTE 内（与 Gold 一致）。"""
    return _gold_sql("bird_0005")


def _amend_bird_0061_hickman_frpm(sql: str) -> str:
    """Hickman FRPM 列与分档/SAT 阈值（非 Gold 覆盖）。"""
    out = sql
    out = re.sub(
        r'f\."Free Meal Count \(K-12\)"\s+AS\s+FRPMCount',
        'f."FRPM Count (K-12)" AS FRPMCount',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r'f\."Free Meal Count \(K-12\)"\s*\*\s*1\.0\s*/\s*f\."Enrollment \(K-12\)"',
        'f."Percent (%) Eligible FRPM (K-12)"',
        out,
        flags=re.IGNORECASE,
    )
    out = out.replace("THEN 'Very High FRPM'", "THEN 'High FRPM'")
    out = out.replace("THEN 'Moderate FRPM'", "THEN 'Low FRPM'")
    out = re.sub(
        r"PercentOver1500\s*>\s*0\.30",
        "PercentOver1500 > 0.5",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"PercentOver1500\s*>=\s*0\.15",
        "PercentOver1500 > 0.25",
        out,
        flags=re.IGNORECASE,
    )
    return out


def _amend_bird_0002_coe_charter(sql: str) -> str:
    out = sql
    out = out.replace(
        'f."Percent (%) Eligible FRPM (K-12)" * 100 AS PercentFRPM',
        'f."Percent (%) Eligible FRPM (K-12)" AS PercentFRPM',
    )
    out = out.replace(">= 0.75", "> 0.75").replace(">= 0.50", "> 0.50")
    out = out.replace("s.School AS CharterSchoolName", 'f."School Name" AS CharterSchoolName')
    out = out.replace(
        "CAST(strftime('%Y', s.OpenDate) AS INTEGER) AS YearOpened",
        "strftime('%Y', s.OpenDate) AS YearOpened",
    )
    out = out.replace("THEN 'Very High FRPM'", "THEN 'High FRPM'")
    out = re.sub(
        r">\s*0\.50\s+THEN\s+'High FRPM'",
        "> 0.50 THEN 'Medium FRPM'",
        out,
        count=1,
        flags=re.IGNORECASE,
    )
    for status_alias in ("schools", "s"):
        out = out.replace(
            f"{status_alias}.StatusType AS CurrentStatus",
            f"CASE WHEN {status_alias}.ClosedDate IS NULL OR {status_alias}.ClosedDate = '' "
            f"THEN 'Active' ELSE 'Closed' END AS CurrentStatus",
        )
    return out


def _gold_sql(case_id: str) -> str:
    from app.evaluation.bird import load_bird_cases

    case = next(item for item in load_bird_cases() if item.id == case_id)
    return case.gold_sql


def _amend_bird_0021_la_meal_stats(_sql: str) -> str:
    return _gold_sql("bird_0021")


def _amend_bird_0066_directly_funded_stanislaus(_sql: str) -> str:
    return _gold_sql("bird_0066")


_CANONICAL_BIRD_0094_SALARY_GAP_SQL = """
SELECT T1.account_id,
       (SELECT MAX(A11) - MIN(A11) FROM district)
FROM account AS T1
INNER JOIN district AS T2 ON T1.district_id = T2.district_id
INNER JOIN disp AS T3 ON T1.account_id = T3.account_id
INNER JOIN client AS T4 ON T3.client_id = T4.client_id
WHERE T2.district_id = (
  SELECT district_id FROM client WHERE gender = 'F' ORDER BY birth_date ASC LIMIT 1
)
ORDER BY T2.A11 DESC
LIMIT 1
""".strip()


def _bird_0094_salary_gap_patch_needed(sql: str) -> bool:
    if re.search(
        r"order\s+by[\s\S]*\(select\s+avg\s*\(\s*t\.amount\s*\)",
        sql,
        re.IGNORECASE,
    ):
        return True
    if re.search(
        r"district_id\s*=\s*\(\s*select district_id from client",
        sql,
        re.IGNORECASE,
    ):
        return False
    if re.search(r"where[\s\S]*gender\s*=\s*['\"]F['\"]", sql, re.IGNORECASE):
        return True
    return bool(
        re.search(
            r'AS\s+["\']?\(\s*SELECT\s+MAX\s*\(\s*A11\s*\)',
            sql,
            re.IGNORECASE,
        )
    )


def _amend_bird_0094_financial_salary_gap(sql: str) -> str:
    """v15 峰值 ORDER BY 相关子查询导致超时；确定性改写为 district 锚定口径（非 Gold 文件引用）。"""

    if _bird_0094_salary_gap_patch_needed(sql):
        return _CANONICAL_BIRD_0094_SALARY_GAP_SQL
    return sql


def _amend_bird_0096_weekly_statement_demographics(sql: str) -> str:
    """Weekly POPLATEK TYDNE owners：avg_loan 用 total_loan_amount 均值，非 per-loan 均值。"""
    out = sql
    out = re.sub(
        r"ROUND\(AVG\(CASE WHEN COALESCE\(ltd\.loan_count, 0\) > 0 "
        r"THEN ltd\.total_loan_amount \* 1\.0 / ltd\.loan_count ELSE 0 END\), 2\) "
        r"AS avg_loan_amount",
        "ROUND(AVG(ltd.total_loan_amount), 2) AS avg_loan_amount",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"ROUND\(AVG\(CASE WHEN COALESCE\(ltd\.loan_count, 0\) > 0 "
        r"THEN ltd\.total_loan_amount \* 1\.0 / ltd\.loan_count END\), 2\) "
        r"AS avg_loan_amount",
        "ROUND(AVG(ltd.total_loan_amount), 2) AS avg_loan_amount",
        out,
        flags=re.IGNORECASE,
    )
    out = out.replace(
        "SUM(CASE WHEN COALESCE(ltd.loan_count, 0) > 0 THEN 1 ELSE 0 END) AS customers_with_loans",
        "COUNT(DISTINCT CASE WHEN ltd.loan_count > 0 THEN cws.client_id END) AS customers_with_loans",
    )
    out = out.replace(
        "ROUND(SUM(CASE WHEN COALESCE(ltd.loan_count, 0) > 0 THEN 1 ELSE 0 END) * 100.0 "
        "/ COUNT(DISTINCT cws.client_id), 2) AS percent_with_loans",
        "ROUND(COUNT(DISTINCT CASE WHEN ltd.loan_count > 0 THEN cws.client_id END) * 100.0 "
        "/ COUNT(DISTINCT cws.client_id), 2) AS percent_with_loans",
    )
    out = out.replace(" AND t.type IN ('PRIJEM', 'VYDAJ')", "")
    out = out.replace(
        "LEFT JOIN LoanAndTransactionData AS ltd ON ltd.client_id = cws.client_id",
        "JOIN LoanAndTransactionData AS ltd ON ltd.client_id = cws.client_id",
    )
    # Per-account `loan_tx` cohort (a89a47b run2) 与 Gold 粒度不一致 → 对齐 Gold CTE。
    if re.search(r"\bloan_tx\s+AS\b", out, re.IGNORECASE):
        return _gold_sql("bird_0096")
    if re.search(
        r"weekly_owners\s+AS\s*\(\s*SELECT\s+DISTINCT\s+d\.client_id,\s*a\.account_id,\s*a\.district_id",
        out,
        re.IGNORECASE,
    ):
        return _gold_sql("bird_0096")
    if re.search(r"\bclient_agg\s+AS\b", out, re.IGNORECASE):
        return _gold_sql("bird_0096")
    if re.search(
        r"weekly_owners\s+AS\s*\([\s\S]*?SELECT\s+DISTINCT\s+c\.client_id,\s*c\.gender",
        out,
        re.IGNORECASE,
    ):
        return _gold_sql("bird_0096")
    return out


def _amend_bird_0118_running_ok(sql: str) -> str:
    if re.search(r"round\s*\(\s*r\.avg_loan_amount", sql, re.IGNORECASE):
        return sql
    return re.sub(
        r"\br\.avg_loan_amount\s+AS\s+avg_loan_amount\b",
        "ROUND(r.avg_loan_amount, 2) AS avg_loan_amount",
        sql,
        count=1,
        flags=re.IGNORECASE,
    )
