#!/usr/bin/env bash
# P0/P1：打印外部 Gold 门禁与无 LLM replay 摘要（402 时运维用）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "== check-external-release =="
python3 -m app.evaluation.external_data check-external-release
echo "release_ready=$(python3 -c 'from app.evaluation.external_release import release_ready; print(release_ready())')"
echo "generic_prompt=$(python3 -c 'from app.agents.text_to_sql.prompt import GENERIC_PROMPT_VERSION; print(GENERIC_PROMPT_VERSION)')"
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
echo "next_after_billing=./scripts/run_external_p0_full_eval_twice.sh"
