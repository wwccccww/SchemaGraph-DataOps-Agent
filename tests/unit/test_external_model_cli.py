"""external_model CLI 默认值。"""

from __future__ import annotations

import subprocess
import sys


def test_cli_documents_max_repair_rounds() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "app.evaluation.external_model", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--max-repair-rounds" in completed.stdout
