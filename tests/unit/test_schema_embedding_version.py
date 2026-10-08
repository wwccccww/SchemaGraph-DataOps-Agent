"""schema_version 与 fingerprint 映射。"""

from __future__ import annotations

from app.schema_registry.indexing import schema_version_from_fingerprint


def test_schema_version_from_fingerprint_strips_prefix() -> None:
    assert schema_version_from_fingerprint("sha256:abc") == "abc"
    assert schema_version_from_fingerprint("abc") == "abc"
