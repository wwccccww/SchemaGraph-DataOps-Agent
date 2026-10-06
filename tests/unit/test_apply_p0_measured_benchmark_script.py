"""apply_p0_measured_benchmark.sh 存在且可执行。"""

from __future__ import annotations

import os
from pathlib import Path


def test_apply_p0_measured_benchmark_script_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/apply_p0_measured_benchmark.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK)
    text = script.read_text(encoding="utf-8")
    assert "--write-benchmark" in text
    assert "p0_measured_manifest.tsv" in text
