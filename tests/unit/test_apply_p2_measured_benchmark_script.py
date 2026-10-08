"""apply_p2_measured_benchmark.sh 入口。"""

from __future__ import annotations

from pathlib import Path


def test_apply_p2_measured_benchmark_script_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/apply_p2_measured_benchmark.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "p2_custom_ablation_summary" in text
    assert "--acceptance-gate" in text
    assert "--write-benchmark" in text
