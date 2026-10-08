# BIRD Complex

本目录是公开 Benchmark 兼容性轨道，不是私有未见数据上的泛化成绩。

## 问题文件

- 数据集：Hugging Face `birdsql/bird_sql_dev_20251106`
- 提交：`3c11fb193e5439b338e23677fa0aae11e8b85db9`
- 文件：`data/dev_20251106-00000-of-00001.json`
- 本地副本：`dev_20251106.json`
- sha256：`ffd8018378ddb1a8794753e0a31cfc81862ff7318a5184c22f3dc4ce03a03feb`
- 许可证：CC BY-SA 4.0
- 来源版本：`bird-sql-dev-20251106@3c11fb193e5439b338e23677fa0aae11e8b85db9`

`dev_20251106.json` 保留原始 `question_id`、`db_id`、`question`、`evidence` 和 `SQL`。用例只取 `db_id`、问题和 Gold SQL。`evidence` 不是 `BenchmarkCase` 字段，也不能进入问数 Prompt。

冻结用例会把 Gold SQL 里的 SQLite `strftime(..., 'now')` / `date('now')` 替换成锚点日 `2026-10-01`，来源版本后缀 `+anchor20261001`。问句文本仍与公开集一致。

## 数据库

- 文件：`minidev_0703.zip`
- Google Drive id：`13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG`
- sha256：`aeb211c0e39010bbdae3838bb5e8bd27dc446ed77495b1709f85ccc9bf67f2be`
- CI 镜像（官方 Alibaba OSS，同 `minidev/MINIDEV/dev_databases` 树）：`https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip`
- 镜像 sha256：`cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f`（`fetch-bird-databases` 在 Drive 失败时自动回退）

压缩包和 SQLite 文件不进入 Git。`database_checksums.json` 记录入选用例实际打开的数据库摘要。执行前要核对摘要。

## 筛选

从 `difficulty = challenging` 的题目里，按 `question_id` 升序，保留可由受限 SQLite Adapter 执行的前 50 条。适配器使用只读 URI、Authorizer、Progress Handler、内存限制和隔离子进程。静态检查或执行失败的 `question_id` 记在 `exclusions.json`。

`gold_attestation.json` 记录 Gold SQL 指纹，并标记依赖 `strftime(..., 'now')` 的墙钟敏感用例。`verify-bird` 成功后会写入 `gold_matched` 与 `result_digest`。正式全量模型评测要求 attestation 为 `gold_matched`。

入选结果只说明这些公开题目能在该适配器上运行。它不并入 PostgreSQL 慢 SQL 指标，也不和自建电商指标混合。

重新获取：

```bash
eval "$(./scripts/fetch_bird_dev_databases.sh | grep '^export ')"
uv run python -m app.evaluation.external_data verify-bird --database-root "$BIRD_DATABASE_ROOT"
uv run python -m app.evaluation.external_data select-bird --database-root "$BIRD_DATABASE_ROOT"
```

等价分步：

```bash
uv run python -m app.evaluation.external_data fetch-bird-questions --dest benchmarks/bird_complex/dev_20251106.json
uv run python -m app.evaluation.external_data fetch-bird-databases --dest /tmp/minidev_0703.zip
unzip -q /tmp/minidev_0703.zip -d /tmp/bird_dev
uv run python -m app.evaluation.external_data verify-bird --database-root /tmp/bird_dev/minidev/MINIDEV/dev_databases
uv run python -m app.evaluation.external_data select-bird --database-root /tmp/bird_dev/minidev/MINIDEV/dev_databases
```
