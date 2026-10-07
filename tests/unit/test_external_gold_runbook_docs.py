"""外部 Gold P0 运维文档与入口交叉引用（无 LLM）。"""

from __future__ import annotations

from pathlib import Path


def test_external_gold_p0_runbook_exists_and_benchmark_links_it() -> None:
    root = Path(__file__).resolve().parents[2]
    runbook = root / "docs/external_gold_p0_runbook.md"
    benchmark = (root / "docs/benchmark.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert runbook.is_file(), "missing docs/external_gold_p0_runbook.md"
    assert "external_gold_p0_runbook.md" in benchmark
    assert "external_gold_p0_runbook.md" in readme
    body = runbook.read_text(encoding="utf-8")
    assert "p0_post_billing_acceptance.sh" in body
    assert "wait_for_billing_and_run_p0.sh" in body
    assert "--gates-only" in body
    assert "ops_runbook=" in body
    assert "unattended_after_billing=" in body
    assert "verify_external_gold.sh" in body
    assert "退出码" in body or "Exit:" in body
    assert "p0_measured_tpcds_run1=" in body
    assert "p0_acceptance_gate=pass" in body
    assert "p0_measured_manifest.tsv" in body
    assert "apply_p0_measured_benchmark.sh" in body
    assert "p0_baseline_followup" in body
    assert "P0_WAIT_CONFIRM_POLLS" in body
    assert "p0-measured-autogen" in body or "P0_APPLY_BENCHMARK" in body
    assert "tpcds_postgres_catalog_reachable" in body
    assert "bird_sqlite=" in body
    assert "fetch_bird_dev_databases.sh" in body
    assert "replay_skipped=external_p0_status_skip_replay" in body
    assert "p0_post_billing=blocked_resume_poll" in body


def test_external_gold_ci_fingerprints_job_includes_runbook_docs_test() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/external-gold.yml").read_text(encoding="utf-8")
    assert "test_external_gold_runbook_docs.py" in workflow
    assert "docs/external_gold_p0_runbook.md" in workflow


def test_external_gold_replay_gate_job_fetches_bird_and_runs_p1_replay() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/external-gold.yml").read_text(encoding="utf-8")
    assert "replay-gate:" in workflow
    assert "fetch_bird_dev_databases.sh" in workflow
    assert "test_p1_replay_gate.py" in workflow
    assert "test_replay_snapshot_paths.py" in workflow
