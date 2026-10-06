"""402 轮询后触发 P0 全量 acceptance 的运维脚本契约。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.unit.bird_replay_fixtures import ensure_bird_database_root


def test_wait_for_billing_script_exists_and_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/wait_for_billing_and_run_p0.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK)
    text = script.read_text(encoding="utf-8")
    assert 'source "$ROOT/.env"' in text
    assert "ops_runbook=docs/external_gold_p0_runbook.md" in text
    assert "P0_BILLING_POLL_SECONDS" in text
    assert "p0_post_billing_acceptance.sh" in text
    assert "P0_WAIT_STUB_ACCEPTANCE" in text
    assert "BIRD_DATABASE_ROOT is required" in text
    assert "POSTGRES_USER" in text
    assert "tpcds_postgres_catalog=" in text
    assert "P0_WAIT_LOG" in text
    assert "wait_log=" in text
    assert "P0_WAIT_CONFIRM_POLLS" in text
    assert "confirm_polls=" in text


def test_wait_for_billing_requires_postgres_env() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/wait_for_billing_and_run_p0.sh"
    env = {k: v for k, v in os.environ.items() if k not in ("POSTGRES_USER", "POSTGRES_PASSWORD")}
    ensure_bird_database_root(env)
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
        timeout=10,
    )
    assert completed.returncode == 1
    assert "POSTGRES_USER" in completed.stderr


def test_wait_for_billing_requires_bird_root_directory() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/wait_for_billing_and_run_p0.sh"
    env = os.environ.copy()
    env["BIRD_DATABASE_ROOT"] = "/tmp/nonexistent_bird_dev_databases_wait_test"
    env.setdefault("POSTGRES_USER", "text2sql_admin")
    env.setdefault("POSTGRES_PASSWORD", "local-admin-secret")
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
        timeout=10,
    )
    assert completed.returncode == 1
    assert "not a directory" in completed.stderr


def test_wait_for_billing_requires_bird_database_root() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/wait_for_billing_and_run_p0.sh"
    env = {k: v for k, v in os.environ.items() if k != "BIRD_DATABASE_ROOT"}
    env.setdefault("POSTGRES_USER", "text2sql_admin")
    env.setdefault("POSTGRES_PASSWORD", "local-admin-secret")
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
        timeout=10,
    )
    assert completed.returncode == 1
    assert "BIRD_DATABASE_ROOT" in completed.stderr


def test_wait_for_billing_non_402_preflight_exits_without_poll(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/wait_for_billing_and_run_p0.sh"
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
  echo "model gateway failed with status 503" >&2
  exit 2
fi
exec {real_python} "$@"
"""
    )
    fake_python.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    env["P0_BILLING_POLL_SECONDS"] = "1"
    ensure_bird_database_root(env, tmp_path=tmp_path)
    env.setdefault("POSTGRES_USER", "text2sql_admin")
    env.setdefault("POSTGRES_PASSWORD", "local-admin-secret")
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
        timeout=10,
    )
    assert completed.returncode == 2
    assert "503" in completed.stderr
    assert "blocked_billing_402" not in completed.stderr


def test_wait_for_billing_polls_402_then_runs_acceptance_stub(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/wait_for_billing_and_run_p0.sh"
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
  if [[ "$n" -lt 1 ]]; then
    echo "status 402 (Payment Required)" >&2
    exit 2
  fi
  exit 0
fi
exec {real_python} "$@"
"""
    )
    fake_python.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    env["P0_BILLING_POLL_SECONDS"] = "1"
    env["P0_WAIT_CONFIRM_SECONDS"] = "1"
    env["P0_WAIT_CONFIRM_POLLS"] = "2"
    env["P0_WAIT_STUB_ACCEPTANCE"] = "1"
    ensure_bird_database_root(env, tmp_path=tmp_path)
    env.setdefault("POSTGRES_USER", "text2sql_admin")
    env.setdefault("POSTGRES_PASSWORD", "local-admin-secret")
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
        timeout=25,
    )
    assert completed.returncode == 0, completed.stderr
    assert "llm_preflight=ready" in completed.stdout
    assert "p0_post_billing=stub" in completed.stdout
    assert "blocked_billing_402" in completed.stderr
