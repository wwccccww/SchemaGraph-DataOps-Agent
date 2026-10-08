"""Format Recovery@3 and EX from a custom ablation summary.json for docs and gates."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _fmt_rate(value: object) -> str:
    rate = _as_float(value)
    if rate is None:
        return "n/a"
    return f"{rate:.4f}"


def format_report(summary: Mapping[str, Any], *, run_dir_name: str) -> str:
    measured = summary.get("measured")
    if not isinstance(measured, dict):
        raise ValueError("summary.json missing measured object")

    complete = measured.get("complete") is True
    accuracy = measured.get("execution_accuracy")
    if not isinstance(accuracy, dict):
        raise ValueError("summary.json missing measured.execution_accuracy")

    recovery = measured.get("recovery_at_3")
    if not isinstance(recovery, dict):
        raise ValueError("summary.json missing measured.recovery_at_3")

    paired = measured.get("paired_recovery")
    if not isinstance(paired, dict):
        raise ValueError("summary.json missing measured.paired_recovery")

    graph = accuracy.get("schema_graph")
    healing = accuracy.get("self_healing")
    graph_overall = graph.get("overall") if isinstance(graph, dict) else None
    healing_overall = healing.get("overall") if isinstance(healing, dict) else None

    lines = [
        f"p2_custom_run_dir={run_dir_name}",
        f"p2_git_commit={summary.get('git_commit', 'unknown')}",
        f"p2_model={summary.get('model', 'unknown')}",
        f"p2_prompt_version={summary.get('prompt_version', 'unknown')}",
        f"p2_measured_complete={'true' if complete else 'false'}",
        f"p2_schema_graph_ex_overall={_fmt_rate(graph_overall)}",
        f"p2_self_healing_ex_overall={_fmt_rate(healing_overall)}",
        f"p2_recovery_at_3_rate={_fmt_rate(recovery.get('rate'))}",
        f"p2_recovery_at_3_recovered={recovery.get('recovered', 'n/a')}",
        f"p2_recovery_at_3_failed={recovery.get('failed', 'n/a')}",
        f"p2_recovery_at_3_denominator={recovery.get('denominator', 'n/a')}",
        f"p2_recovery_at_3_excluded_first_attempt={recovery.get('excluded_first_attempt', 'n/a')}",
        f"p2_paired_recovery_rate={_fmt_rate(paired.get('paired_recovery_rate'))}",
        f"p2_paired_recovered={paired.get('paired_recovered', 'n/a')}",
        f"p2_paired_initial_failures={paired.get('paired_initial_failures', 'n/a')}",
    ]
    if complete:
        lines.append("p2_measured_gate=pass")
    return "\n".join(lines)


def load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object in {path}")
    return payload


def resolve_run_dir(root: Path, *, run_dir: Path | None, latest: bool) -> Path:
    if run_dir is not None:
        resolved = run_dir if run_dir.is_absolute() else root / run_dir
        if not (resolved / "summary.json").is_file():
            raise FileNotFoundError(f"missing summary.json under {resolved}")
        return resolved
    if not latest:
        raise ValueError("pass --run-dir or --latest")
    custom_root = root / "reports" / "custom"
    candidates = sorted(
        (p for p in custom_root.glob("run_*") if (p / "summary.json").is_file()),
        key=lambda p: p.name,
    )
    if not candidates:
        raise FileNotFoundError(f"no run_* with summary.json under {custom_root}")
    return candidates[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize custom ablation Recovery@3 for docs/gates"
    )
    parser.add_argument("--run-dir", type=Path, default=None, help="reports/custom/run_* directory")
    parser.add_argument("--latest", action="store_true", help="use newest run under reports/custom")
    parser.add_argument("--write-benchmark", type=Path, default=None)
    parser.add_argument(
        "--acceptance-gate",
        action="store_true",
        help="exit 3 unless measured.complete and p2_measured_gate=pass in report",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        directory = resolve_run_dir(root, run_dir=args.run_dir, latest=args.latest)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    summary = load_summary(directory / "summary.json")
    report = format_report(summary, run_dir_name=directory.name)
    print(report)
    if args.write_benchmark is not None:
        from app.evaluation.p2_benchmark_docs import write_benchmark_measured_section

        write_benchmark_measured_section(args.write_benchmark, report)
    if args.acceptance_gate and "p2_measured_gate=pass" not in report.splitlines():
        print("p2_measured_gate=fail (incomplete or missing pass line)", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
