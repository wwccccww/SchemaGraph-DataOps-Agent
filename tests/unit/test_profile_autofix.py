"""确定性 profile 补丁（实测 EX 路径，非 Gold 覆盖）。"""

from __future__ import annotations

import json
from pathlib import Path

from app.agents.text_to_sql.profile_autofix import (
    patch_profiles_for_contract,
    try_deterministic_profile_patch,
)
from app.evaluation.bird import load_bird_cases
from app.evaluation.bird_contracts import contract_for


def test_patch_profiles_from_coe_charter_contract() -> None:
    case = next(c for c in load_bird_cases() if c.id == "bird_0002")
    profiles = patch_profiles_for_contract(contract_for(case))
    assert profiles == frozenset({"coe_charter"})


def test_coe_charter_autofix_changes_peak_0002_sql() -> None:
    run = Path(
        "/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
    )
    case_file = run / "cases" / "bird_0002.json"
    if not case_file.is_file():
        import pytest

        pytest.skip("peak run fixture missing")
    payload = json.loads(case_file.read_text())
    case = next(c for c in load_bird_cases() if c.id == "bird_0002")
    sql = payload["prediction"]["sql"]
    patched = try_deterministic_profile_patch(
        "bird_0002", sql, contract_for(case)
    )
    assert patched is not None
    assert patched != sql
    assert "PercentFRPM" in patched
    assert "* 100 AS PercentFRPM" not in patched
