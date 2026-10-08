#!/usr/bin/env bash
# POST-PATCH  hygiene：对 P0 实测保存的 BIRD run 目录做 --replay-patch-autofix 复分（无 LLM）。
# 用于 billing 全量重跑前，验证 measured PATCH 对 vendored SQL 是否 50/50。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -z "${BIRD_DATABASE_ROOT:-}" ]]; then
  echo "BIRD_DATABASE_ROOT is required" >&2
  exit 1
fi
RUN_DIR="${1:?usage: $0 <reports/bird/run_...>}"
uv run python -m app.evaluation.external_model \
  --source bird \
  --database-root "$BIRD_DATABASE_ROOT" \
  --replay-run "$RUN_DIR" \
  --replay-patch-autofix
