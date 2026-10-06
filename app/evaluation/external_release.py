"""外部评测发布门禁。"""

from __future__ import annotations

from dataclasses import dataclass

from app.evaluation.bird import BIRD_CASE_COUNT, load_bird_cases
from app.evaluation.external_gold import ensure_fingerprints, load_attestation, wall_clock_sensitive
from app.evaluation.tpcds import TPCDS_CASE_COUNT, load_tpcds_cases


@dataclass(frozen=True)
class ReleaseFinding:
    level: str
    message: str


def evaluate_external_release() -> list[ReleaseFinding]:
    """检查指纹、全量覆盖与 gold_matched 状态。"""

    findings: list[ReleaseFinding] = []
    for source, loader, expected in (
        ("tpcds-derived", load_tpcds_cases, TPCDS_CASE_COUNT),
        ("bird", load_bird_cases, BIRD_CASE_COUNT),
    ):
        cases = loader()
        if len(cases) != expected:
            findings.append(
                ReleaseFinding("error", f"{source} case count {len(cases)} != {expected}")
            )
            continue
        try:
            ensure_fingerprints(cases, source)  # type: ignore[arg-type]
        except RuntimeError as exc:
            findings.append(ReleaseFinding("error", str(exc)))
            continue
        document = load_attestation(source)  # type: ignore[arg-type]
        status = document.get("status")
        if status != "gold_matched":
            findings.append(
                ReleaseFinding(
                    "error",
                    f"{source} attestation is {status}; run verify and commit gold_matched",
                )
            )
        snapshot = document.get("database_snapshot")
        if not isinstance(snapshot, str) or not snapshot:
            findings.append(
                ReleaseFinding("error", f"{source} attestation missing database_snapshot")
            )
        if source == "bird":
            unstable = [case.id for case in cases if wall_clock_sensitive(case.gold_sql)]
            if unstable:
                findings.append(
                    ReleaseFinding(
                        "warn",
                        f"bird has {len(unstable)} wall-clock Gold SQL cases; "
                        "refresh attestation before comparing historical EX",
                    )
                )
    return findings


def release_ready() -> bool:
    return not any(item.level == "error" for item in evaluate_external_release())
