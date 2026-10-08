"""Schema 版本激活门禁。"""

from __future__ import annotations

from dataclasses import dataclass

from app.schema_registry.snapshot import SchemaSnapshot


@dataclass(frozen=True)
class GateCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ActivationGateResult:
    passed: bool
    checks: tuple[GateCheck, ...]


def evaluate_activation_gate(
    snapshot: SchemaSnapshot,
    *,
    embedding_rows: int | None = None,
    require_embeddings: bool = False,
) -> ActivationGateResult:
    checks: list[GateCheck] = []
    checks.append(
        GateCheck(
            name="non_empty_catalog",
            passed=len(snapshot.documents) > 0,
            detail=f"tables={len(snapshot.documents)}",
        )
    )
    checks.append(
        GateCheck(
            name="has_fingerprint",
            passed=snapshot.fingerprint.startswith("sha256:"),
            detail=snapshot.fingerprint[:24],
        )
    )
    if require_embeddings:
        ok = embedding_rows is not None and embedding_rows > 0
        checks.append(
            GateCheck(
                name="embeddings_present",
                passed=ok,
                detail=f"rows={embedding_rows}",
            )
        )
    passed = all(item.passed for item in checks)
    return ActivationGateResult(passed=passed, checks=tuple(checks))
