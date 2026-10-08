"""e5482a4 vendored measured run 复分脚本（无 LLM）。"""

from __future__ import annotations

from pathlib import Path


def test_replay_e5482a4_scripts_default_to_vendored_run_dir() -> None:
    root = Path(__file__).resolve().parents[2]
    for name in ("replay_e5482a4_baseline.sh", "replay_e5482a4_patch_autofix.sh"):
        text = (root / "scripts" / name).read_text(encoding="utf-8")
        assert "bird_e5482a4_measured_run_dir" in text, name
        assert "replay_bird_baseline.sh" in text, name
    patch = (root / "scripts/replay_e5482a4_patch_autofix.sh").read_text(encoding="utf-8")
    assert "--replay-patch-autofix" in patch
