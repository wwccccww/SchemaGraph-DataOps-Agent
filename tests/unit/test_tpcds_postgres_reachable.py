"""TPC-DS replay 前置：Postgres catalog 可达性探测。"""

from __future__ import annotations

import pytest
from app.evaluation.external_data import tpcds_postgres_catalog_reachable


def test_tpcds_postgres_catalog_reachable_false_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("TPCDS_POSTGRES_USER", raising=False)
    monkeypatch.delenv("TPCDS_POSTGRES_PASSWORD", raising=False)
    assert tpcds_postgres_catalog_reachable() is False


def test_tpcds_postgres_catalog_reachable_false_when_host_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_USER", "text2sql_admin")
    monkeypatch.setenv("POSTGRES_PASSWORD", "any")
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "1")
    assert tpcds_postgres_catalog_reachable(timeout_seconds=1.0) is False
