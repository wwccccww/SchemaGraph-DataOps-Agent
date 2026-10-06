"""P0 计费恢复验收脚本存在且 402 时在前置 preflight 停止。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_p0_post_billing_acceptance_script_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p0_post_billing_acceptance.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK)


def test_p0_post_billing_acceptance_requires_postgres_env() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p0_post_billing_acceptance.sh"
    env = {k: v for k, v in os.environ.items() if k not in ("POSTGRES_USER", "POSTGRES_PASSWORD")}
    env["BIRD_DATABASE_ROOT"] = env.get(
        "BIRD_DATABASE_ROOT", "/tmp/bird_dev/minidev/MINIDEV/dev_databases"
    )
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
    env["BIRD_DATABASE_ROOT"] = env.get(
        "BIRD_DATABASE_ROOT", "/tmp/bird_dev/minidev/MINIDEV/dev_databases"
    )
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
