"""离线 replay 时对已保存预测 SQL 做已知口径修正（不调用 LLM）。"""

from __future__ import annotations

import re


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
