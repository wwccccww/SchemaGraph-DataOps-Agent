"""P0 实测摘要写入 benchmark.md 自动段落。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.evaluation.p0_benchmark_docs import (
    P0_MEASURED_AUTOGEN_END,
    P0_MEASURED_AUTOGEN_START,
    patch_benchmark_measured_section,
)
from app.evaluation.p0_measured_summary import format_report, load_run_measured


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


def test_benchmark_md_has_autogen_markers() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "docs/benchmark.md").read_text(encoding="utf-8")
    assert P0_MEASURED_AUTOGEN_START in text
    assert P0_MEASURED_AUTOGEN_END in text


def test_patch_benchmark_measured_section_replaces_once(tmp_path: Path) -> None:
    benchmark = tmp_path / "benchmark.md"
    benchmark.write_text(
        f"before\n{P0_MEASURED_AUTOGEN_START}\nold\n{P0_MEASURED_AUTOGEN_END}\nafter\n",
        encoding="utf-8",
    )
    report = "p0_measured_bird_run1=7/50 ex=0.14"
    patched = patch_benchmark_measured_section(benchmark.read_text(encoding="utf-8"), report)
    assert "old" not in patched
    assert "p0_measured_bird_run1=7/50" in patched
    assert "p0_acceptance_gate=pass" in patched
    assert patched.count(P0_MEASURED_AUTOGEN_START) == 1


def test_cli_write_benchmark_on_gate_pass(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"
    t2 = tmp_path / "t2"
    b1 = tmp_path / "b1"
    b2 = tmp_path / "b2"
    _write_summary(t1, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(t2, source="tpcds-derived", matched=30, case_count=30, accuracy=1.0)
    _write_summary(b1, source="bird", matched=7, case_count=50, accuracy=0.14)
    _write_summary(b2, source="bird", matched=7, case_count=50, accuracy=0.14)
    benchmark = tmp_path / "benchmark.md"
    benchmark.write_text(
        f"{P0_MEASURED_AUTOGEN_START}\n\n```text\npending\n```\n\n{P0_MEASURED_AUTOGEN_END}\n",
        encoding="utf-8",
    )
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
            "--write-benchmark",
            str(benchmark),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "p0_benchmark_docs=updated" in completed.stdout
    body = benchmark.read_text(encoding="utf-8")
    assert "p0_stability_bird=stable" in body
    assert "pending" not in body


def test_format_report_matches_patch_expectations(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"
    _write_summary(t1, source="bird", matched=7, case_count=50, accuracy=0.14)
    loaded = load_run_measured(t1)
    report = format_report([], [loaded, loaded])
    patched = patch_benchmark_measured_section(
        f"{P0_MEASURED_AUTOGEN_START}\nx{P0_MEASURED_AUTOGEN_END}",
        report,
    )
    assert "p0_measured_bird_run1=7/50" in patched
