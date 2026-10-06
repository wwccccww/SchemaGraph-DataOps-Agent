#!/usr/bin/env bash
# P0/P1：打印外部 Gold 门禁与无 LLM replay 摘要（402 时运维用）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
echo "== check-external-release =="
python3 -m app.evaluation.external_data check-external-release
echo "release_ready=$(python3 -c 'from app.evaluation.external_release import release_ready; print(release_ready())')"
echo "generic_prompt=$(python3 -c 'from app.agents.text_to_sql.prompt import GENERIC_PROMPT_VERSION; print(GENERIC_PROMPT_VERSION)')"
PREFLIGHT_LOG="$(mktemp)"
trap 'rm -f "$PREFLIGHT_LOG"' EXIT
if python3 -m app.evaluation.llm_preflight 2>"$PREFLIGHT_LOG"; then
  echo "llm_preflight=ready"
else
  if grep -q "402" "$PREFLIGHT_LOG"; then
    echo "llm_preflight=blocked_billing_402"
  elif grep -q "DEEPSEEK_API_KEY is not set" "$PREFLIGHT_LOG"; then
    echo "llm_preflight=blocked_no_api_key"
  else
    echo "llm_preflight=blocked"
  fi
fi
if python3 -c "from app.evaluation.external_data import tpcds_postgres_catalog_reachable; raise SystemExit(0 if tpcds_postgres_catalog_reachable() else 1)"; then
  echo "tpcds_postgres_catalog=ready"
else
  echo "tpcds_postgres_catalog=unreachable"
fi
PEAK="${BIRD_PEAK_RUN:-$ROOT/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49}"
if [[ -n "${BIRD_DATABASE_ROOT:-}" && -d "$PEAK/cases" ]]; then
  echo "== BIRD replay (raw) =="
  python3 -m app.evaluation.external_model --source bird \
    --database-root "$BIRD_DATABASE_ROOT" --replay-run "$PEAK" 2>&1 | grep "replay EX:" || true
  echo "== BIRD replay (PATCH autofix) =="
  python3 -m app.evaluation.external_model --source bird \
    --database-root "$BIRD_DATABASE_ROOT" --replay-run "$PEAK" --replay-patch-autofix 2>&1 \
    | grep "replay EX:" || true
else
  echo "skip BIRD replay: set BIRD_DATABASE_ROOT and ensure peak run at $PEAK" >&2
fi
TPCDS_PEAK="${TPCDS_PEAK_RUN:-$ROOT/reports/tpcds-derived/run_20261005T230855Z_43c9faa4c0f6e9844809faa8d8fd781d9150cf74}"
if [[ -d "$TPCDS_PEAK/cases" ]]; then
  echo "== TPC-DS replay =="
  python3 -m app.evaluation.external_model --source tpcds-derived --replay-run "$TPCDS_PEAK" 2>&1 \
    | grep "replay EX:" || true
fi
if [[ -d "$PEAK/cases" ]]; then
  echo "== peak EX=0 frozen semantic bar (≥3 findings) =="
  if python3 -m pytest tests/unit/test_bird_profile_inventory.py::test_peak_v15_ex0_saved_sql_surfaces_frozen_findings -q --tb=no; then
    echo "peak_ex0_frozen_findings=pass_min_3"
  else
    echo "peak_ex0_frozen_findings=fail" >&2
  fi
fi
echo "ops_runbook=docs/external_gold_p0_runbook.md"
echo "next_after_billing=./scripts/p0_post_billing_acceptance.sh"
echo "unattended_after_billing=./scripts/wait_for_billing_and_run_p0.sh"
echo "post_billing_docs=python3 -m app.evaluation.p0_measured_summary --acceptance-gate (via run_external_p0_full_eval_twice.sh)"
if grep -q "402" "$PREFLIGHT_LOG" 2>/dev/null; then
  echo "while_billing_blocked=./scripts/p0_post_billing_acceptance.sh --gates-only"
fi
