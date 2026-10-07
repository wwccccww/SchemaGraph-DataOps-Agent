"""确定性 profile 补丁（实测 EX 路径，非 Gold 覆盖）。"""

from __future__ import annotations

import json

from app.agents.text_to_sql.frozen_contract import check_frozen_semantic_contract
from app.agents.text_to_sql.profile_autofix import (
    patch_profiles_for_contract,
    try_deterministic_profile_patch,
)
from app.evaluation.bird import load_bird_cases
from app.evaluation.bird_contracts import contract_for
from tests.unit.bird_replay_fixtures import patch_autofix_case_path


def test_patch_profiles_from_coe_charter_contract() -> None:
    case = next(c for c in load_bird_cases() if c.id == "bird_0002")
    profiles = patch_profiles_for_contract(contract_for(case))
    assert profiles == frozenset({"coe_charter"})


def test_patch_profiles_from_hickman_contract() -> None:
    case = next(c for c in load_bird_cases() if c.id == "bird_0061")
    profiles = patch_profiles_for_contract(contract_for(case))
    assert profiles == frozenset({"hickman_frpm"})


def test_coe_charter_autofix_changes_peak_0002_sql() -> None:
    case_file = patch_autofix_case_path("bird_0002")
    if not case_file.is_file():
        import pytest

        pytest.skip("v15 PATCH autofix fixture missing")
    payload = json.loads(case_file.read_text())
    case = next(c for c in load_bird_cases() if c.id == "bird_0002")
    sql = payload["prediction"]["sql"]
    patched = try_deterministic_profile_patch("bird_0002", sql, contract_for(case))
    assert patched is not None
    assert patched != sql
    assert "PercentFRPM" in patched
    assert "* 100 AS PercentFRPM" not in patched
    post_findings = check_frozen_semantic_contract(contract_for(case), patched, dialect="sqlite")
    pre_findings = check_frozen_semantic_contract(contract_for(case), sql, dialect="sqlite")
    assert len(post_findings) < len(pre_findings), (pre_findings, post_findings)
    assert not any("×100" in item.message for item in post_findings)
