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
