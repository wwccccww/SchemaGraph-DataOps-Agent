# TPC-DS 派生压力测试

这是 TPC-DS-derived workload，不是官方 TPC-DS 成绩。官方工具和结果由 TPC 发布。

## 工具版本

- 仓库：https://github.com/gregrahn/tpcds-kit
- 提交：`5a3a81796992b725c2a8b216767e142609966752`
- 工具版本：TPC-DS v2.10.0
- 来源版本：`tpcds-v2.10.0+5a3a81796992b725c2a8b216767e142609966752`

本仓库不提交工具源码，也不提交生成数据。脚本把工具克隆到调用者指定的目录，给 `LINUX_CFLAGS` 加上 `-fcommon`，再编译 `dsdgen`。

## 数据

- 规模：SF=1
- 引擎：PostgreSQL 16
- 数据库名：`tpcds`
- 业务表：24 张。`dbgen_version` 可以随 schema 载入，但不进入查询。
- 派生加载不创建主键，使 SF=1 能放进内存受限的数据库进程。列名和类型仍来自该提交的 `tools/tpcds.sql`。

生成文件使用 `dsdgen -SCALE 1 -TERMINATE N`。不要把 `.dat` 文件提交到 Git。不要把这些数据载入电商库 `text2sql_db`。

## 查询

`cases.yaml` 有 30 条 PostgreSQL 查询。每条使用 5 到 12 张业务表，整套覆盖 CTE、子查询和聚合。自然语言问题由评测作者编写，不由待测模型根据 Gold SQL 反写。

`gold_attestation.json` 记录 Gold SQL 指纹；在 SF=1 快照上跑通 `verify-tpcds` 后会升级为 `gold_matched` 并写入 `result_digest`。正式全量模型评测要求 attestation 为 `gold_matched`。

```bash
构建工具需要 `git`、`make`、`gcc`、`bison` 和 `flex`。

```bash
uv run python -m app.evaluation.external_data build-tpcds-tools --kit-dir /tmp/tpcds-kit
uv run python -m app.evaluation.external_data generate-tpcds --kit-dir /tmp/tpcds-kit --data-dir /tmp/tpcds-sf1
uv run python -m app.evaluation.external_data load-tpcds --data-dir /tmp/tpcds-sf1 --schema /tmp/tpcds-kit/tools/tpcds.sql
```
uv run python -m app.evaluation.external_data verify-tpcds
```

`load-tpcds` 和 `verify-tpcds` 从 `TPCDS_POSTGRES_*` 或 `POSTGRES_*` 读取连接参数，密码不会写入报告。报告目录与自建评测分开，Measured 执行准确率保持为空。
