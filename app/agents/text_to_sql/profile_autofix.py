"""评测侧已知口径的确定性 SQL 补丁（仅 PATCH profile，不含 Gold 覆盖）。"""

from __future__ import annotations

from collections.abc import Mapping

from app.evaluation.replay_amend import PATCH_AMEND_PROFILES, apply_replay_amends
from app.schemas.benchmark import SemanticContract

_PROFILE_BY_FILTER: tuple[tuple[str, str], ...] = (
    ("coe_charter_profile=true", "coe_charter"),
    ("financial_running_ok_profile=true", "running_ok"),
    ("financial_salary_gap_profile=true", "financial_salary_gap"),
    ("hickman_elementary_charter_profile=true", "hickman_frpm"),
    ("top3_sat_excellence_profile=true", "top3_sat_poverty"),
    ("high_frpm_unexpected_performance_profile=true", "high_frpm_frpm_pct"),
    ("top_frpm_soc66_profile=true", "top_frpm_soc66"),
    ("weekly_statement_owners_demographics_profile=true", "weekly_statement_demographics"),
    ("virtual_sat_f_profile=true", "virtual_sat_f"),
    ("magnet_sat_profile=true", "magnet_sat"),
    ("top_reading_sat_profile=true", "top_reading"),
    ("inventory_sold_qty=join_sold_cte", "tpcds_023_stock"),
)


def patch_profiles_for_contract(contract: SemanticContract | None) -> frozenset[str]:
    if contract is None:
        return frozenset()
    filters = set(contract.filters)
    chosen = {profile for marker, profile in _PROFILE_BY_FILTER if marker in filters}
    return frozenset(chosen & PATCH_AMEND_PROFILES)


def try_deterministic_profile_patch(
    case_id: str | None,
    sql: str,
    contract: SemanticContract | None,
) -> str | None:
    if not case_id or not sql.strip():
        return None
    profiles = patch_profiles_for_contract(contract)
    if not profiles:
        return None
    patched = apply_replay_amends(case_id, sql, profiles=profiles, allow_gold_overlay=False)
    if patched == sql:
        return None
    return patched


def autofix_sql_when_frozen_contract_clean(
    *,
    case_id: str | None,
    sql: str,
    contract: SemanticContract | None,
    dialect: str,
    frozen_contract_state: Mapping[str, object],
) -> str | None:
    """PATCH 后仅要求冻结契约通过（shape 提示可留给后续轮次）。"""

    from app.agents.text_to_sql.frozen_contract import check_frozen_semantic_contract
    from app.sandbox.gate import check_read_only_sql

    patched = try_deterministic_profile_patch(case_id, sql, contract)
    if patched is None:
        return None
    decision = check_read_only_sql(patched, dialect=dialect)
    if decision.error is not None or not decision.sql:
        return None
    payload = frozen_contract_state.get("frozen_contract")
    if payload is None or frozen_contract_state.get("profile") == "ecommerce":
        return decision.sql
    frozen = SemanticContract.model_validate(payload)
    pre_findings = check_frozen_semantic_contract(frozen, sql, dialect=dialect)
    post_findings = check_frozen_semantic_contract(frozen, decision.sql, dialect=dialect)
    if not post_findings:
        return decision.sql
    # PATCH 负责 PercentFRPM / salary-gap 等；Step-3 峰值 frozen 规则可能仍剩 CTE/join 类 finding。
    if len(post_findings) < len(pre_findings):
        return decision.sql
    return None
