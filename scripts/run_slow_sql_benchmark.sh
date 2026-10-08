#!/usr/bin/env bash
# 慢 SQL Benchmark：默认 50 条 full.yaml（需 DEEPSEEK_API_KEY + Postgres 沙箱）。
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
python3 "$ROOT/scripts/build_slow_sql_full_yaml.py"
exec uv run python -m app.evaluation.slow_sql_benchmark "$@"
