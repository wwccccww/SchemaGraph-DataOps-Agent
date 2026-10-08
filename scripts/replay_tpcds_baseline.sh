#!/usr/bin/env bash
# P1：无 LLM 复分 TPC-DS 派生模型基线（需本地 reports 快照 + Postgres 已 verify）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
RUN_DIR="${1:-$(python3 -c 'from app.evaluation.replay_snapshot_paths import tpcds_peak_run_dir; print(tpcds_peak_run_dir())')}"
if [[ ! -d "$RUN_DIR/cases" ]]; then
  echo "missing run dir: $RUN_DIR" >&2
  exit 1
fi
python3 -m app.evaluation.external_model \
  --source tpcds-derived \
  --replay-run "$RUN_DIR" \
  "${@:2}"
