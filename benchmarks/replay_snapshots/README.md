# External Gold replay snapshots (P0/P1)

Frozen **model prediction traces** for `--replay-run` / `--replay-patch-autofix` regression. These are **not** new LLM runs; they vendor peak measured baselines so CI and fresh clones work without local `reports/` (gitignored).

| Snapshot | Source commit / run | Replay bar |
|----------|---------------------|------------|
| `bird/run_20261007T093506Z_65bcd64…` | v12 measured peak (`65bcd64`, 2× stable **17/50**) | **17/50** raw; offline amend ceiling **17→26** |
| `bird/run_20261007T201201Z_e5482a4…` | BIRD measured (`e5482a4`, manifest **24/50×2**) | **24/50** raw replay; **24→50** `--replay-patch-autofix`; **50/50** live measured PATCH re-score (`test_e5482a4_saved_run_scores_fifty_with_measured_profile_patch`) |
| `bird/run_20261006T001548Z_31113b6…` | generic v15 peak (partial: `bird_0002` + `bird_0094` for PATCH autofix tests) | **7/50** raw; **7→9** PATCH autofix on full local `reports/` run |
| `tpcds-derived/run_20261005T230855Z_43c9faa…` | TPC-DS confirm | **30/30** |

Update only after a **new documented peak** full LLM run and passing `test_p0_external_measured_baseline` / runbook evidence. Measured **80×2** acceptance still requires billing-unblocked live eval + `reports/p0_measured_manifest.tsv`.
