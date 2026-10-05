"""A/B/C/D 消融、逐条结果和不可覆盖的汇总报告。

导入本模块不会造数，也不会下载向量模型或 tokenizer。
Target 常量只读；一次运行写入新目录，不改写历史报告。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.agents.text_to_sql.prompt import PROMPT_VERSION
from app.agents.text_to_sql.workflow import (
    TEXT_TO_SQL_VARIANTS,
    ServiceBundle,
    TextToSqlVariant,
    inspect_text_to_sql,
)
from app.db.seed_data import SEED
from app.evaluation.custom_cases import load_custom_cases
from app.evaluation.ex import results_match
from app.evaluation.sql_shape import PredictionShape, describe_sql
from app.evaluation.text_to_sql import EVALUATION_MAX_ROWS
from app.graph.expand import DEFAULT_MAX_SCHEMA_TOKENS, TokenCounter, render_schema_context
from app.sandbox.errors import ExecutionError
from app.sandbox.execute import ExecutionSuccess, execute_readonly
from app.sandbox.gate import check_read_only_sql
from app.schemas.benchmark import BenchmarkCase
from app.schemas.catalog import TableDocument

ABLATION_VARIANTS: tuple[TextToSqlVariant, ...] = TEXT_TO_SQL_VARIANTS
GRAPH_VARIANTS = frozenset({"schema_graph", "self_healing"})
EMBEDDING_MODEL = "BAAI/bge-m3"
BENCHMARK_SOURCE = "custom"
BENCHMARK_VERSION = "ecommerce-v1"
TARGETS: dict[str, float] = {
    "execution_accuracy": 0.83,
    "junction_recall": 0.968,
    "planner_cost_drop": 0.684,
    "execution_time_drop": 0.742,
    "shared_read_blocks_drop": 0.810,
    "optimize_pass_at_1": 0.72,
    "optimize_pass_at_3": 0.86,
}
Difficulty = Literal["basic", "medium", "complex"]
SqlExecute = Callable[..., Awaitable[ExecutionSuccess | ExecutionError]]


@dataclass(frozen=True)
class CaseResult:
    """一条用例在一个消融组上的原始结果。"""

    case_id: str
    variant: str
    passed: bool
    attempts: int
    seed_tables: tuple[str, ...]
    expanded_tables: tuple[str, ...]
    junction_recall: float | None
    schema_tokens: int
    latency_ms: int
    error_category: str | None
    difficulty: str
    ex: int
    leaked_junctions: tuple[str, ...]
    prediction: PredictionShape = field(default_factory=PredictionShape.empty)

    def as_json(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "variant": self.variant,
            "passed": self.passed,
            "attempts": self.attempts,
            "seed_tables": list(self.seed_tables),
            "expanded_tables": list(self.expanded_tables),
            "junction_recall": self.junction_recall,
            "schema_tokens": self.schema_tokens,
            "latency_ms": self.latency_ms,
            "error_category": self.error_category,
            "difficulty": self.difficulty,
            "ex": self.ex,
            "leaked_junctions": list(self.leaked_junctions),
            "prediction": self.prediction.as_json(),
        }


def junction_recall_for_case(
    case: BenchmarkCase,
    variant: str,
    seed_tables: Sequence[str],
    expanded_tables: Sequence[str],
) -> tuple[float | None, tuple[str, ...]]:
    """图扩展才计算召回。种子泄漏的用例不进入平均。"""

    required = list(case.required_junctions)
    if not required or variant not in GRAPH_VARIANTS:
        return None, ()
    leaked = tuple(name for name in required if name in seed_tables)
    if leaked:
        return None, leaked
    found = sum(1 for name in required if name in expanded_tables)
    return found / len(required), ()


def baseline_schema_tokens(
    documents: Sequence[TableDocument],
    token_counter: TokenCounter,
) -> int:
    """全量非 Junction 表文档的 token，作为 Schema 上下文基线。"""

    entities = [document for document in documents if not document.is_junction]
    return token_counter.count(render_schema_context(entities))


def percentile(values: Sequence[int], fraction: float) -> float | None:
    """线性插值分位数。不依赖 NumPy。"""

    if not values:
        return None
    if not 0 <= fraction <= 1:
        raise ValueError("percentile fraction must be between 0 and 1")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def build_summary(
    records: Sequence[CaseResult],
    *,
    case_ids: Sequence[str],
    git_commit: str,
    database_snapshot: str,
    model: str,
    started_at: str,
    baseline_tokens: int | None,
) -> dict[str, object]:
    """汇总必须指向逐条文件。Target 来自常量，不从本次结果写入。"""

    by_variant = {
        variant: [record for record in records if record.variant == variant]
        for variant in ABLATION_VARIANTS
    }
    expected = {(case_id, variant) for case_id in case_ids for variant in ABLATION_VARIANTS}
    actual = {(record.case_id, record.variant) for record in records}
    complete = bool(case_ids) and actual == expected
    case_files = [
        f"cases/{record.case_id}__{record.variant}.json"
        for record in sorted(records, key=_record_order(case_ids))
    ]
    graph_records = by_variant["schema_graph"]
    recall_rate, recall_denominator, leaks = _junction_average(graph_records)
    enhanced = [record.schema_tokens for record in graph_records]
    return {
        "git_commit": git_commit,
        "benchmark_source": BENCHMARK_SOURCE,
        "benchmark_version": BENCHMARK_VERSION,
        "database_snapshot": database_snapshot,
        "model": model,
        "embedding_model": EMBEDDING_MODEL,
        "prompt_version": PROMPT_VERSION,
        "random_seed": SEED,
        "started_at": started_at,
        "environment": {"postgres": "16", "cpu_limit": 2, "memory_limit_gb": 2},
        "target": dict(TARGETS),
        "measured": {
            "complete": complete,
            "execution_accuracy": {
                variant: _accuracy(by_variant[variant]) for variant in ABLATION_VARIANTS
            },
            "pass_at_1": {
                "variant": "schema_graph",
                "rate": _accuracy(graph_records)["overall"],
                "denominator": len(graph_records),
            },
            "pass_at_3": None,
            "recovery_at_3": _recovery(by_variant["self_healing"]),
            "junction_recall": {
                "variant": "schema_graph",
                "rate": recall_rate,
                "denominator": recall_denominator,
                "excluded_leaks": leaks,
            },
            "schema_tokens": {
                "baseline": baseline_tokens,
                "enhanced_mean": _mean(enhanced),
                "enhanced_median": percentile(enhanced, 0.5),
                "enhanced_p95": percentile(enhanced, 0.95),
                "over_3500": sum(1 for value in enhanced if value > DEFAULT_MAX_SCHEMA_TOKENS),
                "count": len(enhanced),
            },
            "planner_cost_drop": None,
            "execution_time_drop": None,
            "shared_read_blocks_drop": None,
            "optimize_pass_at_1": None,
            "optimize_pass_at_3": None,
        },
        "case_files": case_files,
    }


def write_ablation_report(
    root: Path,
    *,
    stamp: str,
    commit: str,
    summary: Mapping[str, object],
    records: Sequence[CaseResult],
) -> Path:
    """写入 run_<utc>_<commit>。目录已存在时拒绝，避免覆盖历史报告。"""

    _check_stamp(stamp)
    _check_commit(commit)
    root.mkdir(parents=True, exist_ok=True)
    directory = root / f"run_{stamp}_{commit}"
    directory.mkdir(parents=False, exist_ok=False)
    cases_dir = directory / "cases"
    cases_dir.mkdir()
    for record in records:
        path = cases_dir / f"{record.case_id}__{record.variant}.json"
        path.write_text(
            json.dumps(record.as_json(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (directory / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return directory


async def evaluate_case(
    case: BenchmarkCase,
    services: ServiceBundle,
    *,
    variant: TextToSqlVariant,
    execute: SqlExecute = execute_readonly,
) -> CaseResult:
    """生成并执行 Agent SQL。Gold SQL 不进入工作流。"""

    started = time.perf_counter()
    inspection = await inspect_text_to_sql(
        services,
        question=case.question,
        database_id=case.database_id,
        execute=True,
        max_rows=1000,
        variant=variant,
    )
    response = inspection.response
    latency_ms = int((time.perf_counter() - started) * 1000)
    context = response.schema_context
    seeds = tuple(context.seed_tables) if context is not None else ()
    expanded = tuple(context.expanded_tables) if context is not None else ()
    tokens = context.token_count if context is not None else 0
    recall, leaked = junction_recall_for_case(case, variant, seeds, expanded)
    ex = 0
    if response.status == "succeeded" and response.sql is not None:
        ex = await _execution_accuracy(case, response.sql, execute)
    error = None if response.error is None else response.error.category
    return CaseResult(
        case_id=case.id,
        variant=variant,
        passed=ex == 1,
        attempts=response.attempts or 0,
        seed_tables=seeds,
        expanded_tables=expanded,
        junction_recall=recall,
        schema_tokens=tokens,
        latency_ms=latency_ms,
        error_category=None if ex == 1 else error,
        difficulty=case.difficulty,
        ex=ex,
        leaked_junctions=leaked,
        prediction=describe_sql(inspection.generated_sql),
    )


async def run_ablation(
    services: ServiceBundle,
    cases: Sequence[BenchmarkCase],
    *,
    variants: Sequence[TextToSqlVariant] = ABLATION_VARIANTS,
    documents: Sequence[TableDocument] | None = None,
    token_counter: TokenCounter | None = None,
    execute: SqlExecute = execute_readonly,
) -> tuple[list[CaseResult], int | None]:
    """按用例文件顺序和 A/B/C/D 顺序运行。不在这里造数。"""

    records: list[CaseResult] = []
    for case in cases:
        for variant in variants:
            records.append(await evaluate_case(case, services, variant=variant, execute=execute))
    baseline = None
    if documents is not None and token_counter is not None:
        baseline = baseline_schema_tokens(documents, token_counter)
    return records, baseline


def main(argv: list[str] | None = None) -> None:
    """命令行入口。缺少密钥时在真正调用模型时失败。"""

    parser = argparse.ArgumentParser(description="运行自建 Text-to-SQL 消融并写入新报告目录")
    parser.add_argument("--output", default="reports/custom")
    parser.add_argument("--model", default=None)
    parser.add_argument("--snapshot", default=None)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(_run_cli(args.output, model=args.model, snapshot=args.snapshot))


async def _run_cli(output: str, *, model: str | None, snapshot: str | None) -> None:
    from app.agents.text_to_sql.runtime import get_default_services
    from app.config.settings import get_settings
    from app.db.catalog import load_table_documents
    from app.db.engine import get_sandbox_engine
    from app.db.seed_data import build_dataset

    services = get_default_services()
    cases = load_custom_cases()
    async with get_sandbox_engine().connect() as conn:
        documents = await load_table_documents(conn)
    records, baseline = await run_ablation(
        services,
        cases,
        documents=documents,
        token_counter=services.token_counter,
    )
    started = datetime.now(UTC).replace(microsecond=0)
    summary = build_summary(
        records,
        case_ids=[case.id for case in cases],
        git_commit=_git_commit(),
        database_snapshot=snapshot or build_dataset().digest,
        model=model or get_settings().deepseek_model,
        started_at=started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        baseline_tokens=baseline,
    )
    directory = write_ablation_report(
        Path(output),
        stamp=started.strftime("%Y%m%dT%H%M%SZ"),
        commit=_git_commit(),
        summary=summary,
        records=records,
    )
    logging.getLogger(__name__).info("wrote %s", directory)


async def _execution_accuracy(
    case: BenchmarkCase,
    agent_sql: str,
    execute: SqlExecute,
) -> int:
    decision = check_read_only_sql(case.gold_sql)
    if decision.error is not None:
        raise RuntimeError(f"gold SQL failed the read-only gate: {case.id}")
    agent = await execute(agent_sql, max_rows=EVALUATION_MAX_ROWS)
    gold = await execute(decision.sql, max_rows=EVALUATION_MAX_ROWS)
    if isinstance(agent, ExecutionError) or isinstance(gold, ExecutionError):
        return 0
    matched = results_match(
        agent.rows,
        gold.rows,
        order_sensitive=case.order_sensitive,
        numeric_tolerance=case.numeric_tolerance,
    )
    return 1 if matched else 0


def _accuracy(records: Sequence[CaseResult]) -> dict[str, object]:
    def rate(selected: Sequence[CaseResult]) -> float | None:
        if not selected:
            return None
        return sum(record.ex for record in selected) / len(selected)

    return {
        "overall": rate(records),
        "basic": rate([record for record in records if record.difficulty == "basic"]),
        "medium": rate([record for record in records if record.difficulty == "medium"]),
        "complex": rate([record for record in records if record.difficulty == "complex"]),
        "denominator": len(records),
    }


def _recovery(records: Sequence[CaseResult]) -> dict[str, object]:
    first = [record for record in records if record.passed and record.attempts == 1]
    recovered = [record for record in records if record.passed and record.attempts > 1]
    failed = [record for record in records if not record.passed]
    denominator = len(recovered) + len(failed)
    rate = None if denominator == 0 else len(recovered) / denominator
    return {
        "rate": rate,
        "recovered": len(recovered),
        "failed": len(failed),
        "excluded_first_attempt": len(first),
        "denominator": denominator,
    }


def _junction_average(records: Sequence[CaseResult]) -> tuple[float | None, int, list[str]]:
    leaks = [record.case_id for record in records if record.leaked_junctions]
    scored = [record.junction_recall for record in records if record.junction_recall is not None]
    if not scored:
        return None, 0, leaks
    return sum(scored) / len(scored), len(scored), leaks


def _mean(values: Sequence[int]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _record_order(case_ids: Sequence[str]) -> Callable[[CaseResult], tuple[int, int]]:
    positions = {case_id: index for index, case_id in enumerate(case_ids)}
    variants: dict[str, int] = {name: index for index, name in enumerate(ABLATION_VARIANTS)}

    def key(record: CaseResult) -> tuple[int, int]:
        return (positions.get(record.case_id, len(positions)), variants.get(record.variant, 0))

    return key


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


def _git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


if __name__ == "__main__":
    main()
