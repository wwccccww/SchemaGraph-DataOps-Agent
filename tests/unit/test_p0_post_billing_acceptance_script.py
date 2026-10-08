"""P0 计费恢复验收脚本存在且 402 时在前置 preflight 停止。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.unit.bird_replay_fixtures import ensure_bird_database_root


def test_p0_post_billing_acceptance_script_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p0_post_billing_acceptance.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK)
    text = script.read_text(encoding="utf-8")
    assert "--gates-only" in text
    assert 'source "$ROOT/.env"' in text
    assert "p0_acceptance_gate=pass" in text
    assert "run_external_p0_full_eval_twice.sh" in text
    assert "apply_p0_measured_benchmark.sh" in text
    assert "tpcds_postgres_catalog=" in text
    assert "p0_bird_min_matched=" in text
    assert "acceptance-gate" in text or "Exit:" in text
    assert "P0_FROM_BILLING_WAIT" in text
    assert "P0_PREFLIGHT_WAIT_RETRIES" in text
    assert "P0_ACCEPTANCE_LOCK_FILE" in text
    assert "P0_RELEASE_GATE_STUB" in text
    assert "p0_acceptance=already_running" in text
    assert "flock -n 9" in text
    assert "run_external_p0_full_eval_twice.sh" in text
    gate_idx = text.index("p1_release_gate.sh")
    flock_idx = text.index("flock -n 9")
    eval_idx = text.index("run_external_p0_full_eval_twice.sh")
    assert gate_idx < flock_idx < eval_idx


def test_p0_post_billing_acceptance_requires_bird_root_directory() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p0_post_billing_acceptance.sh"
    env = os.environ.copy()
    env["BIRD_DATABASE_ROOT"] = "/tmp/nonexistent_bird_dev_databases_p0_test"
    env.setdefault("POSTGRES_USER", "text2sql_admin")
    env.setdefault("POSTGRES_PASSWORD", "local-admin-secret")
    completed = subprocess.run(
        [str(script), "--gates-only"],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert completed.returncode == 1
    assert "not a directory" in completed.stderr
    assert env["BIRD_DATABASE_ROOT"] in completed.stderr


def test_p0_post_billing_acceptance_requires_postgres_env() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p0_post_billing_acceptance.sh"
    env = {k: v for k, v in os.environ.items() if k not in ("POSTGRES_USER", "POSTGRES_PASSWORD")}
    ensure_bird_database_root(env)
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert completed.returncode == 1
    assert "POSTGRES_USER" in completed.stderr


def test_p0_post_billing_acceptance_retries_transient_402_after_wait(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p0_post_billing_acceptance.sh"
    real_python = subprocess.run(
        ["bash", "-lc", "command -v python3"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    state = tmp_path / "preflight_calls"
    state.write_text("0", encoding="utf-8")
    fake_python = tmp_path / "python3"
    fake_python.write_text(
        f"""#!/usr/bin/env bash
if [[ "$1" == "-m" && "$2" == "app.evaluation.llm_preflight" ]]; then
  n=$(cat {state})
  echo $((n + 1)) > {state}
  if [[ "$n" -lt 2 ]]; then
    echo "model gateway failed with status 402 (Payment Required)" >&2
    exit 2
  fi
  exit 0
fi
exec {real_python} "$@"
"""
    )
    fake_python.chmod(0o755)
    env = os.environ.copy()
    ensure_bird_database_root(env, tmp_path=tmp_path)
    env.setdefault("POSTGRES_USER", "text2sql_admin")
    env.setdefault("POSTGRES_PASSWORD", "local-admin-secret")
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    env["P0_FROM_BILLING_WAIT"] = "1"
    env["P0_PREFLIGHT_WAIT_RETRIES"] = "4"
    env["P0_PREFLIGHT_WAIT_SLEEP"] = "0"
    env["P0_ACCEPTANCE_PREFLIGHT_ONLY"] = "1"
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    assert "p0_acceptance_preflight_only=ok" in completed.stdout
    assert "retry=1/4" in completed.stderr or "retry=1/4" in completed.stdout


def test_p0_post_billing_acceptance_stops_on_llm_preflight_402(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p0_post_billing_acceptance.sh"
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
  echo "P0 full eval blocked: use ./scripts/print_external_p0_status.sh" >&2
  exit 2
fi
exec {real_python} "$@"
"""
    )
    fake_python.chmod(0o755)
    env = os.environ.copy()
    ensure_bird_database_root(env, tmp_path=tmp_path)
    env.setdefault("POSTGRES_USER", "text2sql_admin")
    env.setdefault("POSTGRES_PASSWORD", "local-admin-secret")
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert completed.returncode == 2
    assert "402" in completed.stdout + completed.stderr
    assert "generic_prompt=text-to-sql-generic-v" in completed.stdout


def test_p0_post_billing_gates_only_skips_llm_preflight(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p0_post_billing_acceptance.sh"
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
  echo "preflight should not run in --gates-only" >&2
  exit 99
fi
exec {real_python} "$@"
"""
    )
    fake_python.chmod(0o755)
    env = os.environ.copy()
    ensure_bird_database_root(env, tmp_path=tmp_path)
    env.setdefault("POSTGRES_USER", "text2sql_admin")
    env.setdefault("POSTGRES_PASSWORD", "local-admin-secret")
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    env["P0_GATES_ONLY_STUB"] = "1"
    completed = subprocess.run(
        [str(script), "--gates-only"],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    assert "mode=gates_only" in completed.stdout
    assert "p0_bird_min_matched=19" in completed.stdout
    assert "preflight should not run" not in completed.stderr
    assert "p1_release_gate=stub" in completed.stdout
    assert "P0 gates-only OK" in completed.stdout
    assert "ops_runbook=docs/external_gold_p0_runbook.md" in completed.stdout
    assert "next_after_billing=./scripts/p0_post_billing_acceptance.sh" in completed.stdout
    assert "unattended_after_billing=./scripts/wait_for_billing_and_run_p0.sh" in completed.stdout
    assert "e5482a4_replay_baseline=./scripts/replay_e5482a4_baseline.sh" in completed.stdout
    assert "e5482a4_replay_patch=./scripts/replay_e5482a4_patch_autofix.sh" in completed.stdout
    assert any(
        token in completed.stdout
        for token in (
            "tpcds_postgres_catalog=ready",
            "tpcds_postgres_catalog=unreachable",
        )
    )


def test_p0_post_billing_exits_4_when_acceptance_lock_held(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p0_post_billing_acceptance.sh"
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
  exit 0
fi
exec {real_python} "$@"
"""
    )
    fake_python.chmod(0o755)
    lock = tmp_path / "p0_acceptance.lock"
    lock.touch()
    hold = subprocess.Popen(
        ["bash", "-lc", f'exec 9>"{lock}"; flock 9; sleep 60'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        env = os.environ.copy()
        ensure_bird_database_root(env, tmp_path=tmp_path)
        env.setdefault("POSTGRES_USER", "text2sql_admin")
        env.setdefault("POSTGRES_PASSWORD", "local-admin-secret")
        env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
        env["P0_ACCEPTANCE_LOCK_FILE"] = str(lock)
        env["P0_RELEASE_GATE_STUB"] = "1"
        completed = subprocess.run(
            [str(script)],
            check=False,
            capture_output=True,
            text=True,
            cwd=root,
            env=env,
            timeout=30,
        )
    finally:
        hold.terminate()
        hold.wait(timeout=5)
    assert completed.returncode == 4
    assert "p0_acceptance=already_running" in completed.stderr
