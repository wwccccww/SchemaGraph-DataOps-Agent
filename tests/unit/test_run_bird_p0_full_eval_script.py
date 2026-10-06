"""P0 全量脚本存在且会在无 BIRD 库时快速失败。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_run_bird_p0_full_eval_twice_requires_database_root() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/run_bird_p0_full_eval_twice.sh"
    assert script.is_file()
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k != "BIRD_DATABASE_ROOT"},
        cwd=script.parents[1],
    )
    assert completed.returncode != 0
    assert "BIRD_DATABASE_ROOT" in completed.stderr
