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
4. 可选：**`P0_BIRD_MIN_MATCHED=17`**（acceptance 每轮 BIRD EX 下限，与 `test_p0_external_measured_baseline` 同步；历史默认 7，v11 **13**，v12 **17**）。

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
| **`peak_ex0_frozen_findings=pass_min_14`** | `print_external_p0_status.sh`：v12 峰值 EX=0 inventory（`test_v12_measured_ex0_frozen_finding_coverage_floor`） |
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

分步：`./scripts/p1_release_gate.sh`（pytest 子集 + `./scripts/verify_external_gold.sh`）。

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

- **`p0_acceptance_gate=pass`**
- **`p0_measured_tpcds_run{1,2}=30/30`** 且 **`p0_stability_tpcds=stable`**
- **`p0_measured_bird_run{1,2}=≥17/50`**（默认 **`P0_BIRD_MIN_MATCHED=17`**）且 **`p0_stability_bird=stable`**

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
p0_measured_bird_run1=17/50 ex=0.34 dir=run_… …
p0_measured_bird_run2=17/50 ex=0.34 dir=run_… …
p0_stability_bird=stable
p0_acceptance_gate=pass
```

若 BIRD 稳定高于 **`P0_BIRD_MIN_MATCHED`**（默认 **17/50**），acceptance stdout 会打印 **`p0_baseline_followup=…`**；据此同步 `test_p0_external_measured_baseline.py`、峰值 run 目录与 **`P0_BIRD_MIN_MATCHED`**。

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
| `./scripts/replay_bird_patch_autofix.sh` | PATCH 复分（v12 峰值 **17→17/50**；**0002** 已在实测 EX=1；历史 v11 **13→14**、v15 **7→9**） |
| PATCH autofix 单测夹具 | `benchmarks/replay_snapshots/bird/run_20261006T001548Z_31113b6…/cases/{bird_0002,bird_0094}.json` | 与 v11 measured peak 分离；CI 不依赖 `reports/` |
| `./scripts/replay_tpcds_baseline.sh` | TPC-DS **30/30** |
| `./scripts/replay_bird_offline_ceiling.sh` | 离线 amend 口径（非发布 EX） |

## CI / nightly

- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)：quality + integration（无外部库）。
- [`.github/workflows/external-gold.yml`](../.github/workflows/external-gold.yml)：UTC 06:00 + push 子集 + `check-external-release`；**不**在托管 runner 上跑 `verify-tpcds` / `verify-bird`（无 Postgres/TPC-DS 库）。**`replay-gate`** 默认 **`fetch_bird_dev_databases.sh`** + vendored **`benchmarks/replay_snapshots/`** 跑 `test_p1_replay_gate`（BIRD **17/50** raw + **17→26** offline amend、TPC-DS **30/30**）；可选变量 **`BIRD_DATABASE_ROOT`** 指向已有 `dev_databases` 以跳过 fetch。smoke 需 **`EXTERNAL_GOLD_TESTS=1`**。托管 runner **80 例 Gold 执行**权威路径：本地/自托管 **`./scripts/verify_external_gold.sh`** 或 **`./scripts/p1_release_gate.sh`**。

## 后续（产品顺序第三步：方言 / 串库 / Join / Prompt）

P0 measured gate 与 P1 CI/nightly 已绿时，BIRD 提升依赖**新 2× LLM 全量**（非 replay alone）。**v12 峰值**（`65bcd64`，**17/50**）**33** 条 EX=0；**8** 条 `sql_error`（`test_v12_measured_sql_error_ex0_have_frozen_findings`，**0069/0119** 仍靠 Gold overlay amend）。**v11 归档**（`d502105`，13/50）仍用于 frozen-contract 回归夹具。建议顺序：

1. **Prompt + frozen 契约**：按 `badcase_diagnosis.md` / `test_bird_profile_inventory` 扩 v12 EX=0 保存 SQL 的 frozen 信号（当前下限 **`test_v12_measured_ex0_frozen_finding_coverage_floor` ≥14/33**；`print_external_p0_status.sh` → **`peak_ex0_frozen_findings=pass_min_14`**）。每题加 profile 规则 + `test_frozen_contract` 钉住 peak saved SQL（示例：**`bird_0005`** SAT>400 须在 **SATPerformance** CTE）。**不替代** measured EX。
2. **Join / 粒度**：`test_badcase_join_semantics.py`、AnswerContract 与 Gold 投影对齐（见 [benchmark.md §11](./benchmark.md) 自建 P1，与外部 BIRD 互补）。
3. **方言**：SQLite 执行层与 `test_badcase_sqlite_dialect.py`；禁止误判多语句/函数名。
4. **验收**：billing 后 `./scripts/run_external_p0_full_eval_twice.sh` → manifest → `--acceptance-gate` → `apply_p0_measured_benchmark.sh`；`P0_BIRD_MIN_MATCHED` 与 `test_p0_external_measured_baseline.py` 同步上调。
5. **自建评测（与外部轨道独立）**：电商 **132** 条 Oracle 护栏见 [benchmark.md §11](./benchmark.md)（`test_python_oracle_attestation_covers_every_case` **132/132**）；AnswerContract / 契约复核（P1/P2）与外部 BIRD frozen profile 互补，勿混报告。

## 离线 acceptance 逻辑校验（≠ 新 LLM 实测）

单测 `test_peak_documented_runs_pass_full_acceptance_gate_cli`：文档峰值 run 各 2× 喂 gate；**不能替代** billing 后新 2× 全量。
