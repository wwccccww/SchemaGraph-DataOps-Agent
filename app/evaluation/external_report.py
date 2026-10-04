"""按来源分开的外部评测报告。

导入本模块不会造数、不会下载模型，也不会读取自建 Target。
一次运行写入新目录。Measured 的执行准确率保持为空，直到另有带日志的模型运行。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.schemas.benchmark import BenchmarkCase

ExternalSource = Literal["tpcds-derived", "bird"]
_CUSTOM_TARGETS = ("0.83", "0.968", "0.684", "0.742", "0.81", "0.72", "0.86")


@dataclass(frozen=True)
class GoldTrace:
    """一条 Gold SQL 的执行痕迹。不包含结果行，也不进入问数 Prompt。"""

    case_id: str
    status: str
    row_count: int | None
    digest: str | None
    error: str | None

    def as_json(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "row_count": self.row_count,
            "digest": self.digest,
            "error": self.error,
        }


def build_external_summary(
    cases: Sequence[BenchmarkCase],
    traces: Sequence[GoldTrace],
    *,
    source: ExternalSource,
    benchmark_version: str,
    git_commit: str,
    database_snapshot: str,
    started_at: str,
    environment: Mapping[str, object],
) -> dict[str, object]:
    """汇总只描述这一来源。Target 固定为空，不抄自建指标。"""

    _guard_cases(source, cases)
    _guard_traces(cases, traces)
    executed = sum(1 for trace in traces if trace.status == "ok")
    return {
        "git_commit": git_commit,
        "benchmark_source": source,
        "benchmark_version": benchmark_version,
        "database_snapshot": database_snapshot,
        "model": None,
        "embedding_model": None,
        "prompt_version": None,
        "random_seed": None,
        "started_at": started_at,
        "environment": dict(environment),
        "target": None,
        "mixed_with_custom": False,
        "official_tpcds_result": False,
        "measured": {"execution_accuracy": None},
        "gold_execution": {
            "case_count": len(cases),
            "executed": executed,
            "failed": len(traces) - executed,
            "cases": [trace.as_json() for trace in traces],
        },
        "case_files": [f"cases/{trace.case_id}.json" for trace in traces],
    }


def write_external_report(
    root: Path,
    *,
    stamp: str,
    commit: str,
    summary: Mapping[str, object],
    traces: Sequence[GoldTrace],
) -> Path:
    """写入 run_<utc>_<commit>。目录已存在时拒绝。"""

    _check_stamp(stamp)
    _check_commit(commit)
    source = summary.get("benchmark_source")
    if source not in {"tpcds-derived", "bird"}:
        raise ValueError("external reports only accept tpcds-derived or bird")
    if summary.get("target") is not None or summary.get("mixed_with_custom") is not False:
        raise ValueError("external reports cannot carry a target or custom mix")
    if summary.get("official_tpcds_result") is not False:
        raise ValueError("external reports are not an official TPC-DS result")
    measured = summary.get("measured")
    if not isinstance(measured, dict) or measured.get("execution_accuracy") is not None:
        raise ValueError("external measured execution accuracy stays empty")
    encoded = json.dumps(summary, ensure_ascii=False)
    if any(token in encoded for token in _CUSTOM_TARGETS):
        raise ValueError("external reports cannot copy custom target numbers")
    if "custom_" in encoded:
        raise ValueError("external reports cannot name custom cases")
    root.mkdir(parents=True, exist_ok=True)
    directory = root / f"run_{stamp}_{commit}"
    directory.mkdir(parents=False, exist_ok=False)
    cases_dir = directory / "cases"
    cases_dir.mkdir()
    for trace in traces:
        path = cases_dir / f"{trace.case_id}.json"
        path.write_text(
            json.dumps(trace.as_json(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (directory / "summary.json").write_text(encoded + "\n", encoding="utf-8")
    return directory


def _guard_cases(source: str, cases: Sequence[BenchmarkCase]) -> None:
    if not cases:
        raise ValueError("external report needs cases")
    for case in cases:
        if case.source != source or case.id.startswith("custom_"):
            raise ValueError("refusing to mix custom cases into an external report")


def _guard_traces(cases: Sequence[BenchmarkCase], traces: Sequence[GoldTrace]) -> None:
    expected = [case.id for case in cases]
    actual = [trace.case_id for trace in traces]
    if actual != expected:
        raise ValueError("gold traces must follow the case file order")


def _check_stamp(stamp: str) -> None:
    if len(stamp) != 16 or stamp[8] != "T" or not stamp.endswith("Z"):
        raise ValueError("report stamp must look like 20261004T151200Z")
    compact = stamp[:8] + stamp[9:15]
    if not compact.isdigit():
        raise ValueError("report stamp must look like 20261004T151200Z")


def _check_commit(commit: str) -> None:
    hex_digits = "0123456789abcdef"
    valid = 7 <= len(commit) <= 40 and all(char in hex_digits for char in commit)
    if not valid:
        raise ValueError("git commit must be a hex sha")
