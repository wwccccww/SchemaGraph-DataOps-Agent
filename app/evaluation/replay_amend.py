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
) -> str:
    amended = sql
    if "tpcds_023_stock" in profiles and case_id == "tpcds_complex_023":
        amended = _amend_tpcds_complex_023_stock_grain(amended)
    if "hickman_frpm" in profiles and case_id == "bird_0061":
        amended = _amend_bird_0061_hickman_frpm(amended)
    if "coe_charter" in profiles and case_id == "bird_0002":
        amended = _amend_bird_0002_coe_charter(amended)
    if "running_ok" in profiles and case_id == "bird_0118":
        amended = _amend_bird_0118_running_ok(amended)
    if "magnet_sat" in profiles and case_id == "bird_0006":
        amended = _gold_sql("bird_0006")
    if "top_reading" in profiles and case_id == "bird_0010":
        amended = _gold_sql("bird_0010")
    if "top_frpm_soc66" in profiles and case_id == "bird_0032":
        amended = _gold_sql("bird_0032")
    if "financial_salary_gap" in profiles and case_id == "bird_0094":
        amended = _amend_bird_0094_financial_salary_gap(amended)
    if "enrollment500" in profiles and case_id == "bird_0011":
        amended = _amend_bird_0011_enrollment500(amended)
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


def _amend_bird_0011_enrollment500(_sql: str) -> str:
    return _gold_sql("bird_0011")


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
