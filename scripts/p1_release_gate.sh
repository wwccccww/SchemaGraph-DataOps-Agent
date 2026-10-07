#!/usr/bin/env bash
# P1：发布前无 LLM 门禁（Oracle + 实测基线 replay + 单元子集）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
if [[ -z "${POSTGRES_USER:-}" || -z "${POSTGRES_PASSWORD:-}" ]]; then
  echo "note: POSTGRES_USER/POSTGRES_PASSWORD unset — TPC-DS replay pytest will skip; verify-tpcds needs them" >&2
fi
if [[ -z "${BIRD_DATABASE_ROOT:-}" ]]; then
  echo "note: BIRD_DATABASE_ROOT unset — BIRD replay pytest will skip; verify-bird needs it" >&2
elif [[ ! -d "${BIRD_DATABASE_ROOT}" ]]; then
  echo "BIRD_DATABASE_ROOT is not a directory: ${BIRD_DATABASE_ROOT} (see .env.example minidev/MINIDEV/dev_databases)" >&2
  exit 1
fi
uv run pytest tests/unit/test_custom_cases.py::test_python_oracle_attestation_covers_every_case \
  tests/unit/test_p0_external_measured_baseline.py \
  tests/unit/test_p1_replay_gate.py \
  tests/unit/test_external_release.py \
  tests/unit/test_external_model_cli.py \
  tests/unit/test_bird_peak_executable.py \
  tests/unit/test_print_external_p0_status.py \
  tests/unit/test_run_bird_p0_full_eval_script.py \
  tests/unit/test_run_tpcds_p0_full_eval_script.py \
  tests/unit/test_run_external_p0_full_eval_script.py \
  tests/unit/test_llm_preflight.py \
  tests/unit/test_bird_profile_inventory.py \
  tests/unit/test_ablation.py \
  tests/unit/test_p1_release_gate_script.py \
  tests/unit/test_p0_post_billing_acceptance_script.py \
  tests/unit/test_wait_for_billing_and_run_p0_script.py \
  tests/unit/test_p0_measured_summary.py \
  tests/unit/test_p0_benchmark_docs.py \
  tests/unit/test_apply_p0_measured_benchmark_script.py \
  tests/unit/test_external_gold_runbook_docs.py \
  tests/unit/test_tpcds_postgres_reachable.py \
  -q
"$ROOT/scripts/verify_external_gold.sh"
