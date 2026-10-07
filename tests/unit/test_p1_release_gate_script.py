"""P1 发布门禁脚本与 CI fingerprints 子集对齐。"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


def _pytest_unit_modules(text: str) -> set[str]:
    collapsed = re.sub(r"\\\s*\n", " ", text)
    return set(re.findall(r"tests/unit/(test_[\w.]+\.py)", collapsed))


def test_verify_external_gold_script_sources_env() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts/verify_external_gold.sh").read_text()
    assert 'source "$ROOT/.env"' in script


def test_replay_baseline_scripts_source_env() -> None:
    root = Path(__file__).resolve().parents[2]
    for name in (
        "replay_bird_baseline.sh",
        "replay_bird_patch_autofix.sh",
        "replay_tpcds_baseline.sh",
        "replay_bird_offline_ceiling.sh",
    ):
        text = (root / "scripts" / name).read_text(encoding="utf-8")
        assert 'source "$ROOT/.env"' in text, name


def test_p1_release_gate_script_invokes_verify_external_gold() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts/p1_release_gate.sh").read_text(encoding="utf-8")
    assert "verify_external_gold.sh" in script
    assert 'p2_custom_ablation_gates.sh"' in script
    assert script.strip().endswith('"$ROOT/scripts/verify_external_gold.sh"')


def test_p1_release_gate_script_lists_core_pytest_modules() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts/p1_release_gate.sh").read_text()
    for module in (
        "test_custom_cases.py",
        "test_p0_external_measured_baseline.py",
        "test_p1_replay_gate.py",
        "test_external_model_unit.py",
        "test_bird_profile_inventory.py",
        "test_ablation.py",
        "test_p1_release_gate_script.py",
        "test_llm_preflight.py",
        "test_p0_post_billing_acceptance_script.py",
        "test_wait_for_billing_and_run_p0_script.py",
        "test_external_gold_runbook_docs.py",
        "test_tpcds_postgres_reachable.py",
        "test_p2_custom_ablation_gates_script.py",
    ):
        assert module in script


def test_p1_release_gate_pytest_modules_subset_of_external_gold_ci_fingerprints() -> None:
    """本地 p1_release_gate 的 pytest 须被 nightly fingerprints job 覆盖（超集）。"""
    root = Path(__file__).resolve().parents[2]
    gate = (root / "scripts/p1_release_gate.sh").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/external-gold.yml").read_text(encoding="utf-8")
    gate_modules = _pytest_unit_modules(gate)
    ci_modules = _pytest_unit_modules(workflow)
    assert gate_modules, "expected pytest modules in p1_release_gate.sh"
    missing = gate_modules - ci_modules
    assert not missing, (
        f"p1 gate modules missing from external-gold fingerprints: {sorted(missing)}"
    )


def test_p1_release_gate_rejects_invalid_bird_database_root() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/p1_release_gate.sh"
    env = os.environ.copy()
    env["BIRD_DATABASE_ROOT"] = "/tmp/nonexistent_bird_dev_databases_p1_gate_test"
    env.setdefault("POSTGRES_USER", "text2sql_admin")
    env.setdefault("POSTGRES_PASSWORD", "local-admin-secret")
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
        timeout=15,
    )
    assert completed.returncode == 1
    assert "not a directory" in completed.stderr


def test_p1_release_gate_script_documents_postgres_and_bird_env_notes() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts/p1_release_gate.sh").read_text()
    assert "POSTGRES_USER" in script
    assert "BIRD_DATABASE_ROOT" in script
    assert "skip" in script.lower()


def test_env_example_documents_bird_database_root_for_p1_gate() -> None:
    root = Path(__file__).resolve().parents[2]
    example = (root / ".env.example").read_text(encoding="utf-8")
    assert "BIRD_DATABASE_ROOT=" in example
    assert "p0_post_billing_acceptance.sh" in example
    assert "wait_for_billing_and_run_p0.sh" in example
    assert "P0_BIRD_MIN_MATCHED" in example
    assert "external_gold_p0_runbook.md" in example
    assert "TPCDS_POSTGRES_DB" in example or "tpcds" in example


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
