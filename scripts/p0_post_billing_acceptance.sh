#!/usr/bin/env bash
# P0 产品条：DeepSeek 计费恢复后，按顺序完成 Oracle 门禁 + 2× 全量 LLM（80 例可信度）。
# 402 时第一步 llm_preflight 即 exit 2；402 期间可用 --gates-only 仅跑 P1 门禁，或 ./scripts/print_external_p0_status.sh。
# Exit: 0 OK；1 缺 BIRD_DATABASE_ROOT / POSTGRES_*；2 llm_preflight（402 等）；3 p0_measured_summary --acceptance-gate 未 pass；4 已有全量 acceptance 在跑（flock）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
GATES_ONLY=0
if [[ "${1:-}" == "--gates-only" ]]; then
  GATES_ONLY=1
fi
if [[ -z "${BIRD_DATABASE_ROOT:-}" ]]; then
  echo "BIRD_DATABASE_ROOT is required (path to dev_databases)" >&2
  exit 1
fi
if [[ ! -d "${BIRD_DATABASE_ROOT}" ]]; then
  echo "BIRD_DATABASE_ROOT is not a directory: ${BIRD_DATABASE_ROOT} (see .env.example minidev/MINIDEV/dev_databases)" >&2
  exit 1
fi
if [[ -z "${POSTGRES_USER:-}" || -z "${POSTGRES_PASSWORD:-}" ]]; then
  echo "POSTGRES_USER and POSTGRES_PASSWORD are required (TPC-DS catalog + 2× full eval)" >&2
  exit 1
fi
echo "generic_prompt=$(python3 -c 'from app.agents.text_to_sql.prompt import GENERIC_PROMPT_VERSION; print(GENERIC_PROMPT_VERSION)')"
if python3 -c "from app.evaluation.external_data import tpcds_postgres_catalog_reachable; raise SystemExit(0 if tpcds_postgres_catalog_reachable() else 1)"; then
  echo "tpcds_postgres_catalog=ready"
else
  echo "tpcds_postgres_catalog=unreachable"
fi
if [[ "$GATES_ONLY" -eq 1 ]]; then
  echo "mode=gates_only (skipping llm_preflight and 2× full eval while billing blocked)"
  if [[ -n "${P0_GATES_ONLY_STUB:-}" ]]; then
    echo "p1_release_gate=stub"
  else
    "$ROOT/scripts/p1_release_gate.sh"
  fi
  echo "ops_runbook=docs/external_gold_p0_runbook.md"
  echo "next_after_billing=./scripts/p0_post_billing_acceptance.sh"
  echo "unattended_after_billing=./scripts/wait_for_billing_and_run_p0.sh"
  echo "P0 gates-only OK: after billing restore, re-run without --gates-only for 2× full LLM + docs/benchmark.md."
  exit 0
fi
P0_ACCEPTANCE_LOCK_FILE="${P0_ACCEPTANCE_LOCK_FILE:-/tmp/p0_post_billing_acceptance.lock}"
exec 9>"$P0_ACCEPTANCE_LOCK_FILE"
if ! flock -n 9; then
  echo "p0_acceptance=already_running lock=${P0_ACCEPTANCE_LOCK_FILE}" >&2
  exit 4
fi
_p0_run_llm_preflight() {
  if [[ -n "${P0_FROM_BILLING_WAIT:-}" ]]; then
    local retries="${P0_PREFLIGHT_WAIT_RETRIES:-6}"
    local sleep_sec="${P0_PREFLIGHT_WAIT_SLEEP:-20}"
    local i
    for ((i = 1; i <= retries; i++)); do
      if python3 -m app.evaluation.llm_preflight 2>/tmp/p0_acceptance_preflight.err; then
        return 0
      fi
      if grep -q "402" /tmp/p0_acceptance_preflight.err 2>/dev/null; then
        echo "llm_preflight=blocked_billing_402 retry=${i}/${retries}" >&2
        if [[ "$i" -lt "$retries" ]]; then
          sleep "$sleep_sec"
        fi
      else
        cat /tmp/p0_acceptance_preflight.err >&2
        return 2
      fi
    done
    cat /tmp/p0_acceptance_preflight.err >&2
    return 2
  fi
  python3 -m app.evaluation.llm_preflight
}
_p0_run_llm_preflight || exit 2
if [[ -n "${P0_ACCEPTANCE_PREFLIGHT_ONLY:-}" ]]; then
  echo "p0_acceptance_preflight_only=ok"
  exit 0
fi
"$ROOT/scripts/p1_release_gate.sh"
"$ROOT/scripts/run_external_p0_full_eval_twice.sh"
if [[ "${P0_APPLY_BENCHMARK:-1}" == "1" ]]; then
  "$ROOT/scripts/apply_p0_measured_benchmark.sh"
else
  echo "p0_benchmark_docs=skipped (set P0_APPLY_BENCHMARK=1 to patch docs/benchmark.md)"
fi
echo "ops_runbook=docs/external_gold_p0_runbook.md"
echo "unattended_after_billing=./scripts/wait_for_billing_and_run_p0.sh"
echo "P0 acceptance: require p0_acceptance_gate=pass above; benchmark autogen via apply_p0_measured_benchmark.sh; update test_p0_external_measured_baseline when BIRD/TPC-DS fractions stabilize."
