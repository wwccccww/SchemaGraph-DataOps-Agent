"""P0 实测 run 摘要 CLI。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from app.evaluation.p0_measured_summary import (
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
    _write_summary(b1, source="bird", matched=7, case_count=50, accuracy=0.14)
    _write_summary(b2, source="bird", matched=7, case_count=50, accuracy=0.14)
    text = format_report(
        [load_run_measured(t1), load_run_measured(t2)],
        [load_run_measured(b1), load_run_measured(b2)],
    )
    assert "p0_measured_tpcds_run1=30/30" in text
    assert "p0_stability_tpcds=stable" in text
    assert "p0_measured_bird_run2=7/50" in text
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
    _write_summary(b1, source="bird", matched=8, case_count=50, accuracy=0.16)
    _write_summary(b2, source="bird", matched=8, case_count=50, accuracy=0.16)
    assert (
        validate_p0_acceptance_gate(
            [load_run_measured(t1), load_run_measured(t2)],
            [load_run_measured(b1), load_run_measured(b2)],
        )
        == []
    )


def test_acceptance_gate_fails_unstable_tpcds(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"
    t2 = tmp_path / "t2"
    b1 = tmp_path / "b1"
    b2 = tmp_path / "b2"
    _write_summary(t1, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(t2, source="tpcds-derived", matched=29, case_count=30, accuracy=29 / 30)
    _write_summary(b1, source="bird", matched=7, case_count=50, accuracy=0.14)
    _write_summary(b2, source="bird", matched=7, case_count=50, accuracy=0.14)
    failures = validate_p0_acceptance_gate(
        [load_run_measured(t1), load_run_measured(t2)],
        [load_run_measured(b1), load_run_measured(b2)],
    )
    assert any("tpcds" in item for item in failures)


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
    root = Path(__file__).resolve().parents[2]
    peak = root / "reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
    if not peak.is_dir():
        pytest.skip("bird peak run fixture unavailable")
    loaded = load_run_measured(peak)
    assert loaded.matched == 7
    assert loaded.case_count == 50
