#!/usr/bin/env bash
# P1：无 LLM 离线口径上界（全部 --replay-amend profile，非模型实测 EX）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
RUN_DIR="${1:-$(python3 -c 'from app.evaluation.replay_snapshot_paths import bird_peak_run_dir; print(bird_peak_run_dir())')}"
if [[ -z "${BIRD_DATABASE_ROOT:-}" ]]; then
  echo "BIRD_DATABASE_ROOT is required" >&2
  exit 1
fi
exec "$ROOT/scripts/replay_bird_baseline.sh" "$RUN_DIR" \
  --replay-amend coe_charter \
  --replay-amend magnet_sat \
  --replay-amend top_reading \
  --replay-amend top_frpm_soc66 \
  --replay-amend enrollment500 \
  --replay-amend la_meal_stats \
  --replay-amend directly_funded_stanislaus \
  --replay-amend state_special_soc3 \
  --replay-amend la_k9_frpm_sat \
  --replay-amend schools_admin_doc_soc \
  --replay-amend financial_salary_gap \
  --replay-amend financial_1993_poplatek
