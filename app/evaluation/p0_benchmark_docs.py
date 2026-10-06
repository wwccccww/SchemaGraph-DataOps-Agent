"""Patch docs/benchmark.md P0 measured autogen section after acceptance gate passes."""

from __future__ import annotations

import re
from pathlib import Path

P0_MEASURED_AUTOGEN_START = "<!-- p0-measured-autogen:start -->"
P0_MEASURED_AUTOGEN_END = "<!-- p0-measured-autogen:end -->"


def format_measured_autogen_inner(
    report_text: str, *, gate_pass_line: str = "p0_acceptance_gate=pass"
) -> str:
    """Markdown body placed between autogen markers (fenced text block)."""
    lines = [line for line in report_text.strip().splitlines() if line.strip()]
    if gate_pass_line not in lines:
        lines.append(gate_pass_line)
    body = "\n".join(lines)
    return f"```text\n{body}\n```"


def patch_benchmark_measured_section(benchmark_text: str, report_text: str) -> str:
    if (
        P0_MEASURED_AUTOGEN_START not in benchmark_text
        or P0_MEASURED_AUTOGEN_END not in benchmark_text
    ):
        raise ValueError(
            f"benchmark.md must contain {P0_MEASURED_AUTOGEN_START} and {P0_MEASURED_AUTOGEN_END}"
        )
    inner = format_measured_autogen_inner(report_text)
    pattern = re.compile(
        re.escape(P0_MEASURED_AUTOGEN_START) + r".*?" + re.escape(P0_MEASURED_AUTOGEN_END),
        flags=re.DOTALL,
    )
    replacement = f"{P0_MEASURED_AUTOGEN_START}\n\n{inner}\n\n{P0_MEASURED_AUTOGEN_END}"
    patched, count = pattern.subn(replacement, benchmark_text, count=1)
    if count != 1:
        raise ValueError("expected exactly one p0-measured-autogen section in benchmark.md")
    return patched


def write_benchmark_measured_section(benchmark_path: Path, report_text: str) -> None:
    text = benchmark_path.read_text(encoding="utf-8")
    patched = patch_benchmark_measured_section(text, report_text)
    benchmark_path.write_text(patched, encoding="utf-8")
