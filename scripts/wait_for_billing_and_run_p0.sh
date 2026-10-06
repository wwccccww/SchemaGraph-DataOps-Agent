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
echo "ops_runbook=docs/external_gold_p0_runbook.md"
echo "polling_llm_preflight every ${INTERVAL}s until ready (402→exit 2 from preflight)"
while true; do
  if python3 -m app.evaluation.llm_preflight 2>/tmp/wait_for_billing_preflight.err; then
    echo "llm_preflight=ready"
    break
  fi
  if ! grep -q "402" /tmp/wait_for_billing_preflight.err 2>/dev/null; then
    cat /tmp/wait_for_billing_preflight.err >&2
    exit 2
  fi
  echo "llm_preflight=blocked_billing_402 sleep=${INTERVAL}s" >&2
  sleep "$INTERVAL"
done
if [[ -n "${P0_WAIT_STUB_ACCEPTANCE:-}" ]]; then
  echo "p0_post_billing=stub"
  exit 0
fi
exec "$ROOT/scripts/p0_post_billing_acceptance.sh"
