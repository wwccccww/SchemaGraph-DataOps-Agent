#!/usr/bin/env bash
# P1：无 LLM 的外部 Gold Oracle 门禁（发布前 / nightly 自托管）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
python3 -m app.evaluation.external_data check-external-release
python3 -m app.evaluation.external_data verify-tpcds
if [[ -n "${BIRD_DATABASE_ROOT:-}" ]]; then
  python3 -m app.evaluation.external_data verify-bird --database-root "$BIRD_DATABASE_ROOT"
else
  echo "skip verify-bird: set BIRD_DATABASE_ROOT to dev_databases path" >&2
fi
