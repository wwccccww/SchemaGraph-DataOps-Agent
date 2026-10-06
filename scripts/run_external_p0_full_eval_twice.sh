#!/usr/bin/env bash
# P0：80 例模型可信度 — 连续 2× TPC-DS + 2× BIRD（需 gold_matched；BIRD 需 BIRD_DATABASE_ROOT）。
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
  echo "BIRD_DATABASE_ROOT is required for the combined P0 80-case run" >&2
  exit 1
fi
if [[ -z "${POSTGRES_USER:-}" || -z "${POSTGRES_PASSWORD:-}" ]]; then
  echo "POSTGRES_USER and POSTGRES_PASSWORD are required (TPC-DS 2× full eval runs first)" >&2
  exit 1
fi
MANIFEST="$ROOT/reports/p0_measured_manifest.tsv"
mkdir -p "$(dirname "$MANIFEST")"
: > "$MANIFEST"
export P0_MEASURED_MANIFEST="$MANIFEST"
"$ROOT/scripts/run_tpcds_p0_full_eval_twice.sh"
"$ROOT/scripts/run_bird_p0_full_eval_twice.sh"
echo "== P0 measured summary (paste into docs/benchmark.md) =="
BIRD_MIN="${P0_BIRD_MIN_MATCHED:-7}"
python3 -m app.evaluation.p0_measured_summary \
  --manifest "$MANIFEST" \
  --acceptance-gate \
  --bird-min-matched "$BIRD_MIN"
