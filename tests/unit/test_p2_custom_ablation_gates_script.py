"""§11 P2：自建消融无 LLM 门禁脚本。"""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_p2_custom_ablation_gates_script_exists() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/p2_custom_ablation_gates.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "test_validate_p2_repair_traces_accepts_zero_shot_skeleton_for_all_custom_cases" in text
    assert "run_custom_ablation.sh" in text


def test_p2_custom_ablation_gates_script_passes() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/p2_custom_ablation_gates.sh"
    completed = subprocess.run(
        [str(script)], check=False, capture_output=True, text=True, cwd=script.parents[1]
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "p2_custom_ablation_gates=pass" in completed.stdout
    assert "pgvector" in completed.stdout
