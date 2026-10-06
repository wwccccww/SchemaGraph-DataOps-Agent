#!/usr/bin/env bash
# P0：80 例模型可信度 — 连续 2× TPC-DS + 2× BIRD（需 gold_matched；BIRD 需 BIRD_DATABASE_ROOT）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -z "${BIRD_DATABASE_ROOT:-}" ]]; then
  echo "BIRD_DATABASE_ROOT is required for the combined P0 80-case run" >&2
  exit 1
fi
if [[ -z "${POSTGRES_USER:-}" || -z "${POSTGRES_PASSWORD:-}" ]]; then
  echo "POSTGRES_USER and POSTGRES_PASSWORD are required (TPC-DS 2× full eval runs first)" >&2
  exit 1
fi
"$ROOT/scripts/run_tpcds_p0_full_eval_twice.sh"
"$ROOT/scripts/run_bird_p0_full_eval_twice.sh"
