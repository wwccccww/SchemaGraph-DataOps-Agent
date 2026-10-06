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
    assert "--gates-only" in body

