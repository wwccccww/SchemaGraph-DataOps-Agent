"""按来源分开的外部评测报告。

导入本模块不会造数、不会下载模型，也不会读取自建 Target。
一次运行写入新目录。Measured 的执行准确率保持为空，直到另有带日志的模型运行。
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.schemas.benchmark import BenchmarkCase

ExternalSource = Literal["tpcds-derived", "bird"]
_CUSTOM_TARGETS = ("0.83", "0.968", "0.684", "0.742", "0.81", "0.72", "0.86")
_DIALECT_ERRORS = frozenset({"syntax_error", "disallowed_function"})


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


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


@dataclass(frozen=True)
class ModelCaseTrace:
    """一条外部模型预测。Gold 结果行不在这里。"""

    case_id: str
    database_id: str
    primary_class: str
    ex: int
    error_category: str | None
    attempts: int
    seed_tables: tuple[str, ...]
    expanded_tables: tuple[str, ...]
    leaked_tables: tuple[str, ...]
    ecommerce_rule_hits: tuple[str, ...]
    prediction: Mapping[str, object]
    normalized_message: str | None = None
    context_recall: float | None = None
    sql_table_recall: float | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "database_id": self.database_id,
            "primary_class": self.primary_class,
            "ex": self.ex,
            "error_category": self.error_category,
            "normalized_message": self.normalized_message,
            "attempts": self.attempts,
            "seed_tables": list(self.seed_tables),
            "expanded_tables": list(self.expanded_tables),
            "context_recall": self.context_recall,
            "sql_table_recall": self.sql_table_recall,
            "leaked_tables": list(self.leaked_tables),
            "ecommerce_rule_hits": list(self.ecommerce_rule_hits),
            "prediction": dict(self.prediction),
        }


def build_external_model_summary(
    traces: Sequence[ModelCaseTrace],
    *,
    source: ExternalSource,
    benchmark_version: str,
    git_commit: str,
    database_snapshot: str,
    started_at: str,
    model: str,
    prompt_version: str,
    environment: Mapping[str, object],
) -> dict[str, object]:
    """汇总一次真实模型运行。准确率等于 matched / 用例数。"""

    _guard_model_traces(source, traces)
    if model.strip() == "" or prompt_version.strip() == "":
        raise ValueError("model reports need a model and prompt version")
    matched = sum(1 for trace in traces if trace.primary_class == "matched")
    sql_errors = sum(1 for trace in traces if trace.primary_class == "sql_error")
    dialect_errors = sum(1 for trace in traces if trace.error_category in _DIALECT_ERRORS)
    return {
        "git_commit": git_commit,
        "benchmark_source": source,
        "benchmark_version": benchmark_version,
        "database_snapshot": database_snapshot,
        "model": model,
        "embedding_model": "lexical",
        "prompt_version": prompt_version,
        "random_seed": None,
        "started_at": started_at,
        "environment": dict(environment),
        "target": None,
        "mixed_with_custom": False,
        "official_tpcds_result": False,
        "measured": {"execution_accuracy": matched / len(traces)},
        "model_execution": {
            "case_count": len(traces),
            "matched": matched,
            "sql_error": sql_errors,
            "other_result_mismatch": sum(
                1 for trace in traces if trace.primary_class == "other_result_mismatch"
            ),
            "executable_rate": (len(traces) - sql_errors) / len(traces),
            "dialect_error_rate": dialect_errors / len(traces),
            "context_recall": _mean(
                [trace.context_recall for trace in traces if trace.context_recall is not None]
            ),
            "sql_table_recall": _mean(
                [trace.sql_table_recall for trace in traces if trace.sql_table_recall is not None]
            ),
            "ecommerce_rule_cases": sum(1 for trace in traces if trace.ecommerce_rule_hits),
            "cross_database_leaks": sum(1 for trace in traces if trace.leaked_tables),
        },
        "case_files": [f"cases/{trace.case_id}.json" for trace in traces],
    }


def write_external_model_report(
    root: Path,
    *,
    stamp: str,
    commit: str,
    summary: Mapping[str, object],
    traces: Sequence[ModelCaseTrace],
) -> Path:
    """写入带执行准确率的模型报告。不放宽 Gold 报告的空准确率约束。"""

    _check_stamp(stamp)
    _check_commit(commit)
    _guard_model_summary(summary, traces)
    encoded = json.dumps(summary, ensure_ascii=False)
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


def _guard_model_traces(source: str, traces: Sequence[ModelCaseTrace]) -> None:
    if not traces:
        raise ValueError("model report needs cases")
    if source not in {"tpcds-derived", "bird"}:
        raise ValueError("external reports only accept tpcds-derived or bird")
    classes = {"matched", "sql_error", "other_result_mismatch"}
    for trace in traces:
        if trace.case_id.startswith("custom_") or "custom_" in trace.case_id:
            raise ValueError("external reports cannot name custom cases")
        if trace.database_id in {"ecommerce", "text2sql_db"}:
            raise ValueError("model reports cannot use the ecommerce database")
        if trace.primary_class not in classes:
            raise ValueError("model case class is not recognized")
        if trace.ex not in {0, 1}:
            raise ValueError("model execution accuracy uses 0 or 1")
        if (trace.primary_class == "matched") != (trace.ex == 1):
            raise ValueError("matched cases are the only ones with execution accuracy 1")


def _guard_model_summary(summary: Mapping[str, object], traces: Sequence[ModelCaseTrace]) -> None:
    source = summary.get("benchmark_source")
    if not isinstance(source, str):
        raise ValueError("external reports only accept tpcds-derived or bird")
    _guard_model_traces(source, traces)
    if summary.get("model") in {None, ""} or summary.get("prompt_version") in {None, ""}:
        raise ValueError("model reports need a model and prompt version")
    if summary.get("target") is not None or summary.get("mixed_with_custom") is not False:
        raise ValueError("external reports cannot carry a target or custom mix")
    if summary.get("official_tpcds_result") is not False:
        raise ValueError("external reports are not an official TPC-DS result")
    measured = summary.get("measured")
    accuracy = measured.get("execution_accuracy") if isinstance(measured, dict) else None
    if not isinstance(accuracy, float):
        raise ValueError("model reports need a measured execution accuracy")
    matched = sum(1 for trace in traces if trace.primary_class == "matched")
    if not math.isclose(accuracy, matched / len(traces), rel_tol=0, abs_tol=1e-9):
        raise ValueError("measured execution accuracy must equal the matched ratio")
    copied = any(
        math.isclose(accuracy, target, rel_tol=0, abs_tol=1e-12)
        for target in _custom_target_values()
    )
    if copied:
        raise ValueError("external reports cannot copy custom target numbers")
    if _redacted_summary_copies_custom_targets(summary):
        raise ValueError("external reports cannot copy custom target numbers")
    files = summary.get("case_files")
    expected = [f"cases/{trace.case_id}.json" for trace in traces]
    if files != expected:
        raise ValueError("model case files must follow the trace order")


def _custom_target_values() -> tuple[float, ...]:
    return tuple(float(token) for token in _CUSTOM_TARGETS)


def _redacted_summary_copies_custom_targets(summary: Mapping[str, object]) -> bool:
    cloned = json.loads(json.dumps(summary, ensure_ascii=False))
    if not isinstance(cloned, dict):
        return True
    measured = cloned.get("measured")
    if isinstance(measured, dict):
        measured["execution_accuracy"] = None
    execution = cloned.get("model_execution")
    if isinstance(execution, dict):
        for key in (
            "executable_rate",
            "dialect_error_rate",
            "context_recall",
            "sql_table_recall",
        ):
            execution[key] = None
    encoded = json.dumps(cloned, ensure_ascii=False)
    return any(token in encoded for token in _CUSTOM_TARGETS) or "custom_" in encoded
