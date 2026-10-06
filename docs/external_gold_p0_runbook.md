# 外部 Gold P0/P1 运维手册

产品顺序：**Oracle（TPC-DS 30 + BIRD 50）→ 模型实测可信度（80×2 全量）→ P1 CI/nightly/verify**。细节与证据表见 [benchmark.md](./benchmark.md)。

## 环境

1. 复制 [`.env.example`](../.env.example) 为项目根 `.env`（勿提交）；tmux/CI 无 `.env` 时须 **export** 同名变量（各 gate 脚本会 `source .env` 若存在）。
2. 必填：**`BIRD_DATABASE_ROOT`**（`…/dev_databases`）、**`POSTGRES_*`**（TPC-DS catalog + 全量）、计费后 **`DEEPSEEK_API_KEY`**。
3. 可选：**`P0_BIRD_MIN_MATCHED=7`**（acceptance 每轮 BIRD EX 下限，与 `test_p0_external_measured_baseline` 同步）。

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

成功条件（脚本末尾）：

- **`p0_acceptance_gate=pass`**
- **`p0_measured_tpcds_run{1,2}=30/30`** 且 **`p0_stability_tpcds=stable`**
- **`p0_measured_bird_run{1,2}=≥7/50`**（默认）且 **`p0_stability_bird=stable`**

将 **`p0_measured_*` / `p0_stability_*`** 行写入 [benchmark.md](./benchmark.md)。若 BIRD 稳定高于 **7/50**，更新 `test_p0_external_measured_baseline.py` 与 **`P0_BIRD_MIN_MATCHED`**。

## 无 LLM 复分（回归，非新实测）

| 命令 | 用途 |
| --- | --- |
| `./scripts/replay_bird_baseline.sh` | BIRD 峰值 raw replay（当前 **7/50**） |
| `./scripts/replay_bird_patch_autofix.sh` | PATCH 上界（当前 **9/50**） |
| `./scripts/replay_tpcds_baseline.sh` | TPC-DS **30/30** |
| `./scripts/replay_bird_offline_ceiling.sh` | 离线 amend 口径（非发布 EX） |

## CI / nightly

- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)：quality + integration（无外部库）。
- [`.github/workflows/external-gold.yml`](../.github/workflows/external-gold.yml)：UTC 06:00 + push 子集；`replay-gate` 需变量 **`BIRD_DATABASE_ROOT`**；smoke 需 **`EXTERNAL_GOLD_TESTS=1`**。

## 离线 acceptance 逻辑校验（≠ 新 LLM 实测）

单测 `test_peak_documented_runs_pass_full_acceptance_gate_cli`：文档峰值 run 各 2× 喂 gate；**不能替代** billing 后新 2× 全量。
