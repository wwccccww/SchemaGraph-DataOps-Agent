#!/usr/bin/env bash
# 在 p0_acceptance_gate=pass 后，将 reports/p0_measured_manifest.tsv 摘要写入 docs/benchmark.md 自动段落。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MANIFEST="${P0_MEASURED_MANIFEST:-$ROOT/reports/p0_measured_manifest.tsv}"
BENCHMARK="${P0_BENCHMARK_MD:-$ROOT/docs/benchmark.md}"
BIRD_MIN="${P0_BIRD_MIN_MATCHED:-17}"
if [[ ! -f "$MANIFEST" ]]; then
  echo "missing manifest: $MANIFEST (run ./scripts/run_external_p0_full_eval_twice.sh first)" >&2
  exit 1
fi
python3 -m app.evaluation.p0_measured_summary \
  --manifest "$MANIFEST" \
  --acceptance-gate \
  --bird-min-matched "$BIRD_MIN" \
  --write-benchmark "$BENCHMARK"
