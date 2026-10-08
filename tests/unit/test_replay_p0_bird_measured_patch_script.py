"""replay_p0_bird_measured_patch.sh 存在且指向 measured PATCH replay。"""

from __future__ import annotations

from pathlib import Path


def test_replay_p0_bird_measured_patch_script_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/replay_p0_bird_measured_patch.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "replay-patch-autofix" in text
    assert "BIRD_DATABASE_ROOT" in text
