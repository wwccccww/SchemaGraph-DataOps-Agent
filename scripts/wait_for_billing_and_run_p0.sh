#!/usr/bin/env bash
# 402 解除后：轮询 llm_preflight，就绪则执行 P0 全量 acceptance（同 p0_post_billing_acceptance.sh 全量路径）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
if [[ -z "${BIRD_DATABASE_ROOT:-}" ]]; then
  echo "BIRD_DATABASE_ROOT is required before unattended P0 acceptance" >&2
  exit 1
fi
if [[ ! -d "${BIRD_DATABASE_ROOT}" ]]; then
  echo "BIRD_DATABASE_ROOT is not a directory: ${BIRD_DATABASE_ROOT} (see .env.example minidev/MINIDEV/dev_databases)" >&2
  exit 1
fi
if [[ -z "${POSTGRES_USER:-}" || -z "${POSTGRES_PASSWORD:-}" ]]; then
  echo "POSTGRES_USER and POSTGRES_PASSWORD are required (TPC-DS 2× full eval after billing)" >&2
  exit 1
fi
if python3 -c "from app.evaluation.external_data import tpcds_postgres_catalog_reachable; raise SystemExit(0 if tpcds_postgres_catalog_reachable() else 1)"; then
  echo "tpcds_postgres_catalog=ready"
else
  echo "tpcds_postgres_catalog=unreachable"
fi
INTERVAL="${P0_BILLING_POLL_SECONDS:-300}"
CONFIRM_POLLS="${P0_WAIT_CONFIRM_POLLS:-2}"
CONFIRM_SLEEP="${P0_WAIT_CONFIRM_SECONDS:-15}"
WAIT_LOG="${P0_WAIT_LOG:-/tmp/p0-wait-billing.log}"
_p0_wait_log() {
  # shellcheck disable=SC2129
  printf '%s\n' "$@" | tee -a "$WAIT_LOG"
}
_p0_wait_log "ops_runbook=docs/external_gold_p0_runbook.md"
echo "ops_runbook=docs/external_gold_p0_runbook.md"
echo "wait_log=${WAIT_LOG}"
_p0_wait_log "wait_log=${WAIT_LOG}"
_p0_wait_log "polling_llm_preflight every ${INTERVAL}s until ready (402→exit 2 from preflight)"
_p0_wait_log "confirm_polls=${CONFIRM_POLLS} confirm_sleep_seconds=${CONFIRM_SLEEP}"
echo "polling_llm_preflight every ${INTERVAL}s until ready (402→exit 2 from preflight)"
echo "confirm_polls=${CONFIRM_POLLS}"
while true; do
  ready_streak=0
  while true; do
    if python3 -m app.evaluation.llm_preflight 2>/tmp/wait_for_billing_preflight.err; then
      ready_streak=$((ready_streak + 1))
      _p0_wait_log "llm_preflight=ready_streak=${ready_streak}/${CONFIRM_POLLS}"
      echo "llm_preflight=ready_streak=${ready_streak}/${CONFIRM_POLLS}"
      if [[ "$ready_streak" -ge "$CONFIRM_POLLS" ]]; then
        _p0_wait_log "llm_preflight=ready"
        echo "llm_preflight=ready"
        break
      fi
      sleep "$CONFIRM_SLEEP"
      continue
    fi
    ready_streak=0
    if ! grep -q "402" /tmp/wait_for_billing_preflight.err 2>/dev/null; then
      cat /tmp/wait_for_billing_preflight.err >&2
      _p0_wait_log "llm_preflight=failed_non_402"
      exit 2
    fi
    _p0_wait_log "llm_preflight=blocked_billing_402 sleep=${INTERVAL}s"
    echo "llm_preflight=blocked_billing_402 sleep=${INTERVAL}s" >&2
    sleep "$INTERVAL"
  done
  if [[ -n "${P0_WAIT_STUB_ACCEPTANCE:-}" ]]; then
    echo "p0_post_billing=stub"
    exit 0
  fi
  export P0_FROM_BILLING_WAIT=1
  if "$ROOT/scripts/p0_post_billing_acceptance.sh"; then
    _p0_wait_log "p0_post_billing=success"
    exit 0
  fi
  rc=$?
  if [[ "$rc" -eq 2 ]]; then
    _p0_wait_log "p0_post_billing=blocked_resume_poll interval=${INTERVAL}s"
    echo "p0_post_billing=blocked_resume_poll interval=${INTERVAL}s" >&2
    continue
  fi
  if [[ "$rc" -eq 4 ]]; then
    _p0_wait_log "p0_post_billing=skipped_already_running"
    echo "p0_post_billing=skipped_already_running (peer holds P0_ACCEPTANCE_LOCK_FILE)" >&2
    exit 0
  fi
  exit "$rc"
done
