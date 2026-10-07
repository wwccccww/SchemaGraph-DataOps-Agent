# 外部 Gold P0/P1 运维手册

产品顺序：**Oracle（TPC-DS 30 + BIRD 50）→ 模型实测可信度（80×2 全量）→ P1 CI/nightly/verify**。细节与证据表见 [benchmark.md](./benchmark.md)。

## 环境

1. 复制 [`.env.example`](../.env.example) 为项目根 `.env`（勿提交）；tmux/CI 无 `.env` 时须 **export** 同名变量（各 gate 脚本会 `source .env` 若存在）。
2. **BIRD 库（Oracle / replay）**：本地无 MINIDEV 时一键获取（校验 zip sha256，见 [SOURCE.md](../benchmarks/bird_complex/SOURCE.md)）：

   ```bash
   eval "$(./scripts/fetch_bird_dev_databases.sh | grep '^export ')"
   # 强制重下：BIRD_FETCH_FORCE=1 ./scripts/fetch_bird_dev_databases.sh
   # 可选 Oracle：BIRD_FETCH_VERIFY=1 ./scripts/fetch_bird_dev_databases.sh
   ```

3. 必填：**`BIRD_DATABASE_ROOT`**（`…/dev_databases`）、**`POSTGRES_*`**（TPC-DS catalog + 全量；须能连上 **`TPCDS_POSTGRES_DB` 默认 `tpcds`**，否则 TPC-DS replay 单测 **skip**、verify 失败）、计费后 **`DEEPSEEK_API_KEY`**。
4. 可选：**`P0_BIRD_MIN_MATCHED=19`**（acceptance 每轮 BIRD EX 下限；历史默认 7，v11 **13**，v12 **17**；当前 **`bc29bb6` 80×2** 实测 **19×2 stable**）。vendored BIRD replay 峰值仍 **17/50**（PATCH **17→19**，**0061** + **0003**）。

**探测 TPC-DS catalog（门禁前）**：

```bash
python3 -c "from app.evaluation.external_data import tpcds_postgres_catalog_reachable as ok; raise SystemExit(0 if ok() else 1)"
```

失败时修正 **`POSTGRES_*`** / **`TPCDS_POSTGRES_*`**，确保能连上 **`tpcds`** 库（见 [`.env.example`](../.env.example) 注释）。

## 脚本 stdout 键（运维/自动化）

| 键 | 典型来源 |
| --- | --- |
| **`ops_runbook=docs/external_gold_p0_runbook.md`** | `print_external_p0_status.sh`；`p0_post_billing_acceptance.sh`（`--gates-only` 成功或全量结束） |
| **`next_after_billing=./scripts/p0_post_billing_acceptance.sh`** | 同上 |
| **`unattended_after_billing=./scripts/wait_for_billing_and_run_p0.sh`** | 同上（计费恢复后可选轮询 preflight） |
| **`while_billing_blocked=… --gates-only`** | `print_external_p0_status.sh`（402 时） |
| **`llm_preflight=ready`** | `python3 -m app.evaluation.llm_preflight` 成功 stdout |
| **`tpcds_postgres_catalog=ready\|unreachable`** | `print_external_p0_status.sh`；`p0_post_billing_acceptance.sh`；`wait_for_billing_and_run_p0.sh`（`tpcds_postgres_catalog_reachable`） |
| **`bird_sqlite=ready\|missing\|unset\|invalid_root`** | `print_external_p0_status.sh`（`california_schools/california_schools.sqlite` 探针；missing 含 **`fetch_bird_dev_databases.sh`**） |
| **`replay_skipped=external_p0_status_skip_replay`** | `print_external_p0_status.sh` 在 **`EXTERNAL_P0_STATUS_SKIP_REPLAY=1`** 时（单测 / 快速扫键；**运维 acceptance 勿设**，须看 replay EX 行） |
| **`p0_acceptance_lock=free\|held`** | `print_external_p0_status.sh`：全量 acceptance **`flock`** 锁是否被占用（**`P0_ACCEPTANCE_LOCK_FILE`**） |
| **`peak_ex0_frozen_findings=pass_min_33`** | `print_external_p0_status.sh`：v12 峰值 EX=0 inventory（`test_v12_measured_ex0_frozen_finding_coverage_floor` **33/33**） |
| **`p0_post_billing=blocked_resume_poll`** | `wait_for_billing_and_run_p0.sh`：全量 acceptance 仍 **402→exit 2** 时写 wait 日志并**继续轮询**（不退出 tmux） |
| **`p0_post_billing=skipped_already_running`** | wait 触发全量时 acceptance **exit 4**（`flock` 锁）；另一路（timer/手动）已在跑，wait **exit 0** |
| **`p0_acceptance=already_running`** | `p0_post_billing_acceptance.sh` 全量路径：**exit 4**（默认锁 **`/tmp/p0_post_billing_acceptance.lock`**，可 `P0_ACCEPTANCE_LOCK_FILE`） |

402 时 **`llm_preflight`** stderr 亦指向本 runbook 与 **`--gates-only`**。

## 402 期间（无 LLM）

```bash
./scripts/print_external_p0_status.sh
# 或完整 P1 门禁（~20min）：
./scripts/p0_post_billing_acceptance.sh --gates-only
```

分步：`./scripts/p1_release_gate.sh`（pytest 子集 + `./scripts/p2_custom_ablation_gates.sh` + `./scripts/verify_external_gold.sh`）。

**耗时（本地，含 replay 单测 + Oracle verify）**：约 **20–25 分钟**（`p1_release_gate` 内 `test_print_external_p0_status` 设 **`EXTERNAL_P0_STATUS_SKIP_REPLAY=1`** 跳过脚本内 replay，门禁约 **5–8 分钟**）；402 运维用 `./scripts/print_external_p0_status.sh` 默认**含** BIRD/TPC-DS replay 摘要（须 **`bird_sqlite=ready`** + Postgres catalog）。

## 计费恢复后（P0 产品条）

```bash
python3 -m app.evaluation.llm_preflight          # 须 stdout: llm_preflight=ready（402→exit 2）
./scripts/p0_post_billing_acceptance.sh          # 禁止 --gates-only
```

无人值守（402 解除后自动跑全量 acceptance，轮询间隔默认 **300s**，可 `export P0_BILLING_POLL_SECONDS=60`）：

```bash
./scripts/wait_for_billing_and_run_p0.sh
# 轮询日志默认追加到 /tmp/p0-wait-billing.log（export P0_WAIT_LOG=… 可改）
```

须已配置 **`BIRD_DATABASE_ROOT`**（须为存在的 **`dev_databases`** 目录）+ **`POSTGRES_*`**（与全量 acceptance 相同），否则**立即 exit 1**，避免空轮询或 verify 跑错路径。

非 402 的 preflight 失败会**立即 exit 2**（不无限轮询）。默认 **`P0_WAIT_CONFIRM_POLLS=2`**：连续两次 preflight 成功才启动全量（间隔 **`P0_WAIT_CONFIRM_SECONDS`** 默认 15s），避免偶发误报。wait 触发全量时会 **`export P0_FROM_BILLING_WAIT=1`**；acceptance 入口 preflight 对 402 默认再重试 **6** 次（间隔 **`P0_PREFLIGHT_WAIT_SLEEP`** 默认 20s），避免确认通过后立刻 402 导致全量未启动。若 acceptance 仍以 **exit 2** 结束，wait 记录 **`p0_post_billing=blocked_resume_poll`** 并回到 preflight 轮询（acceptance gate 失败 **exit 3** 则 wait **exit 3**，不无限重试）。

**退出码**（`p0_post_billing_acceptance.sh` 全量）：**0** 成功；**1** 环境缺失；**2** `llm_preflight`（含 402）；**3** acceptance gate 未 pass（`set -e` 自 `run_external_p0_full_eval_twice.sh` 传播）；**4** 已有 **2× 全量**在跑（**`p1_release_gate` 之后** `flock`，避免 gate 内单测再启 acceptance 时自锁；仍防 wait + timer 双启 80×2）。

成功条件（脚本末尾）：

- **`p0_acceptance_gate=pass`**（当前 autogen：`docs/benchmark.md` — **80×2** @ **`bc29bb6`**：TPC-DS **30/30×2** + BIRD **19/50×2 stable**）
- **`p0_measured_tpcds_run{1,2}=30/30`** 且 **`p0_stability_tpcds=stable`**
- **`p0_measured_bird_run{1,2}=≥19/50`**（默认 **`P0_BIRD_MIN_MATCHED=19`**）且 **`p0_stability_bird=stable`**

全量 acceptance 默认 **`P0_APPLY_BENCHMARK=1`**（可 `export P0_APPLY_BENCHMARK=0` 跳过）会在 gate pass 后调用 **`./scripts/apply_p0_measured_benchmark.sh`**，把 **`p0_measured_*` / `p0_stability_*`** 与 **`p0_acceptance_gate=pass`** 写入 [benchmark.md](./benchmark.md) 的 **`p0-measured-autogen`** 段落（单测 `test_p0_benchmark_docs.py`）。也可在已有 manifest 上单独执行：

```bash
./scripts/apply_p0_measured_benchmark.sh
# 或：python3 -m app.evaluation.p0_measured_summary --manifest reports/p0_measured_manifest.tsv --acceptance-gate --write-benchmark docs/benchmark.md
```

手动粘贴格式与 `python3 -m app.evaluation.p0_measured_summary --acceptance-gate` 一致，例如：

```text
p0_measured_tpcds_run1=30/30 ex=1.0 dir=run_… commit=… prompt=text-to-sql-generic-v59
p0_measured_tpcds_run2=30/30 ex=1.0 dir=run_… commit=… prompt=…
p0_stability_tpcds=stable
p0_measured_bird_run1=19/50 ex=0.38 dir=run_… …
p0_measured_bird_run2=19/50 ex=0.38 dir=run_… …
p0_stability_bird=stable
p0_acceptance_gate=pass
```

若 BIRD 稳定高于 **`P0_BIRD_MIN_MATCHED`**（默认 **19/50**），acceptance stdout 会打印 **`p0_baseline_followup=…`**；据此同步 vendored 峰值 run、**`P0_BIRD_MIN_MATCHED`** 与 `test_p0_external_measured_baseline.py`（replay 断言）。

**bird_0003 High-FRPM**：勿用 Free Meal/Enrollment 充当 FRPM 小数；**`high_frpm_frpm_pct` PATCH** 在 **validate**、**repair** 与 **实测 `score_prediction`**（非 replay）均会尝试；**`--replay-run`** 仍用 **`--replay-patch-autofix`**。另修正实测常见 **`ROUND(..., 2) AS PercentHighScorers`** 与 **Below/Average/Above** 分档 → Gold **High/Medium/Low**（**7645bbb** 两 run 保存 SQL offline 可 EX=1）。v12 vendored 峰值 + **881dd08** / **a78b594** 同理。

**bird_0032 Top FRPM (SOC=66)**：实测勿用 **Free Meal/Enrollment** 充当 eligibility；**`top_frpm_soc66` PATCH**（实测路径，非 Gold overlay）改 **FRPM Count/Enrollment** 与 `>=` 分档；**`--replay-amend top_frpm_soc66`** 仍为 Gold 上界估算。

**bird_0096 Weekly owners**：**`weekly_statement_demographics` PATCH** 修正 **avg_loan_amount**（total 均值非 per-loan）、**customers_with_loans**（`COUNT DISTINCT`）、去掉 trans 多余 type 过滤、**JOIN** `LoanAndTransactionData`。

**bird_0013 Top-3 SAT**：2× 方差常见 poverty 标签（`Very High`/`Moderate`）与 outer `ROUND`；workflow **`top3_sat_poverty` PATCH** 与 frozen 四档标签对齐。

**bird_0061 Hickman**：实测常见 Free Meal→FRPM 列混淆；workflow **`hickman_frpm` PATCH**（`profile_autofix` + `replay_amend`）与 frozen 分档/SAT 阈值 finding 一并收紧。

**tpcds_complex_023**：stock CTE 须 item 粒度 `GROUP BY` + `SUM(inv_quantity_on_hand)` 再 JOIN sold；否则 `quantity_sold` 重复计数。frozen + **`tpcds_023_stock` PATCH**；`--replay-patch-autofix` 对 **tpcds-derived** 与 BIRD 同路径。

**不稳定探针（勿单独抬 min）**：同 commit 连续 2× 若 matched 不一致（例如 **19/50** 与 **18/50**，差分常为 **bird_0013** poverty 标签/`ROUND` 或 **bird_0061** FRPM 列），则 **`p0_stability_bird=unstable`**；优先 **`top3_sat_poverty` / `hickman_frpm` PATCH** 与 frozen 后再跑 2×。

### Measured manifest（2×2 全量）

`run_external_p0_full_eval_twice.sh` 会清空并写入 **`reports/p0_measured_manifest.tsv`**（stdout 键 **`p0_measured_manifest=`**）。每行 **`SOURCE<TAB>绝对或相对 run 目录`**：

```text
tpcds-derived	reports/tpcds-derived/run_…
tpcds-derived	reports/tpcds-derived/run_…
bird	reports/bird/run_…
bird	reports/bird/run_…
```

验收：`python3 -m app.evaluation.p0_measured_summary --manifest reports/p0_measured_manifest.tsv --acceptance-gate`

## 无 LLM 复分（回归，非新实测）

| 命令 | 用途 |
| --- | --- |
| `./scripts/replay_bird_baseline.sh` | BIRD 峰值 raw replay（v12 measured **17/50**） |
| `./scripts/replay_bird_patch_autofix.sh` | PATCH 复分（v12 峰值 **17→19/50**，**0061** + **0003**；**881dd08** 实测 run **19→20**；**0002** 已在实测 EX=1；历史 v11 **13→14**、v15 **7→9**） |
| PATCH autofix 单测夹具 | `benchmarks/replay_snapshots/bird/run_20261006T001548Z_31113b6…/cases/{bird_0002,bird_0094}.json` | 与 v11 measured peak 分离；CI 不依赖 `reports/` |
| `./scripts/replay_tpcds_baseline.sh` | TPC-DS **30/30** |
| `./scripts/replay_bird_offline_ceiling.sh` | 离线 amend 口径（非发布 EX） |

## CI / nightly

- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)：quality + integration（无外部库）。
- 本地发布门禁：**`./scripts/p1_release_gate.sh`** = pytest 子集 + **`./scripts/p2_custom_ablation_gates.sh`**（§11 无 LLM）+ **`verify_external_gold.sh`**（80/80 Oracle）。
- [`.github/workflows/external-gold.yml`](../.github/workflows/external-gold.yml)：UTC 06:00 + push 子集 + `check-external-release`；**不**在托管 runner 上跑 `verify-tpcds` / `verify-bird`（无 Postgres/TPC-DS 库）。**`replay-gate`** 默认 **`fetch_bird_dev_databases.sh`**（Drive 超限时自动回退官方 Alibaba OSS `minidev.zip`，见 `benchmarks/bird_complex/SOURCE.md`）+ vendored **`benchmarks/replay_snapshots/`** 跑 `test_p1_replay_gate`（BIRD **17/50** raw + **17→26** offline amend、TPC-DS **30/30** + **`--replay-patch-autofix` 30→30**）；可选变量 **`BIRD_DATABASE_ROOT`** 指向已有 `dev_databases` 以跳过 fetch。smoke 需 **`EXTERNAL_GOLD_TESTS=1`**。托管 runner **80 例 Gold 执行**权威路径：本地/自托管 **`./scripts/verify_external_gold.sh`** 或 **`./scripts/p1_release_gate.sh`**。本分支 **PR #2** @ **`1a7258d`**：**fingerprints + replay-gate**（含 P2 schema 单测）；**`p0_acceptance_gate=pass`**（**80×2** @ **`bc29bb6`**）；**UTC 06:00** nightly 与 push 同 workflow。

## 后续（产品顺序第三步：方言 / 串库 / Join / Prompt）

P0 measured gate 与 P1 CI/nightly 已绿时，BIRD 提升依赖**新 2× LLM 全量**（非 replay alone）。**v12 峰值**（`65bcd64`，**17/50**）**33** 条 EX=0；**8** 条 `sql_error`（`test_v12_measured_sql_error_ex0_have_frozen_findings`，**0069/0119** 仍靠 Gold overlay amend）。**v11 归档**（`d502105`，13/50）仍用于 frozen-contract 回归夹具。建议顺序：

1. **Prompt + frozen 契约**：v12 峰值 **33/33** EX=0 保存 SQL 均有 frozen 信号（**`test_v12_measured_ex0_frozen_finding_coverage_floor`**；`print_external_p0_status.sh` → **`peak_ex0_frozen_findings=pass_min_33`**）。**`test_v12_peak_multattempt_cases_include_repair_trace_symptoms`** 钉住 attempts>1 的 repair_trace 症状链（对齐 benchmark §11.5 P2 外部报告口径）；`score_prediction` 与 replay **`inspection_from_replay`** 对多轮空 trace fail-fast。**0069/0119** 仍为 sql_error，靠 Gold overlay amend 抬离线口径。**不替代** measured EX。
2. **Join / 粒度**：`test_badcase_join_semantics.py`、AnswerContract 与 Gold 投影对齐（见 [benchmark.md §11](./benchmark.md) 自建 P1，与外部 BIRD 互补）；v12 峰值 **5** 条 `join_semantics` EX=0 见 **`test_v12_measured_join_semantics_ex0_have_frozen_findings`**（**0066/0078/0092/0097/0111**）；Gold 须 **`test_v12_join_semantics_cases_gold_sql_passes_frozen`**；**0066** CountyStats cohort / **0078** poverty COUNT vs SUM 等 frozen 已收紧（`d4e91a2+`）。
3. **方言 / 串库**：SQLite 执行层与 `test_badcase_sqlite_dialect.py`；禁止误判多语句/函数名；v12 峰值 **`test_v12_peak_zero_cross_database_leaks`**（`cross_database_leaks=0`）。**response_shape** **0055/0113**：**`test_v12_response_shape_cases_gold_sql_passes_frozen`** + **`test_v12_measured_response_shape_ex0_have_frozen_findings`**。
4. **验收**：billing 后 `./scripts/run_external_p0_full_eval_twice.sh` → manifest → `--acceptance-gate` → `apply_p0_measured_benchmark.sh`（当前 **`p0_acceptance_gate=pass`** 见 `benchmark.md` autogen；BIRD 下限 **`P0_BIRD_MIN_MATCHED=19`**，vendored replay 仍 **17/50**）。
5. **自建评测（与外部轨道独立）**：电商 **132** 条 Oracle 护栏见 [benchmark.md §11](./benchmark.md)（`test_python_oracle_attestation_covers_every_case` **132/132**）；无 LLM 门禁 **`./scripts/p2_custom_ablation_gates.sh`**；全量 Recovery@3 实测需本机电商 Postgres + **`./scripts/run_custom_ablation.sh`**。

## 离线 acceptance 逻辑校验（≠ 新 LLM 实测）

单测 `test_peak_documented_runs_pass_full_acceptance_gate_cli`：文档峰值 run 各 2× 喂 gate；**不能替代** billing 后新 2× 全量。
