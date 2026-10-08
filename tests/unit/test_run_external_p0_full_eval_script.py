"""P0 组合脚本存在且会要求 BIRD_DATABASE_ROOT。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.unit.bird_replay_fixtures import ensure_bird_database_root


def test_run_external_p0_full_eval_twice_requires_bird_root() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/run_external_p0_full_eval_twice.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert 'source "$ROOT/.env"' in text
    assert "p0_measured_summary" in text
    assert "--acceptance-gate" in text
    assert "P0_BIRD_MIN_MATCHED" in text
    assert "--bird-min-matched" in text
    assert "run_tpcds_p0_full_eval_twice.sh" in text
    assert "run_bird_p0_full_eval_twice.sh" in text
    assert "P0_MEASURED_MANIFEST" in text
    assert "p0_measured_manifest=" in text
    assert "p0_measured_manifest_format=" in text
    assert "p0_bird_min_matched=" in text
    env = {k: v for k, v in os.environ.items() if k != "BIRD_DATABASE_ROOT"}
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=script.parents[1],
    )
    assert completed.returncode != 0
    assert "BIRD_DATABASE_ROOT" in completed.stderr


def test_run_external_p0_full_eval_twice_requires_bird_root_directory() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/run_external_p0_full_eval_twice.sh"
    env = os.environ.copy()
    env["BIRD_DATABASE_ROOT"] = "/tmp/nonexistent_bird_dev_databases_external_p0_test"
    env.setdefault("POSTGRES_USER", "text2sql_admin")
    env.setdefault("POSTGRES_PASSWORD", "local-admin-secret")
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=script.parents[1],
    )
    assert completed.returncode == 1
    assert "not a directory" in completed.stderr


def test_run_external_p0_full_eval_twice_requires_postgres_env() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/run_external_p0_full_eval_twice.sh"
    env = {k: v for k, v in os.environ.items() if k not in ("POSTGRES_USER", "POSTGRES_PASSWORD")}
    ensure_bird_database_root(env)
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=script.parents[1],
    )
    assert completed.returncode == 1
    assert "POSTGRES_USER" in completed.stderr
