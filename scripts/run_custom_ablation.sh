#!/usr/bin/env bash
# §11 P2：自建 132 条全量消融（含 Recovery@3）；需 DeepSeek、Postgres 电商库（`python -m app.db.initialize`）与 SANDBOX_DB_PASSWORD。
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
  echo "POSTGRES_USER, POSTGRES_PASSWORD, and SANDBOX_DB_PASSWORD are required (see .env.example)" >&2
  exit 1
fi
python3 -m app.evaluation.external_data check-external-release
python3 -m app.evaluation.llm_preflight
uv run python -m app.evaluation.ablation --output "${CUSTOM_ABLATION_OUTPUT:-reports/custom}"
