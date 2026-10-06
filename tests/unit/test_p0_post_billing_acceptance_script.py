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


def test_p0_post_billing_acceptance_stops_on_llm_preflight_402() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p0_post_billing_acceptance.sh"
    env = os.environ.copy()
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
    assert completed.returncode == 2
    assert "402" in completed.stdout + completed.stderr or "preflight" in completed.stdout.lower()
