"""BIRD dev_databases 获取脚本契约（无网络）。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_fetch_bird_dev_databases_script_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/fetch_bird_dev_databases.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK)
    text = script.read_text(encoding="utf-8")
    assert "fetch-bird-databases" in text
    assert "bird_database_root=" in text
    assert "BIRD_FETCH_ROOT" in text
    assert "BIRD_FETCH_VERIFY" in text
    assert "BIRD_FETCH_FORCE" in text
    assert "reuse existing tree" in text
    assert "minidev/MINIDEV/dev_databases" in text


def test_source_md_documents_fetch_bird_databases_cli() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "benchmarks/bird_complex/SOURCE.md").read_text(encoding="utf-8")
    assert "fetch-bird-databases" in source
    assert "minidev_0703.zip" in source


def test_fetch_script_reuses_existing_dev_databases(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/fetch_bird_dev_databases.sh"
    dev = tmp_path / "minidev/MINIDEV/dev_databases"
    dev.mkdir(parents=True)
    env = os.environ.copy()
    env["BIRD_FETCH_ROOT"] = str(tmp_path)
    completed = subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    assert "reuse existing tree" in completed.stdout
    assert "fetching minidev zip" not in completed.stdout


def test_runbook_mentions_fetch_bird_dev_databases_script() -> None:
    root = Path(__file__).resolve().parents[2]
    runbook = (root / "docs/external_gold_p0_runbook.md").read_text(encoding="utf-8")
    assert "fetch_bird_dev_databases.sh" in runbook
