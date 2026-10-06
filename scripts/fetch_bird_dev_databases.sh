#!/usr/bin/env bash
# P0/P1：下载并解压 BIRD MINIDEV dev_databases（见 benchmarks/bird_complex/SOURCE.md）。
# 不提交 zip/SQLite；fetch 会校验 sha256。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DEST_ROOT="${BIRD_FETCH_ROOT:-/tmp/bird_dev}"
ZIP="${BIRD_FETCH_ZIP:-/tmp/minidev_0703.zip}"
DEV_DATABASES="$DEST_ROOT/minidev/MINIDEV/dev_databases"
if [[ -d "$DEV_DATABASES" && "${BIRD_FETCH_FORCE:-0}" != "1" ]]; then
  echo "bird_database_root=$DEV_DATABASES (reuse existing tree)"
  echo "export BIRD_DATABASE_ROOT=$DEV_DATABASES"
  if [[ "${BIRD_FETCH_VERIFY:-0}" == "1" ]]; then
    python3 -m app.evaluation.external_data verify-bird --database-root "$DEV_DATABASES"
  fi
  exit 0
fi
echo "fetching minidev zip to $ZIP"
python3 -m app.evaluation.external_data fetch-bird-databases --dest "$ZIP"
mkdir -p "$DEST_ROOT"
echo "unzipping to $DEST_ROOT"
unzip -oq "$ZIP" -d "$DEST_ROOT"
if [[ ! -d "$DEV_DATABASES" ]]; then
  echo "expected dev_databases at $DEV_DATABASES after unzip" >&2
  exit 1
fi
echo "bird_database_root=$DEV_DATABASES"
echo "export BIRD_DATABASE_ROOT=$DEV_DATABASES"
if [[ "${BIRD_FETCH_VERIFY:-0}" == "1" ]]; then
  python3 -m app.evaluation.external_data verify-bird --database-root "$DEV_DATABASES"
fi
