"""p2_measured_prereq.sh 存在且覆盖 seed + retrieval.index。"""

from __future__ import annotations

from pathlib import Path


def test_p2_measured_prereq_script_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p2_measured_prereq.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "app.db.seed" in text
    assert "app.retrieval.index" in text
    assert "POSTGRES_DB" in text
