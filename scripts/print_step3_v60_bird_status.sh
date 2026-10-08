#!/usr/bin/env bash
# Step-3：读取 reports/step3_v60_bird_manifest.tsv（run_bird_p0_full_eval_twice.sh 写入）并验收 v60 BIRD 2×。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MANIFEST="${STEP3_V60_MANIFEST:-$ROOT/reports/step3_v60_bird_manifest.tsv}"
MIN="${STEP3_BIRD_MIN_MATCHED:-24}"
if [[ ! -f "$MANIFEST" ]]; then
  echo "missing manifest: $MANIFEST (run ./scripts/run_bird_p0_full_eval_twice.sh with P0_MEASURED_MANIFEST set)" >&2
  exit 1
fi
python3 -m app.evaluation.p0_measured_summary \
  --manifest "$MANIFEST" \
  --step3-bird-gate \
  --step3-bird-min-matched "$MIN"
