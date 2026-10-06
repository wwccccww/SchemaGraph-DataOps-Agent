"""P0 全量实测 run 目录摘要（计费后 acceptance 写入 docs/benchmark.md 用）。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunMeasured:
    run_dir: Path
    benchmark_source: str
    matched: int
    case_count: int
    execution_accuracy: float
    git_commit: str | None
    prompt_version: str | None

    @property
    def fraction_label(self) -> str:
        return f"{self.matched}/{self.case_count}"


def load_run_measured(run_dir: Path) -> RunMeasured:
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"missing summary.json under {run_dir}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise ValueError(f"summary must be object: {summary_path}")
    measured = summary.get("measured")
    if not isinstance(measured, dict):
        raise ValueError(f"summary.measured missing: {summary_path}")
    accuracy = measured.get("execution_accuracy")
    if not isinstance(accuracy, (int, float)):
        raise ValueError(f"execution_accuracy missing: {summary_path}")
    model_exec = summary.get("model_execution")
    if not isinstance(model_exec, dict):
        raise ValueError(f"model_execution missing: {summary_path}")
    matched = model_exec.get("matched")
    case_count = model_exec.get("case_count")
    if not isinstance(matched, int) or not isinstance(case_count, int):
        raise ValueError(f"matched/case_count missing: {summary_path}")
    source = summary.get("benchmark_source")
    if not isinstance(source, str):
        raise ValueError(f"benchmark_source missing: {summary_path}")
    git_commit = summary.get("git_commit")
    prompt_version = summary.get("prompt_version")
    return RunMeasured(
        run_dir=run_dir.resolve(),
        benchmark_source=source,
        matched=matched,
        case_count=case_count,
        execution_accuracy=float(accuracy),
        git_commit=str(git_commit) if git_commit is not None else None,
        prompt_version=str(prompt_version) if prompt_version is not None else None,
    )


def stability_label(first: RunMeasured, second: RunMeasured) -> str:
    if (
        first.matched != second.matched
        or abs(first.execution_accuracy - second.execution_accuracy) > 1e-9
    ):
        return "unstable"
    return "stable"


def format_report(
    tpcds_runs: list[RunMeasured],
    bird_runs: list[RunMeasured],
) -> str:
    lines: list[str] = []
    for index, run in enumerate(tpcds_runs, start=1):
        lines.append(
            f"p0_measured_tpcds_run{index}={run.fraction_label} "
            f"ex={run.execution_accuracy} dir={run.run_dir.name} "
            f"commit={run.git_commit or '?'} prompt={run.prompt_version or '?'}"
        )
    if len(tpcds_runs) == 2:
        lines.append(f"p0_stability_tpcds={stability_label(tpcds_runs[0], tpcds_runs[1])}")
    for index, run in enumerate(bird_runs, start=1):
        lines.append(
            f"p0_measured_bird_run{index}={run.fraction_label} "
            f"ex={run.execution_accuracy} dir={run.run_dir.name} "
            f"commit={run.git_commit or '?'} prompt={run.prompt_version or '?'}"
        )
    if len(bird_runs) == 2:
        lines.append(f"p0_stability_bird={stability_label(bird_runs[0], bird_runs[1])}")
    return "\n".join(lines)


def load_manifest(manifest_path: Path) -> tuple[list[Path], list[Path]]:
    tpcds: list[Path] = []
    bird: list[Path] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split("\t", 1)
        if len(parts) != 2:
            raise ValueError(f"manifest line must be SOURCE<TAB>PATH: {stripped!r}")
        source, path_text = parts[0].strip(), parts[1].strip()
        path = Path(path_text)
        if source == "tpcds-derived":
            tpcds.append(path)
        elif source == "bird":
            bird.append(path)
        else:
            raise ValueError(f"unknown manifest source {source!r}")
    return tpcds, bird


def validate_p0_acceptance_gate(
    tpcds_runs: list[RunMeasured],
    bird_runs: list[RunMeasured],
    *,
    tpcds_cases: int = 30,
    bird_min_matched: int = 7,
) -> list[str]:
    """Return human-readable failure reasons; empty list means gate passed."""
    failures: list[str] = []
    if len(tpcds_runs) != 2:
        failures.append(f"expected 2 tpcds runs, got {len(tpcds_runs)}")
    if len(bird_runs) != 2:
        failures.append(f"expected 2 bird runs, got {len(bird_runs)}")
    for index, run in enumerate(tpcds_runs, start=1):
        if run.case_count != tpcds_cases or run.matched != tpcds_cases:
            failures.append(
                f"tpcds run{index} need {tpcds_cases}/{tpcds_cases}, got {run.fraction_label}"
            )
    if len(tpcds_runs) == 2 and stability_label(tpcds_runs[0], tpcds_runs[1]) != "stable":
        failures.append("tpcds 2× runs are not stable (matched or ex differ)")
    if len(bird_runs) == 2 and stability_label(bird_runs[0], bird_runs[1]) != "stable":
        failures.append("bird 2× runs are not stable (matched or ex differ)")
    if bird_min_matched > 0:
        for index, run in enumerate(bird_runs, start=1):
            if run.matched < bird_min_matched:
                failures.append(
                    f"bird run{index} below baseline min {bird_min_matched}/50, got {run.fraction_label}"
                )
    return failures


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Summarize P0 2× full measured run directories")
    parser.add_argument("--manifest", type=Path, help="TSV from run_external_p0_full_eval_twice.sh")
    parser.add_argument("--tpcds-run", type=Path, action="append", default=[], dest="tpcds_runs")
    parser.add_argument("--bird-run", type=Path, action="append", default=[], dest="bird_runs")
    parser.add_argument(
        "--acceptance-gate",
        action="store_true",
        help="Exit 3 if TPC-DS not 30/30×2 stable or BIRD 2× not stable",
    )
    parser.add_argument(
        "--bird-min-matched",
        type=int,
        default=7,
        help="With --acceptance-gate: each BIRD run must have at least this many EX (0=disable)",
    )
    args = parser.parse_args(argv)
    tpcds_paths = list(args.tpcds_runs)
    bird_paths = list(args.bird_runs)
    if args.manifest is not None:
        manifest_tpcds, manifest_bird = load_manifest(args.manifest)
        tpcds_paths.extend(manifest_tpcds)
        bird_paths.extend(manifest_bird)
    tpcds = [load_run_measured(path) for path in tpcds_paths]
    bird = [load_run_measured(path) for path in bird_paths]
    for run in tpcds:
        if run.benchmark_source != "tpcds-derived":
            print(
                f"expected tpcds-derived run, got {run.benchmark_source}: {run.run_dir}",
                file=sys.stderr,
            )
            raise SystemExit(1)
    for run in bird:
        if run.benchmark_source != "bird":
            print(f"expected bird run, got {run.benchmark_source}: {run.run_dir}", file=sys.stderr)
            raise SystemExit(1)
    print(format_report(tpcds, bird))
    if args.acceptance_gate:
        failures = validate_p0_acceptance_gate(tpcds, bird, bird_min_matched=args.bird_min_matched)
        if failures:
            for item in failures:
                print(f"p0_acceptance_gate=fail reason={item}", file=sys.stderr)
            raise SystemExit(3)
        print("p0_acceptance_gate=pass")


if __name__ == "__main__":
    main()
