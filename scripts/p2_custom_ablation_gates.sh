#!/usr/bin/env bash
# §11 P2：自建评测无 LLM 门禁（Oracle 132 + repair_trace 落盘/schema + Recovery@3 汇总单测）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv run pytest tests/unit/test_custom_cases.py::test_python_oracle_attestation_covers_every_case \
  tests/unit/test_ablation.py::test_validate_p2_repair_traces_accepts_zero_shot_skeleton_for_all_custom_cases \
  tests/unit/test_ablation.py::test_write_ablation_report_accepts_132_custom_zero_shot_skeleton \
  tests/unit/test_ablation.py::test_summary_keeps_targets_and_does_not_pad_a_partial_run \
  tests/unit/test_run_custom_ablation_script.py \
  tests/unit/test_p2_measured_prereq_script.py \
  -q
echo "p2_custom_ablation_gates=pass (schema/oracle; measured Recovery@3: ./scripts/p2_measured_prereq.sh then ./scripts/run_custom_ablation.sh + llm_preflight)"
