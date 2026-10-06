# 外部 Gold P0/P1 运维手册

产品顺序：**Oracle（TPC-DS 30 + BIRD 50）→ 模型实测可信度（80×2 全量）→ P1 CI/nightly/verify**。细节与证据表见 [benchmark.md](./benchmark.md)。

## 环境

1. 复制 [`.env.example`](../.env.example) 为项目根 `.env`（勿提交）；tmux/CI 无 `.env` 时须 **export** 同名变量（各 gate 脚本会 `source .env` 若存在）。
2. 必填：**`BIRD_DATABASE_ROOT`**（`…/dev_databases`）、**`POSTGRES_*`**（TPC-DS catalog + 全量；须能连上 **`TPCDS_POSTGRES_DB` 默认 `tpcds`**，否则 TPC-DS replay 单测 **skip**、verify 失败）、计费后 **`DEEPSEEK_API_KEY`**。
3. 可选：**`P0_BIRD_MIN_MATCHED=7`**（acceptance 每轮 BIRD EX 下限，与 `test_p0_external_measured_baseline` 同步）。

## 脚本 stdout 键（运维/自动化）

| 键 | 典型来源 |
| --- | --- |
| **`ops_runbook=docs/external_gold_p0_runbook.md`** | `print_external_p0_status.sh`；`p0_post_billing_acceptance.sh`（`--gates-only` 成功或全量结束） |
| **`next_after_billing=./scripts/p0_post_billing_acceptance.sh`** | 同上 |
| **`unattended_after_billing=./scripts/wait_for_billing_and_run_p0.sh`** | 同上（计费恢复后可选轮询 preflight） |
| **`while_billing_blocked=… --gates-only`** | `print_external_p0_status.sh`（402 时） |
| **`llm_preflight=ready`** | `python3 -m app.evaluation.llm_preflight` 成功 stdout |

402 时 **`llm_preflight`** stderr 亦指向本 runbook 与 **`--gates-only`**。

## 402 期间（无 LLM）

```bash
./scripts/print_external_p0_status.sh
# 或完整 P1 门禁（~20min）：
./scripts/p0_post_billing_acceptance.sh --gates-only
```

分步：`./scripts/p1_release_gate.sh`（pytest 子集 + `./scripts/verify_external_gold.sh`）。

**耗时（本地，含 replay 单测 + Oracle verify）**：约 **20–25 分钟**；402 窗口用 `./scripts/print_external_p0_status.sh` 可更快扫一遍 release + replay 摘要。

## 计费恢复后（P0 产品条）

```bash
python3 -m app.evaluation.llm_preflight          # 须 stdout: llm_preflight=ready（402→exit 2）
./scripts/p0_post_billing_acceptance.sh          # 禁止 --gates-only
```

无人值守（402 解除后自动跑全量 acceptance，轮询间隔默认 **300s**，可 `export P0_BILLING_POLL_SECONDS=60`）：

```bash
./scripts/wait_for_billing_and_run_p0.sh
```

非 402 的 preflight 失败会**立即 exit 2**（不无限轮询）。

**退出码**（`p0_post_billing_acceptance.sh` 全量）：**0** 成功；**1** 环境缺失；**2** `llm_preflight`（含 402）；**3** acceptance gate 未 pass（`set -e` 自 `run_external_p0_full_eval_twice.sh` 传播）。

成功条件（脚本末尾）：

- **`p0_acceptance_gate=pass`**
- **`p0_measured_tpcds_run{1,2}=30/30`** 且 **`p0_stability_tpcds=stable`**
- **`p0_measured_bird_run{1,2}=≥7/50`**（默认）且 **`p0_stability_bird=stable`**

将脚本 stdout 中 **`p0_measured_*` / `p0_stability_*`** 行（及 **`p0_acceptance_gate=pass`**）写入 [benchmark.md](./benchmark.md) 的 P0 实测段落；格式与 `python3 -m app.evaluation.p0_measured_summary --acceptance-gate` 一致，例如：

```text
p0_measured_tpcds_run1=30/30 ex=1.0 dir=run_… commit=… prompt=text-to-sql-generic-v59
p0_measured_tpcds_run2=30/30 ex=1.0 dir=run_… commit=… prompt=…
p0_stability_tpcds=stable
p0_measured_bird_run1=7/50 ex=0.14 dir=run_… …
p0_measured_bird_run2=7/50 ex=0.14 dir=run_… …
p0_stability_bird=stable
p0_acceptance_gate=pass
```

若 BIRD 稳定高于 **7/50**，同步更新 `test_p0_external_measured_baseline.py` 与 **`P0_BIRD_MIN_MATCHED`**。

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
| `./scripts/replay_bird_baseline.sh` | BIRD 峰值 raw replay（当前 **7/50**） |
| `./scripts/replay_bird_patch_autofix.sh` | PATCH 上界（当前 **9/50**） |
| `./scripts/replay_tpcds_baseline.sh` | TPC-DS **30/30** |
| `./scripts/replay_bird_offline_ceiling.sh` | 离线 amend 口径（非发布 EX） |

## CI / nightly

- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)：quality + integration（无外部库）。
- [`.github/workflows/external-gold.yml`](../.github/workflows/external-gold.yml)：UTC 06:00 + push 子集 + `check-external-release`；**不**在托管 runner 上跑 `verify-tpcds` / `verify-bird`（无库）。`replay-gate` 需变量 **`BIRD_DATABASE_ROOT`**；smoke 需 **`EXTERNAL_GOLD_TESTS=1`**。托管 runner **80 例 Gold 执行**权威路径：本地/自托管 **`./scripts/verify_external_gold.sh`** 或 **`./scripts/p1_release_gate.sh`**。

## 离线 acceptance 逻辑校验（≠ 新 LLM 实测）

单测 `test_peak_documented_runs_pass_full_acceptance_gate_cli`：文档峰值 run 各 2× 喂 gate；**不能替代** billing 后新 2× 全量。
