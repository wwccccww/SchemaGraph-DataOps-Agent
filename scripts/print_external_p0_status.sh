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
BIRD_SQLITE="${BIRD_DATABASE_ROOT:-}/california_schools/california_schools.sqlite"
if [[ -z "${BIRD_DATABASE_ROOT:-}" ]]; then
  echo "bird_sqlite=unset"
elif [[ ! -d "${BIRD_DATABASE_ROOT}" ]]; then
  echo "bird_sqlite=invalid_root"
elif [[ -f "$BIRD_SQLITE" ]]; then
  echo "bird_sqlite=ready"
else
  echo "bird_sqlite=missing fetch=./scripts/fetch_bird_dev_databases.sh"
fi
PEAK="${BIRD_PEAK_RUN:-$(python3 -c 'from app.evaluation.replay_snapshot_paths import bird_peak_run_dir; print(bird_peak_run_dir())')}"
E5482A4="${BIRD_E5482A4_RUN:-$(python3 -c 'from app.evaluation.replay_snapshot_paths import bird_e5482a4_measured_run_dir; print(bird_e5482a4_measured_run_dir())')}"
TPCDS_PEAK="${TPCDS_PEAK_RUN:-$(python3 -c 'from app.evaluation.replay_snapshot_paths import tpcds_peak_run_dir; print(tpcds_peak_run_dir())')}"
if [[ "${EXTERNAL_P0_STATUS_SKIP_REPLAY:-0}" == "1" ]]; then
  echo "replay_skipped=external_p0_status_skip_replay"
else
  if [[ -n "${BIRD_DATABASE_ROOT:-}" && -f "$BIRD_SQLITE" && -d "$PEAK/cases" ]]; then
    echo "== BIRD replay (raw) =="
    python3 -m app.evaluation.external_model --source bird \
      --database-root "$BIRD_DATABASE_ROOT" --replay-run "$PEAK" 2>&1 | grep "replay EX:" || true
    echo "== BIRD replay (PATCH autofix) =="
    python3 -m app.evaluation.external_model --source bird \
      --database-root "$BIRD_DATABASE_ROOT" --replay-run "$PEAK" --replay-patch-autofix 2>&1 \
      | grep "replay EX:" || true
    if [[ -d "$E5482A4/cases" ]]; then
      echo "== BIRD e5482a4 measured replay (raw) =="
      python3 -m app.evaluation.external_model --source bird \
        --database-root "$BIRD_DATABASE_ROOT" --replay-run "$E5482A4" 2>&1 | grep "replay EX:" || true
      echo "== BIRD e5482a4 measured replay (PATCH autofix) =="
      python3 -m app.evaluation.external_model --source bird \
        --database-root "$BIRD_DATABASE_ROOT" --replay-run "$E5482A4" --replay-patch-autofix 2>&1 \
        | grep "replay EX:" || true
    fi
  else
    echo "skip BIRD replay: set BIRD_DATABASE_ROOT and ensure peak run at $PEAK" >&2
  fi
  if [[ -d "$TPCDS_PEAK/cases" ]]; then
    echo "== TPC-DS replay =="
    python3 -m app.evaluation.external_model --source tpcds-derived --replay-run "$TPCDS_PEAK" 2>&1 \
      | grep "replay EX:" || true
  fi
fi
if [[ -d "$PEAK/cases" ]]; then
  echo "== peak EX=0 frozen semantic bar (v12: 33/33 EX=0 with ≥1 finding) =="
  if python3 -m pytest tests/unit/test_bird_profile_inventory.py::test_v12_measured_ex0_frozen_finding_coverage_floor -q --tb=no; then
    echo "peak_ex0_frozen_findings=pass_min_33"
  else
    echo "peak_ex0_frozen_findings=fail" >&2
  fi
fi
echo "ops_runbook=docs/external_gold_p0_runbook.md"
echo "next_after_billing=./scripts/p0_post_billing_acceptance.sh"
echo "unattended_after_billing=./scripts/wait_for_billing_and_run_p0.sh"
echo "wait_log=${P0_WAIT_LOG:-/tmp/p0-wait-billing.log}"
echo "confirm_polls=${P0_WAIT_CONFIRM_POLLS:-2}"
P0_ACCEPTANCE_LOCK_FILE="${P0_ACCEPTANCE_LOCK_FILE:-/tmp/p0_post_billing_acceptance.lock}"
if [[ ! -e "$P0_ACCEPTANCE_LOCK_FILE" ]] || (
  exec 9<>"$P0_ACCEPTANCE_LOCK_FILE"
  flock -n 9
); then
  echo "p0_acceptance_lock=free path=${P0_ACCEPTANCE_LOCK_FILE}"
else
  echo "p0_acceptance_lock=held path=${P0_ACCEPTANCE_LOCK_FILE}"
fi
echo "post_billing_docs=python3 -m app.evaluation.p0_measured_summary --acceptance-gate (via run_external_p0_full_eval_twice.sh)"
if grep -q "402" "$PREFLIGHT_LOG" 2>/dev/null; then
  echo "while_billing_blocked=./scripts/p0_post_billing_acceptance.sh --gates-only"
fi
