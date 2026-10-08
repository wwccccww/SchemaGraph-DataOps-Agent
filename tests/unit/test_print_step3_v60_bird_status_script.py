"""print_step3_v60_bird_status.sh 入口。"""

from __future__ import annotations

from pathlib import Path


def test_print_step3_v60_bird_status_script_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/print_step3_v60_bird_status.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "--step3-bird-gate" in text
    assert "step3_v60_bird_manifest.tsv" in text
