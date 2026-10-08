"""P0 实测 run 摘要 CLI。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from app.evaluation.p0_measured_summary import (
    RunMeasured,
    baseline_followup_hint,
    format_report,
    load_manifest,
    load_run_measured,
    stability_label,
    validate_p0_acceptance_gate,
)


def _write_summary(
    run_dir: Path, *, source: str, matched: int, case_count: int, accuracy: float
) -> None:
    run_dir.mkdir(parents=True)
    payload = {
        "git_commit": "abc123",
        "benchmark_source": source,
        "prompt_version": "text-to-sql-generic-v59",
        "measured": {"execution_accuracy": accuracy},
        "model_execution": {"matched": matched, "case_count": case_count},
    }
    (run_dir / "summary.json").write_text(json.dumps(payload), encoding="utf-8")


def test_load_run_measured_from_fixture(tmp_path: Path) -> None:
    run = tmp_path / "run_test"
    _write_summary(run, source="bird", matched=7, case_count=50, accuracy=0.14)
    loaded = load_run_measured(run)
    assert loaded.fraction_label == "7/50"
    assert loaded.execution_accuracy == 0.14


def test_baseline_followup_hint_e5482a4_class_24_with_floor_19() -> None:
    a = RunMeasured(
        run_dir=Path("/tmp/a"),
        benchmark_source="bird",
        matched=24,
        case_count=50,
        execution_accuracy=0.48,
        git_commit="e5482a4",
        prompt_version="text-to-sql-generic-v59",
    )
    b = RunMeasured(
        run_dir=Path("/tmp/b"),
        benchmark_source="bird",
        matched=24,
        case_count=50,
        execution_accuracy=0.48,
        git_commit="e5482a4",
        prompt_version="text-to-sql-generic-v59",
    )
    hint = baseline_followup_hint([a, b], documented_bird_min=19)
    assert hint is not None
    assert "P0_BIRD_MIN_MATCHED=24" in hint
    assert "bird_stable_matched=24/50" in hint


def test_baseline_followup_hint_when_bird_beats_documented_floor() -> None:
    a = load_run_measured_from_values("bird", 8, 50, 0.16)
    b = load_run_measured_from_values("bird", 8, 50, 0.16)
    hint = baseline_followup_hint([a, b], documented_bird_min=7)
    assert hint is not None
    assert "P0_BIRD_MIN_MATCHED=8" in hint
    assert baseline_followup_hint([a, b], documented_bird_min=8) is None


def test_stability_label() -> None:
    a = load_run_measured_from_values("bird", 7, 50, 0.14)
    b = load_run_measured_from_values("bird", 7, 50, 0.14)
    c = load_run_measured_from_values("bird", 8, 50, 0.16)
    assert stability_label(a, b) == "stable"
    assert stability_label(a, c) == "unstable"


def load_run_measured_from_values(source: str, matched: int, case_count: int, accuracy: float):
    from app.evaluation.p0_measured_summary import RunMeasured

    return RunMeasured(
        run_dir=Path("/tmp/x"),
        benchmark_source=source,
        matched=matched,
        case_count=case_count,
        execution_accuracy=accuracy,
        git_commit="x",
        prompt_version="v",
    )


def test_format_report_two_by_two(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"
    t2 = tmp_path / "t2"
    b1 = tmp_path / "b1"
    b2 = tmp_path / "b2"
    _write_summary(t1, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(t2, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(b1, source="bird", matched=17, case_count=50, accuracy=0.34)
    _write_summary(b2, source="bird", matched=17, case_count=50, accuracy=0.34)
    text = format_report(
        [load_run_measured(t1), load_run_measured(t2)],
        [load_run_measured(b1), load_run_measured(b2)],
    )
    assert "p0_measured_tpcds_run1=30/30" in text
    assert "p0_stability_tpcds=stable" in text
    assert "p0_measured_bird_run2=17/50" in text
    assert "p0_stability_bird=stable" in text


def test_cli_rejects_wrong_source(tmp_path: Path) -> None:
    run = tmp_path / "bad"
    _write_summary(run, source="bird", matched=1, case_count=50, accuracy=0.02)
    completed = subprocess.run(
        [sys.executable, "-m", "app.evaluation.p0_measured_summary", "--tpcds-run", str(run)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "tpcds-derived" in completed.stderr


def test_load_manifest_tsv(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"
    _write_summary(t1, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    manifest = tmp_path / "m.tsv"
    manifest.write_text(f"tpcds-derived\t{t1}\n", encoding="utf-8")
    tpcds, bird = load_manifest(manifest)
    assert bird == []
    assert tpcds == [t1]


def test_acceptance_gate_passes_on_stable_full_band(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"
    t2 = tmp_path / "t2"
    b1 = tmp_path / "b1"
    b2 = tmp_path / "b2"
    _write_summary(t1, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(t2, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(b1, source="bird", matched=19, case_count=50, accuracy=0.38)
    _write_summary(b2, source="bird", matched=19, case_count=50, accuracy=0.38)
    assert (
        validate_p0_acceptance_gate(
            [load_run_measured(t1), load_run_measured(t2)],
            [load_run_measured(b1), load_run_measured(b2)],
        )
        == []
    )


def test_acceptance_gate_fails_bird_below_baseline_min(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"
    t2 = tmp_path / "t2"
    b1 = tmp_path / "b1"
    b2 = tmp_path / "b2"
    _write_summary(t1, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(t2, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(b1, source="bird", matched=16, case_count=50, accuracy=0.32)
    _write_summary(b2, source="bird", matched=16, case_count=50, accuracy=0.32)
    failures = validate_p0_acceptance_gate(
        [load_run_measured(t1), load_run_measured(t2)],
        [load_run_measured(b1), load_run_measured(b2)],
        bird_min_matched=17,
    )
    assert any("below baseline min" in item for item in failures)


def test_acceptance_gate_fails_unstable_tpcds(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"
    t2 = tmp_path / "t2"
    b1 = tmp_path / "b1"
    b2 = tmp_path / "b2"
    _write_summary(t1, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(t2, source="tpcds-derived", matched=29, case_count=30, accuracy=29 / 30)
    _write_summary(b1, source="bird", matched=17, case_count=50, accuracy=0.34)
    _write_summary(b2, source="bird", matched=17, case_count=50, accuracy=0.34)
    failures = validate_p0_acceptance_gate(
        [load_run_measured(t1), load_run_measured(t2)],
        [load_run_measured(b1), load_run_measured(b2)],
        bird_min_matched=17,
    )
    assert any("tpcds" in item for item in failures)


def test_acceptance_gate_bird_min_zero_skips_floor(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"
    t2 = tmp_path / "t2"
    b1 = tmp_path / "b1"
    b2 = tmp_path / "b2"
    _write_summary(t1, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(t2, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(b1, source="bird", matched=6, case_count=50, accuracy=0.12)
    _write_summary(b2, source="bird", matched=6, case_count=50, accuracy=0.12)
    assert (
        validate_p0_acceptance_gate(
            [load_run_measured(t1), load_run_measured(t2)],
            [load_run_measured(b1), load_run_measured(b2)],
            bird_min_matched=0,
        )
        == []
    )


def test_cli_acceptance_gate_passes(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"
    t2 = tmp_path / "t2"
    b1 = tmp_path / "b1"
    b2 = tmp_path / "b2"
    _write_summary(t1, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(t2, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(b1, source="bird", matched=19, case_count=50, accuracy=0.38)
    _write_summary(b2, source="bird", matched=19, case_count=50, accuracy=0.38)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.p0_measured_summary",
            "--tpcds-run",
            str(t1),
            "--tpcds-run",
            str(t2),
            "--bird-run",
            str(b1),
            "--bird-run",
            str(b2),
            "--acceptance-gate",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "p0_acceptance_gate=pass" in completed.stdout


def test_cli_acceptance_gate_exit_code(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"
    _write_summary(t1, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.p0_measured_summary",
            "--tpcds-run",
            str(t1),
            "--acceptance-gate",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 3
    assert "p0_acceptance_gate=fail" in completed.stderr


def test_cli_on_peak_bird_fixture() -> None:
    from tests.unit.bird_replay_fixtures import BIRD_PEAK_RUN

    peak = BIRD_PEAK_RUN
    if not peak.is_dir():
        pytest.skip("bird peak run fixture unavailable")
    loaded = load_run_measured(peak)
    assert loaded.matched == 17
    assert loaded.case_count == 50


def test_peak_tpcds_pair_satisfies_acceptance_tpcds_rules() -> None:
    from tests.unit.bird_replay_fixtures import TPCDS_PEAK_RUN

    peak = TPCDS_PEAK_RUN
    if not peak.is_dir():
        pytest.skip("tpcds peak run fixture unavailable")
    pair = [load_run_measured(peak), load_run_measured(peak)]
    failures = validate_p0_acceptance_gate(pair, [], bird_min_matched=7)
    tpcds_failures = [item for item in failures if "tpcds" in item.lower()]
    assert tpcds_failures == []


def test_peak_bird_pair_satisfies_acceptance_bird_rules() -> None:
    """Peak v12 双跑同目录时 BIRD 侧应 stable 且满足 17/50 下限（TPC-DS 仍须另补 2 run）。"""
    from tests.unit.bird_replay_fixtures import BIRD_PEAK_RUN

    peak = BIRD_PEAK_RUN
    if not peak.is_dir():
        pytest.skip("bird peak run fixture unavailable")
    pair = [load_run_measured(peak), load_run_measured(peak)]
    failures = validate_p0_acceptance_gate([], pair, bird_min_matched=17)
    bird_failures = [item for item in failures if "bird" in item.lower()]
    assert bird_failures == []


def test_live_measured_manifest_runs_pass_full_acceptance_gate_cli() -> None:
    """Billing 后 live manifest 四行（本地 reports/）须 gate pass；无目录则 skip。"""
    root = Path(__file__).resolve().parents[2]
    tpcds1 = (
        root / "reports/tpcds-derived/run_20261008T033330Z_5e4659e6f4df4587e99794a3e64fa30922c78619"
    )
    tpcds2 = (
        root / "reports/tpcds-derived/run_20261008T033735Z_5e4659e6f4df4587e99794a3e64fa30922c78619"
    )
    bird1 = root / "reports/bird/run_20261008T041410Z_7fd32c8d7e62e3e19a023e75e5e91e6cd1d3dc94"
    bird2 = root / "reports/bird/run_20261008T041713Z_7fd32c8d7e62e3e19a023e75e5e91e6cd1d3dc94"
    if not all(p.is_dir() for p in (tpcds1, tpcds2, bird1, bird2)):
        pytest.skip("live P0 measured run dirs missing (billing acceptance artifact)")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.p0_measured_summary",
            "--tpcds-run",
            str(tpcds1),
            "--tpcds-run",
            str(tpcds2),
            "--bird-run",
            str(bird1),
            "--bird-run",
            str(bird2),
            "--acceptance-gate",
            "--bird-min-matched",
            "50",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "p0_acceptance_gate=pass" in completed.stdout
    assert "p0_measured_bird_run1=50/50" in completed.stdout
    assert "p0_stability_bird=stable" in completed.stdout


def test_peak_documented_runs_pass_full_acceptance_gate_cli() -> None:
    """vendored 峰值 run 各 2× 重放目录时 gate pass（BIRD 17/50 须显式 --bird-min-matched 17）。"""
    from tests.unit.bird_replay_fixtures import BIRD_PEAK_RUN, TPCDS_PEAK_RUN

    if not TPCDS_PEAK_RUN.is_dir() or not BIRD_PEAK_RUN.is_dir():
        pytest.skip("peak tpcds/bird run fixtures unavailable")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.p0_measured_summary",
            "--tpcds-run",
            str(TPCDS_PEAK_RUN),
            "--tpcds-run",
            str(TPCDS_PEAK_RUN),
            "--bird-run",
            str(BIRD_PEAK_RUN),
            "--bird-run",
            str(BIRD_PEAK_RUN),
            "--acceptance-gate",
            "--bird-min-matched",
            "17",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "p0_acceptance_gate=pass" in completed.stdout
    assert "p0_stability_tpcds=stable" in completed.stdout
    assert "p0_stability_bird=stable" in completed.stdout
