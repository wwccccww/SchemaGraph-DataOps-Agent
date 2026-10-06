"""P0 TPC-DS 2× 全量脚本契约（不调用 LLM）。"""

from __future__ import annotations

from pathlib import Path


def test_run_tpcds_p0_full_eval_twice_script_contract() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts/run_tpcds_p0_full_eval_twice.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "tpcds-derived" in text
    assert "--full" in text
    assert "check-external-release" in text
    assert "POSTGRES_USER" in text
    assert "POSTGRES_PASSWORD" in text
