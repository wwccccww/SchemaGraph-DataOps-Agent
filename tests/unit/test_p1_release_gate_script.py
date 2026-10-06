"""P1 发布门禁脚本与 CI fingerprints 子集对齐。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_p1_release_gate_script_lists_core_pytest_modules() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts/p1_release_gate.sh").read_text()
    for module in (
        "test_custom_cases.py",
        "test_p0_external_measured_baseline.py",
        "test_p1_replay_gate.py",
        "test_bird_profile_inventory.py",
        "test_p1_release_gate_script.py",
        "test_llm_preflight.py",
        "test_p0_post_billing_acceptance_script.py",
    ):
        assert module in script


def test_p1_release_gate_script_documents_postgres_and_bird_env_notes() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts/p1_release_gate.sh").read_text()
    assert "POSTGRES_USER" in script
    assert "BIRD_DATABASE_ROOT" in script
    assert "skip" in script.lower()


def test_p1_release_gate_fast_pytest_subset_passes() -> None:
    """与 gate 同源模块中的快路径（无全量 replay）。"""
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            "tests/unit/test_bird_profile_inventory.py",
            "tests/unit/test_print_external_p0_status.py",
            "tests/unit/test_llm_preflight.py",
            "-q",
            "--tb=no",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env={k: v for k, v in os.environ.items() if k != "BIRD_DATABASE_ROOT"},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
