#!/usr/bin/env bash
# P0/P1：无 LLM 复分 BIRD 峰值 SQL + measured-path PATCH autofix（非 Gold overlay，非 LLM 实测）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
RUN_DIR="${1:-$(python3 -c 'from app.evaluation.replay_snapshot_paths import bird_peak_run_dir; print(bird_peak_run_dir())')}"
if [[ -z "${BIRD_DATABASE_ROOT:-}" ]]; then
  echo "BIRD_DATABASE_ROOT is required" >&2
  exit 1
fi
exec "$ROOT/scripts/replay_bird_baseline.sh" "$RUN_DIR" --replay-patch-autofix "${@:2}"
