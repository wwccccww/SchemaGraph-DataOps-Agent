"""P0 组合脚本存在且会要求 BIRD_DATABASE_ROOT。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_run_external_p0_full_eval_twice_requires_bird_root() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/run_external_p0_full_eval_twice.sh"
    assert script.is_file()
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
