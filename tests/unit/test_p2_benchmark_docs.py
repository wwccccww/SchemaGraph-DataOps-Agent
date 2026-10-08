"""P2 自建实测 Recovery@3 摘要写入 benchmark.md 自动段落。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.evaluation.p2_benchmark_docs import (
    P2_MEASURED_AUTOGEN_END,
    P2_MEASURED_AUTOGEN_START,
    patch_benchmark_measured_section,
)


def _minimal_summary(*, complete: bool = True) -> dict[str, object]:
    return {
        "git_commit": "abc1234",
        "model": "deepseek-chat",
        "prompt_version": "text-to-sql-generic-v59",
        "measured": {
            "complete": complete,
            "execution_accuracy": {
                "schema_graph": {"overall": 0.75, "denominator": 132},
                "self_healing": {"overall": 0.80, "denominator": 132},
            },
            "recovery_at_3": {
                "rate": 0.5,
                "recovered": 10,
                "failed": 10,
                "excluded_first_attempt": 112,
                "denominator": 20,
            },
            "paired_recovery": {
                "paired_recovery_rate": 0.4,
                "paired_recovered": 8,
                "paired_initial_failures": 20,
            },
        },
    }


def test_benchmark_md_has_p2_autogen_markers() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "docs/benchmark.md").read_text(encoding="utf-8")
    assert P2_MEASURED_AUTOGEN_START in text
    assert P2_MEASURED_AUTOGEN_END in text
    autogen = text.split(P2_MEASURED_AUTOGEN_START, 1)[1].split(P2_MEASURED_AUTOGEN_END, 1)[0]
    assert "p2_measured_gate=pass" in autogen
    assert "p2_recovery_at_3_rate=" in autogen
    assert "p2_measured_complete=true" in autogen


def test_patch_p2_benchmark_measured_section_replaces_once(tmp_path: Path) -> None:
    benchmark = tmp_path / "benchmark.md"
    benchmark.write_text(
        f"before\n{P2_MEASURED_AUTOGEN_START}\nold\n{P2_MEASURED_AUTOGEN_END}\nafter\n",
        encoding="utf-8",
    )
    report = "p2_recovery_at_3_rate=0.5000"
    patched = patch_benchmark_measured_section(benchmark.read_text(encoding="utf-8"), report)
    assert "old" not in patched
    assert "p2_recovery_at_3_rate=0.5000" in patched
    assert "p2_measured_gate=pass" in patched


def test_p2_custom_ablation_summary_cli_gate_and_write(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_20261008T000000Z_abc1234"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(json.dumps(_minimal_summary()), encoding="utf-8")
    benchmark = tmp_path / "benchmark.md"
    benchmark.write_text(
        f"{P2_MEASURED_AUTOGEN_START}\n\n```text\npending\n```\n\n{P2_MEASURED_AUTOGEN_END}\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.p2_custom_ablation_summary",
            "--run-dir",
            str(run_dir),
            "--acceptance-gate",
            "--write-benchmark",
            str(benchmark),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "p2_recovery_at_3_rate=0.5000" in completed.stdout
    assert "p2_measured_gate=pass" in benchmark.read_text(encoding="utf-8")


def test_p2_custom_ablation_summary_gate_fails_when_incomplete(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_incomplete"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps(_minimal_summary(complete=False)), encoding="utf-8"
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.evaluation.p2_custom_ablation_summary",
            "--run-dir",
            str(run_dir),
            "--acceptance-gate",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert completed.returncode == 3
