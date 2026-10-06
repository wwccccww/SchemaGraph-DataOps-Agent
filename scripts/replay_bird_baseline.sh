#!/usr/bin/env bash
# P1：无 LLM 复分 BIRD 模型基线（需本地 reports 快照 + BIRD 库）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
RUN_DIR="${1:-/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49}"
if [[ -z "${BIRD_DATABASE_ROOT:-}" ]]; then
  echo "BIRD_DATABASE_ROOT is required" >&2
  exit 1
fi
if [[ ! -d "$RUN_DIR/cases" ]]; then
  echo "missing run dir: $RUN_DIR" >&2
  exit 1
fi
python3 -m app.evaluation.external_model \
  --source bird \
  --database-root "$BIRD_DATABASE_ROOT" \
  --replay-run "$RUN_DIR" \
  "${@:2}"
