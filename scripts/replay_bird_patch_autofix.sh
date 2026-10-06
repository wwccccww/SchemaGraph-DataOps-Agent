#!/usr/bin/env bash
# P0/P1：无 LLM 复分 BIRD 峰值 SQL + measured-path PATCH autofix（非 Gold overlay，非 LLM 实测）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_DIR="${1:-/workspace/reports/bird/run_20261006T001548Z_31113b64a03d1e965d346333edef538d98aedd49}"
if [[ -z "${BIRD_DATABASE_ROOT:-}" ]]; then
  echo "BIRD_DATABASE_ROOT is required" >&2
  exit 1
fi
exec "$ROOT/scripts/replay_bird_baseline.sh" "$RUN_DIR" --replay-patch-autofix "${@:2}"
