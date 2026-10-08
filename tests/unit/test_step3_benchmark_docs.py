"""Step-3 v60 BIRD 实测 autogen 段落。"""

from __future__ import annotations

from pathlib import Path

STEP3_START = "<!-- step3-measured-autogen:start -->"
STEP3_END = "<!-- step3-measured-autogen:end -->"


def test_benchmark_md_has_step3_v60_autogen_pass() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "docs/benchmark.md").read_text(encoding="utf-8")
    assert STEP3_START in text
    assert STEP3_END in text
    autogen = text.split(STEP3_START, 1)[1].split(STEP3_END, 1)[0]
    assert "step3_v60_bird_gate=pass" in autogen
    assert "text-to-sql-generic-v60" in autogen
    assert "49/50" in autogen
