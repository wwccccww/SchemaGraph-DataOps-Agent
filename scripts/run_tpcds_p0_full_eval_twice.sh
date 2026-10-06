#!/usr/bin/env bash
# P0：Billing 恢复后连续 2× 全量 TPC-DS 派生模型实测（需 gold_matched + 本机 tpcds 库）。
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
  echo "POSTGRES_USER and POSTGRES_PASSWORD are required (TPC-DS catalog + full eval)" >&2
  exit 1
fi
python3 -m app.evaluation.external_data check-external-release
python3 -m app.evaluation.llm_preflight
echo "generic_prompt=$(python3 -c 'from app.agents.text_to_sql.prompt import GENERIC_PROMPT_VERSION; print(GENERIC_PROMPT_VERSION)')"
RUN_DIRS=()
for run in 1 2; do
  echo "== TPC-DS derived full eval run $run/2 =="
  python3 -m app.evaluation.external_model \
    --source tpcds-derived \
    --full \
    --variant self_healing \
    --max-repair-rounds 4
  latest="$(ls -td reports/tpcds-derived/run_* 2>/dev/null | head -1)"
  RUN_DIRS+=("$latest")
  echo "wrote $latest"
  python3 -m app.evaluation.external_model \
    --source tpcds-derived \
    --replay-run "$latest" 2>&1 | grep "replay EX:" || true
done
echo "P0 TPC-DS runs: ${RUN_DIRS[0]:-?} ; ${RUN_DIRS[1]:-?}"
echo "Target band: 30/30 on both runs (LLM variance)."
