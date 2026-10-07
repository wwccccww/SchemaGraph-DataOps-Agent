#!/usr/bin/env bash
# P0：e5482a4 saved SQL + measured PATCH autofix 复分（**24→50/50**；非新 LLM）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_DIR="${1:-$(python3 -c 'from app.evaluation.replay_snapshot_paths import bird_e5482a4_measured_run_dir; print(bird_e5482a4_measured_run_dir())')}"
exec "$ROOT/scripts/replay_bird_baseline.sh" "$RUN_DIR" --replay-patch-autofix "${@:2}"
