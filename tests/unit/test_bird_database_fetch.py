"""BIRD dev_databases fetch sources (no network)."""

from __future__ import annotations

import inspect

from app.evaluation import bird
from app.evaluation.external_data import _download, fetch_bird_databases


def test_bird_database_mirror_constants_pinned() -> None:
    assert bird.DATABASE_MIRROR_URL.startswith("https://")
    assert len(bird.DATABASE_MIRROR_ZIP_SHA256) == 64


def test_fetch_bird_databases_tries_drive_then_mirror() -> None:
    source = inspect.getsource(fetch_bird_databases)
    assert "DATABASE_URL" in source
    assert "DATABASE_MIRROR_URL" in source
    assert source.index("DATABASE_URL") < source.index("DATABASE_MIRROR_URL")


def test_download_retries_transient_network_errors() -> None:
    source = inspect.getsource(_download)
    assert "SSLError" in source
    assert "retries" in source
