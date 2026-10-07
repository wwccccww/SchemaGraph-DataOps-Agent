"""§11 P2：自建消融脚本入口。"""

from __future__ import annotations

from pathlib import Path


def test_run_custom_ablation_script_exists_and_invokes_ablation_module() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/run_custom_ablation.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "check-external-release" in text
    assert "llm_preflight" in text
    assert "app.evaluation.ablation" in text
