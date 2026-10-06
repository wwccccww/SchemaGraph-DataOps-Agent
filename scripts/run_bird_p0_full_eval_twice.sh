#!/usr/bin/env bash
# P0：Billing 恢复后连续 2× 全量 BIRD 模型实测（generic v59 + self_healing，需 gold_matched）。
# 402 时在 generate_sql 失败；可先 ./scripts/print_external_p0_status.sh。
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
  echo "BIRD_DATABASE_ROOT is required (path to dev_databases)" >&2
  exit 1
fi
if [[ ! -d "${BIRD_DATABASE_ROOT}" ]]; then
  echo "BIRD_DATABASE_ROOT is not a directory: ${BIRD_DATABASE_ROOT} (see .env.example minidev/MINIDEV/dev_databases)" >&2
  exit 1
fi
python3 -m app.evaluation.external_data check-external-release
python3 -m app.evaluation.llm_preflight
echo "generic_prompt=$(python3 -c 'from app.agents.text_to_sql.prompt import GENERIC_PROMPT_VERSION; print(GENERIC_PROMPT_VERSION)')"
RUN_DIRS=()
for run in 1 2; do
  echo "== BIRD full eval run $run/2 =="
  python3 -m app.evaluation.external_model \
    --source bird \
    --database-root "$BIRD_DATABASE_ROOT" \
    --full \
    --variant self_healing \
    --max-repair-rounds 4
  latest="$(ls -td reports/bird/run_* 2>/dev/null | head -1)"
  RUN_DIRS+=("$latest")
  if [[ -n "${P0_MEASURED_MANIFEST:-}" ]]; then
    echo -e "bird\t$latest" >> "$P0_MEASURED_MANIFEST"
  fi
  echo "wrote $latest"
  python3 -m app.evaluation.external_model \
    --source bird \
    --database-root "$BIRD_DATABASE_ROOT" \
    --replay-run "$latest" 2>&1 | grep "replay EX:" || true
done
echo "P0 runs: ${RUN_DIRS[0]:-?} ; ${RUN_DIRS[1]:-?}"
echo "Compare summary.json measured.execution_accuracy and stability band."
