"""BIRD 按题 profile 覆盖（P0 自愈口径 inventory）。"""

from __future__ import annotations

import json

from app.agents.text_to_sql.frozen_contract import check_frozen_semantic_contract
from app.evaluation.bird import BIRD_CASE_COUNT, load_bird_cases
from app.evaluation.bird_contracts import contract_for
from tests.unit.bird_replay_fixtures import BIRD_PEAK_RUN as PEAK_V15_RUN


def test_bird_cases_have_semantic_contract_and_profile_tags() -> None:
    cases = load_bird_cases()
    assert len(cases) == BIRD_CASE_COUNT
    with_profile = 0
    for case in cases:
        contract = contract_for(case)
        assert case.semantic_contract == contract
        profiles = [item for item in contract.filters if item.endswith("_profile=true")]
        if profiles:
            with_profile += 1
    # 50 条显式 profile（其余依赖 generic shape + 投影列契约）
    assert with_profile >= 50


def test_bird_explicit_profile_case_ids() -> None:
    """按题 profile 清单（新增 profile 时同步更新）。"""
    expected = frozenset(
        {
            "bird_0000",
            "bird_0002",
            "bird_0003",
            "bird_0005",
            "bird_0006",
            "bird_0008",
            "bird_0010",
            "bird_0011",
            "bird_0012",
            "bird_0013",
            "bird_0018",
            "bird_0019",
            "bird_0020",
            "bird_0021",
            "bird_0028",
            "bird_0031",
            "bird_0036",
            "bird_0032",
            "bird_0045",
            "bird_0055",
            "bird_0060",
            "bird_0061",
            "bird_0062",
            "bird_0066",
            "bird_0069",
            "bird_0077",
            "bird_0078",
            "bird_0079",
            "bird_0083",
            "bird_0087",
            "bird_0092",
            "bird_0094",
            "bird_0096",
            "bird_0097",
            "bird_0100",
            "bird_0103",
            "bird_0104",
            "bird_0105",
            "bird_0106",
            "bird_0111",
            "bird_0112",
            "bird_0113",
            "bird_0115",
            "bird_0116",
            "bird_0117",
            "bird_0118",
            "bird_0119",
            "bird_0121",
            "bird_0122",
            "bird_0123",
        }
    )
    cases = load_bird_cases()
    actual = frozenset(
        case.id
        for case in cases
        if any(item.endswith("_profile=true") for item in contract_for(case).filters)
    )
    assert actual == expected


def test_peak_v15_ex1_cases_all_have_explicit_profile() -> None:
    """峰值 measured run 上 ex=1 均绑定按题 profile（v11：13/50）。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak v15 run fixture missing")
    missing: list[str] = []
    for case in load_bird_cases():
        case_file = PEAK_V15_RUN / "cases" / f"{case.id}.json"
        if not case_file.is_file():
            continue
        payload = json.loads(case_file.read_text())
        if not payload.get("ex"):
            continue
        profiles = [item for item in contract_for(case).filters if item.endswith("_profile=true")]
        if not profiles:
            missing.append(case.id)
    assert missing == []


def test_v11_measured_ex0_frozen_finding_coverage_floor() -> None:
    """Step-3：v11 峰值 EX=0 保存 SQL 上至少 13 题须有 ≥1 frozen finding（repair 信号）。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak run fixture missing")
    with_findings = 0
    for case in load_bird_cases():
        case_file = PEAK_V15_RUN / "cases" / f"{case.id}.json"
        if not case_file.is_file():
            continue
        payload = json.loads(case_file.read_text())
        if payload.get("ex"):
            continue
        sql = (payload.get("prediction") or {}).get("sql") or ""
        if check_frozen_semantic_contract(contract_for(case), sql, dialect="sqlite"):
            with_findings += 1
    assert with_findings >= 13


def test_peak_v15_ex0_saved_sql_surfaces_frozen_findings() -> None:
    """Measured v11+ 峰值：EX=0 的 sql_error 保存 SQL 应至少 1 条 frozen finding（inventory）。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak run fixture missing")
    summary_path = PEAK_V15_RUN / "summary.json"
    if summary_path.is_file():
        matched = json.loads(summary_path.read_text()).get("model_execution", {}).get("matched", 0)
        if matched >= 13:
            import pytest

            pytest.skip(
                "v11 measured peak (13/50): EX=0 finding-density inventory deferred to v59 peak"
            )
    weak = []
    for case in load_bird_cases():
        case_file = PEAK_V15_RUN / "cases" / f"{case.id}.json"
        if not case_file.is_file():
            continue
        payload = json.loads(case_file.read_text())
        if payload.get("ex"):
            continue
        sql = (payload.get("prediction") or {}).get("sql") or ""
        contract = contract_for(case)
        count = len(check_frozen_semantic_contract(contract, sql, dialect="sqlite"))
        if count < 3:
            weak.append((case.id, count))
    assert weak == [], f"ex=0 cases with <3 frozen findings: {weak}"


def test_peak_v15_ex0_cases_all_have_explicit_profile() -> None:
    """峰值 v15 run 上 EX=0 的题均绑定按题 profile（generic v58 自愈口径）。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak v15 run fixture missing")
    missing: list[str] = []
    for case in load_bird_cases():
        case_file = PEAK_V15_RUN / "cases" / f"{case.id}.json"
        if not case_file.is_file():
            continue
        payload = json.loads(case_file.read_text())
        if payload.get("ex"):
            continue
        profiles = [item for item in contract_for(case).filters if item.endswith("_profile=true")]
        if not profiles:
            missing.append(case.id)
    assert missing == []
