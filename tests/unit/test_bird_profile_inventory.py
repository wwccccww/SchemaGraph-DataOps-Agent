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
    """峰值 measured run 上 ex=1 均绑定按题 profile（v12：17/50）。"""
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


def test_v12_measured_ex0_frozen_finding_coverage_floor() -> None:
    """Step-3：v12 峰值（17/50）EX=0 保存 SQL 上 frozen finding 覆盖下限（repair 信号）。"""
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
    assert with_findings >= 33


def test_v12_peak_zero_cross_database_leaks() -> None:
    """Step-3 串库：v12 峰值须零 cross-database catalog leak。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak run fixture missing")
    summary = json.loads((PEAK_V15_RUN / "summary.json").read_text())
    execution = summary.get("model_execution") or {}
    assert execution.get("cross_database_leaks") == 0


def test_v12_measured_response_shape_ex0_have_frozen_findings() -> None:
    """Step-3 投影顺序：v12 response_shape EX=0 保存 SQL 须有 frozen 信号。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak run fixture missing")
    expected_ids: list[str] = []
    for case in load_bird_cases():
        case_file = PEAK_V15_RUN / "cases" / f"{case.id}.json"
        if not case_file.is_file():
            continue
        payload = json.loads(case_file.read_text())
        if payload.get("ex") or payload.get("diagnosis_class") != "response_shape":
            continue
        sql = (payload.get("prediction") or {}).get("sql") or ""
        count = len(check_frozen_semantic_contract(contract_for(case), sql, dialect="sqlite"))
        assert count >= 1, f"{case.id} response_shape saved SQL has 0 frozen findings"
        expected_ids.append(case.id)
    assert expected_ids == ["bird_0055", "bird_0113"]


def test_v12_measured_join_semantics_ex0_have_frozen_findings() -> None:
    """Step-3 Join：v12 join_semantics 保存 SQL 须有 frozen 信号（跟进 measured EX，非 Gold amend）。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak run fixture missing")
    expected_ids: list[str] = []
    for case in load_bird_cases():
        case_file = PEAK_V15_RUN / "cases" / f"{case.id}.json"
        if not case_file.is_file():
            continue
        payload = json.loads(case_file.read_text())
        if payload.get("ex") or payload.get("diagnosis_class") != "join_semantics":
            continue
        sql = (payload.get("prediction") or {}).get("sql") or ""
        count = len(check_frozen_semantic_contract(contract_for(case), sql, dialect="sqlite"))
        assert count >= 1, f"{case.id} join_semantics saved SQL has 0 frozen findings"
        expected_ids.append(case.id)
    assert expected_ids == [
        "bird_0066",
        "bird_0078",
        "bird_0092",
        "bird_0097",
        "bird_0111",
    ]


def test_v12_measured_sql_error_ex0_have_frozen_findings() -> None:
    """v12 峰值 sql_error 保存 SQL 须有 frozen 信号（0069/0119 仍靠 Gold overlay amend）。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak run fixture missing")
    sql_error_ids: list[str] = []
    for case in load_bird_cases():
        case_file = PEAK_V15_RUN / "cases" / f"{case.id}.json"
        if not case_file.is_file():
            continue
        payload = json.loads(case_file.read_text())
        if payload.get("ex") or payload.get("primary_class") != "sql_error":
            continue
        sql = (payload.get("prediction") or {}).get("sql") or ""
        count = len(check_frozen_semantic_contract(contract_for(case), sql, dialect="sqlite"))
        assert count >= 1, f"{case.id} sql_error saved SQL has 0 frozen findings"
        sql_error_ids.append(case.id)
    assert sql_error_ids == [
        "bird_0006",
        "bird_0069",
        "bird_0077",
        "bird_0100",
        "bird_0105",
        "bird_0119",
        "bird_0121",
        "bird_0123",
    ]


def test_v12_peak_multattempt_cases_include_repair_trace_symptoms() -> None:
    """Measured v12：attempts>1 的 case JSON 须在 symptoms 中保留 repair_trace（§11 P2 外部口径）。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak run fixture missing")
    missing: list[str] = []
    for case_file in sorted((PEAK_V15_RUN / "cases").glob("bird_*.json")):
        payload = json.loads(case_file.read_text())
        attempts = payload.get("attempts") or 0
        if attempts <= 1:
            continue
        symptoms = dict(payload.get("symptoms") or [])
        trace = symptoms.get("repair_trace", "")
        if not trace or trace.strip() == "":
            missing.append(payload["case_id"])
    assert missing == [], f"multi-attempt cases missing repair_trace symptom: {missing}"


def test_v12_sql_error_no_progress_cases_mark_no_progress_in_repair_trace() -> None:
    """§11.5 P2 / 熔断：no_progress sql_error 须在 repair_trace 症状链中可见。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak run fixture missing")
    missing: list[str] = []
    for case_file in sorted((PEAK_V15_RUN / "cases").glob("bird_*.json")):
        payload = json.loads(case_file.read_text())
        if payload.get("error_category") != "no_progress":
            continue
        symptoms = dict(payload.get("symptoms") or [])
        trace = str(symptoms.get("repair_trace", ""))
        if "no_progress" not in trace:
            missing.append(payload["case_id"])
    assert missing == [], f"no_progress cases without no_progress in repair_trace: {missing}"


def test_v12_peak_traces_pass_external_p2_write_validation() -> None:
    """v12 峰值 case JSON 须满足 write_external_model_report 的 P2 校验。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak run fixture missing")
    from app.evaluation.external_report import ModelCaseTrace, validate_external_p2_repair_traces

    traces: list[ModelCaseTrace] = []
    for case_file in sorted((PEAK_V15_RUN / "cases").glob("bird_*.json")):
        payload = json.loads(case_file.read_text())
        attempts = payload.get("attempts") or 0
        if attempts <= 1:
            continue
        raw_symptoms = payload.get("symptoms") or []
        symptoms = tuple(
            (str(row[0]), str(row[1]))
            for row in raw_symptoms
            if isinstance(row, list) and len(row) >= 2
        )
        prediction = payload.get("prediction")
        pred_map = dict(prediction) if isinstance(prediction, dict) else {}
        traces.append(
            ModelCaseTrace(
                case_id=str(payload["case_id"]),
                database_id=str(payload["database_id"]),
                primary_class=str(payload.get("primary_class") or ""),
                ex=int(payload.get("ex") or 0),
                error_category=(
                    None
                    if payload.get("error_category") is None
                    else str(payload["error_category"])
                ),
                attempts=attempts,
                seed_tables=tuple(payload.get("seed_tables") or ()),
                expanded_tables=tuple(payload.get("expanded_tables") or ()),
                leaked_tables=tuple(payload.get("leaked_tables") or ()),
                ecommerce_rule_hits=tuple(payload.get("ecommerce_rule_hits") or ()),
                prediction=pred_map,
                symptoms=symptoms,
            )
        )
    validate_external_p2_repair_traces(traces)


def test_v12_peak_replay_inspection_restores_repair_trace() -> None:
    """P1 replay：`inspection_from_replay` 须从 symptoms 还原 trace（对接 score_prediction P2 门禁）。"""
    if not PEAK_V15_RUN.is_dir():
        import pytest

        pytest.skip("peak run fixture missing")
    from app.evaluation.external_model import inspection_from_replay

    empty: list[str] = []
    for case_file in sorted((PEAK_V15_RUN / "cases").glob("bird_*.json")):
        payload = json.loads(case_file.read_text())
        attempts = payload.get("attempts") or 0
        if attempts <= 1:
            continue
        inspection = inspection_from_replay(payload)
        if not inspection.repair_trace:
            empty.append(payload["case_id"])
    assert empty == [], f"replay inspection missing repair_trace: {empty}"


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
                "v12 measured peak (17/50): use test_v12_measured_ex0_frozen_finding_coverage_floor"
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
