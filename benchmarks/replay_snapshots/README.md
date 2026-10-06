# External Gold replay snapshots (P0/P1)

Frozen **model prediction traces** for `--replay-run` / `--replay-patch-autofix` regression. These are **not** new LLM runs; they vendor peak measured baselines so CI and fresh clones work without local `reports/` (gitignored).

| Snapshot | Source commit / run | Replay bar |
|----------|---------------------|------------|
| `bird/run_20261006T001548Z_31113b6…` | generic v15 peak | **7/50** raw; **7→9** PATCH autofix |
| `tpcds-derived/run_20261005T230855Z_43c9faa…` | TPC-DS confirm | **30/30** |

Update only after a **new documented peak** full LLM run and passing `test_p0_external_measured_baseline` / runbook evidence. Measured **80×2** acceptance still requires billing-unblocked live eval + `reports/p0_measured_manifest.tsv`.
