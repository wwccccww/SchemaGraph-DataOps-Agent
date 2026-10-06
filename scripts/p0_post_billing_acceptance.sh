#!/usr/bin/env bash
# P0 产品条：DeepSeek 计费恢复后，按顺序完成 Oracle 门禁 + 2× 全量 LLM（80 例可信度）。
# 402 时第一步 llm_preflight 即 exit 2；402 期间请用 ./scripts/print_external_p0_status.sh。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -z "${BIRD_DATABASE_ROOT:-}" ]]; then
  echo "BIRD_DATABASE_ROOT is required (path to dev_databases)" >&2
  exit 1
fi
echo "generic_prompt=$(python3 -c 'from app.agents.text_to_sql.prompt import GENERIC_PROMPT_VERSION; print(GENERIC_PROMPT_VERSION)')"
python3 -m app.evaluation.llm_preflight
"$ROOT/scripts/p1_release_gate.sh"
"$ROOT/scripts/run_external_p0_full_eval_twice.sh"
echo "P0 acceptance: record both TPC-DS and BIRD runs' execution_accuracy in docs/benchmark.md and update test_p0_external_measured_baseline if stable."
