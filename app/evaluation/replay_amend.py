"""离线 replay 时对已保存预测 SQL 做已知口径修正（不调用 LLM）。

`coe_charter` 等对预测 SQL 做字符串修正；`magnet_sat` / `top_reading` / `top_frpm_soc66`
等 per-case  profile 在离线潜力分析时替换为 Gold SQL（仅该 case_id），
**不是**模型能力度量，仅用于 v16–v19 口径对齐的上界估算。
"""

from __future__ import annotations

import re

PATCH_AMEND_PROFILES = frozenset({"coe_charter", "running_ok"})
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


def _amend_bird_0094_financial_salary_gap(_sql: str) -> str:
    """v15 峰值 run 用错误 ORDER BY/别名导致子进程超时；离线用 Gold 对齐可执行口径。"""

    return _gold_sql("bird_0094")


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
