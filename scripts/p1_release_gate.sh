#!/usr/bin/env bash
# P1：发布前无 LLM 门禁（Oracle + 实测基线 replay + 单元子集）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 -m pytest tests/unit/test_p0_external_measured_baseline.py \
  tests/unit/test_p1_replay_gate.py \
  tests/unit/test_external_release.py \
  tests/unit/test_external_model_cli.py \
  tests/unit/test_bird_peak_executable.py \
  tests/unit/test_print_external_p0_status.py \
  tests/unit/test_run_bird_p0_full_eval_script.py \
  tests/unit/test_run_tpcds_p0_full_eval_script.py \
  tests/unit/test_run_external_p0_full_eval_script.py \
  tests/unit/test_llm_preflight.py \
  -q
"$ROOT/scripts/verify_external_gold.sh"
