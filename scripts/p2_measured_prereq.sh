#!/usr/bin/env bash
# P2 实测前置：pgvector + 电商 schema/seed + BGE-M3 向量索引（无 LLM 消融本身）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
if [[ -z "${POSTGRES_USER:-}" || -z "${POSTGRES_PASSWORD:-}" || -z "${SANDBOX_DB_PASSWORD:-}" ]]; then
  echo "POSTGRES_USER, POSTGRES_PASSWORD, and SANDBOX_DB_PASSWORD are required" >&2
  exit 1
fi
export POSTGRES_DB="${POSTGRES_DB:-text2sql_db}"
echo "p2_prereq_postgres_db=${POSTGRES_DB}"
python3 -m app.evaluation.external_data check-external-release
uv run python -m app.db.initialize
uv run python -m app.db.seed
uv run python -m app.retrieval.index
echo "p2_measured_prereq=ok (then ./scripts/run_custom_ablation.sh + llm_preflight)"
