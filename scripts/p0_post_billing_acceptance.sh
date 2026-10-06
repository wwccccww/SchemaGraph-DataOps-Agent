#!/usr/bin/env bash
# P0 产品条：DeepSeek 计费恢复后，按顺序完成 Oracle 门禁 + 2× 全量 LLM（80 例可信度）。
# 402 时第一步 llm_preflight 即 exit 2；402 期间可用 --gates-only 仅跑 P1 门禁，或 ./scripts/print_external_p0_status.sh。
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
if [[ -z "${POSTGRES_USER:-}" || -z "${POSTGRES_PASSWORD:-}" ]]; then
  echo "POSTGRES_USER and POSTGRES_PASSWORD are required (TPC-DS catalog + 2× full eval)" >&2
  exit 1
fi
echo "generic_prompt=$(python3 -c 'from app.agents.text_to_sql.prompt import GENERIC_PROMPT_VERSION; print(GENERIC_PROMPT_VERSION)')"
if [[ "$GATES_ONLY" -eq 1 ]]; then
  echo "mode=gates_only (skipping llm_preflight and 2× full eval while billing blocked)"
  if [[ -n "${P0_GATES_ONLY_STUB:-}" ]]; then
    echo "p1_release_gate=stub"
  else
    "$ROOT/scripts/p1_release_gate.sh"
  fi
  echo "ops_runbook=docs/external_gold_p0_runbook.md"
  echo "next_after_billing=./scripts/p0_post_billing_acceptance.sh"
  echo "P0 gates-only OK: after billing restore, re-run without --gates-only for 2× full LLM + docs/benchmark.md."
  exit 0
fi
python3 -m app.evaluation.llm_preflight
"$ROOT/scripts/p1_release_gate.sh"
"$ROOT/scripts/run_external_p0_full_eval_twice.sh"
echo "P0 acceptance: require p0_acceptance_gate=pass above; copy p0_measured_* into docs/benchmark.md; update test_p0_external_measured_baseline when BIRD/TPC-DS fractions stabilize."
