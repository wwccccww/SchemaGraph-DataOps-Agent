#!/usr/bin/env bash
# P1：无 LLM 复分 TPC-DS 派生模型基线（需本地 reports 快照 + Postgres 已 verify）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_DIR="${1:-/workspace/reports/tpcds-derived/run_20261005T230855Z_43c9faa4c0f6e9844809faa8d8fd781d9150cf74}"
if [[ ! -d "$RUN_DIR/cases" ]]; then
  echo "missing run dir: $RUN_DIR" >&2
  exit 1
fi
python3 -m app.evaluation.external_model \
  --source tpcds-derived \
  --replay-run "$RUN_DIR" \
  "${@:2}"
