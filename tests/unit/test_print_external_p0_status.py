"""print_external_p0_status.sh 冒烟（无 BIRD 库时仍应打印 release_ready）。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_print_external_p0_status_runs_without_bird_replay() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/print_external_p0_status.sh"
    if not script.is_file():
        raise AssertionError("missing print_external_p0_status.sh")
    env = {k: v for k, v in os.environ.items() if k != "BIRD_DATABASE_ROOT"}
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=script.parents[1],
    )
    assert completed.returncode == 0, completed.stderr
    assert "release_ready=True" in completed.stdout
    assert "ops_runbook=docs/external_gold_p0_runbook.md" in completed.stdout
    assert "next_after_billing=./scripts/p0_post_billing_acceptance.sh" in completed.stdout
    assert (
        "post_billing_docs=python3 -m app.evaluation.p0_measured_summary --acceptance-gate"
        in completed.stdout
    )
    assert "generic_prompt=text-to-sql-generic-v" in completed.stdout
    assert any(
        token in completed.stdout
        for token in (
            "llm_preflight=ready",
            "llm_preflight=blocked",
            "llm_preflight=blocked_billing_402",
            "llm_preflight=blocked_no_api_key",
        )
    )
    peak = (
        script.parents[1]
        / "reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49"
    )
    if peak.is_dir():
        assert "peak_ex0_frozen_findings=pass_min_3" in completed.stdout


def test_print_external_p0_status_reports_billing_402_with_stub(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/print_external_p0_status.sh"
    real_python = subprocess.run(
        ["bash", "-lc", "command -v python3"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    fake_python = tmp_path / "python3"
    fake_python.write_text(
        f"""#!/usr/bin/env bash
if [[ "$1" == "-m" && "$2" == "app.evaluation.llm_preflight" ]]; then
  echo "model gateway failed with status 402 (Payment Required)" >&2
  exit 2
fi
exec {real_python} "$@"
"""
    )
    fake_python.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "BIRD_DATABASE_ROOT"}
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=root,
    )
    assert completed.returncode == 0, completed.stderr
    assert "llm_preflight=blocked_billing_402" in completed.stdout
    assert (
        "while_billing_blocked=./scripts/p0_post_billing_acceptance.sh --gates-only"
        in completed.stdout
    )


def test_print_external_p0_status_reports_ready_with_stub(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/print_external_p0_status.sh"
    real_python = subprocess.run(
        ["bash", "-lc", "command -v python3"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    fake_python = tmp_path / "python3"
    fake_python.write_text(
        f"""#!/usr/bin/env bash
if [[ "$1" == "-m" && "$2" == "app.evaluation.llm_preflight" ]]; then
  echo "llm_preflight=ready"
  exit 0
fi
exec {real_python} "$@"
"""
    )
    fake_python.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "BIRD_DATABASE_ROOT"}
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=root,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.count("llm_preflight=ready") >= 1
