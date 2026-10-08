#!/usr/bin/env bash
# 全量自建消融完成后，将 reports/custom/run_*/summary.json 摘要写入 docs/benchmark.md p2-measured-autogen。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_DIR="${P2_CUSTOM_RUN_DIR:-}"
BENCHMARK="${P2_BENCHMARK_MD:-$ROOT/docs/benchmark.md}"
ARGS=(--acceptance-gate --write-benchmark "$BENCHMARK")
if [[ -n "$RUN_DIR" ]]; then
  ARGS=(--run-dir "$RUN_DIR" "${ARGS[@]}")
else
  ARGS=(--latest "${ARGS[@]}")
fi
python3 -m app.evaluation.p2_custom_ablation_summary "${ARGS[@]}"
