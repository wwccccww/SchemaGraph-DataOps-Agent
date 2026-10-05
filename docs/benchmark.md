# Benchmark 与验收规范

## 1. 原则

评测必须可复现、可解释并避免数据泄漏：

- 自建、TPC-DS 派生和 BIRD 三套结果独立报告；
- Baseline 与 Enhanced 使用相同数据、模型和采样参数；
- Gold SQL 只存在于评测侧，不能进入 Agent Prompt 或检索库；
- Gold SQL 的可执行性不等于语义正确性；自建 Gold 必须有独立于主 Gold SQL 的结果校验；
- Target 与 Measured 指标严格区分；
- 失败、超时和熔断必须进入分母，不能只统计成功请求；
- 数据版本、模型版本、Prompt 版本和代码提交必须写入报告。

## 2. 评测轨道

### 2.1 自建电商 Text-to-SQL

共 132 条：

| 难度 | 数量 | 范围 |
| --- | ---: | --- |
| Basic | 50 | 单表或 2～3 表过滤、排序、基础聚合 |
| Medium | 50 | 4～6 表、多条件分组、HAVING、子查询 |
| Complex | 32 | 7～12 表、长链 Join、无语义 Junction Table |

该轨道是项目主指标来源，用于计算：

- Execution Accuracy；
- Junction Table Recall；
- Schema Context Token；
- Text-to-SQL Pass@K 与 Recovery@3；
- 熔断次数及平均收敛轮数。

### 2.2 TPC-DS 派生压力测试

默认使用 TPC-DS 24 表 Schema、PostgreSQL 16 和 `SF=1`，从规定查询模板中选择 30 条：

- 涉及至少 5 张表；
- 单条查询相关表不超过 12；
- 覆盖复杂 Join、CTE、子查询和聚合；
- PostgreSQL 方言适配经过人工审计；
- 自然语言问题由评测设计者编写，不由待测模型根据 Gold SQL 反向生成。

该轨道属于 **TPC-DS-derived workload**，不能宣称为官方 TPC-DS 成绩。生成数据不提交到 Git，只提交固定版本的获取和生成脚本。

### 2.3 BIRD Complex

默认从具有公开 Gold SQL 的固定开发集筛选 50 条复杂问题：

- 保留原始 `db_id`、自然语言问题和 Gold SQL；
- 固定数据集版本或 Commit；
- 记录许可证和来源；
- 首期只选择可由受限 SQLite Adapter 执行的原生 SQLite 用例；
- SQLite Adapter 使用只读 URI、Authorizer、Progress Handler 和隔离子进程；
- 只用于 Text-to-SQL EX，不并入 PostgreSQL 慢 SQL 指标。

公开数据可能已出现在模型训练语料中，因此 BIRD 结果只能表示公开 Benchmark 兼容性，不能替代私有未见数据泛化评测。

### 2.4 慢 SQL

50 条独立用例，不包含在自建 132 条中。每条用例至少记录：

- 原 SQL；
- 数据库快照版本；
- 已知反模式；
- 索引前置条件；
- 原始执行结果；
- 允许的改写类别；
- `primary_metric`，枚举为 `planner_cost`、`execution_time` 或 `shared_buffer_access`，默认 `planner_cost`；
- `min_primary_drop` 与次要指标最大允许退化比例；
- 超时和资源预算。

因此默认规模是：

```text
Text-to-SQL：132 + 30 + 50 = 212 条
慢 SQL：50 条独立用例
```

### 2.5 外部 Gold 指纹与 attestation

TPC-DS 派生与 BIRD 在 Git 中各有一份 `gold_attestation.json`：

- **fingerprint_verified**：Gold SQL 摘要、投影列名和墙钟敏感标记与冻结用例一致；每个 PR 的单元测试会校验；
- **gold_matched**：在固定数据库快照上执行全部 Gold，`result_digest` 与 attestation 一致；由 `verify-tpcds` / `verify-bird` 写入。

正式 **全量** 外部模型评测（30/30 或 50/50）必须在 `gold_matched` 状态下启动。小样本诊断只要求指纹层通过。

**P1 门禁（CI / nightly）**：工作流 [`.github/workflows/external-gold.yml`](../.github/workflows/external-gold.yml) 在 `push`（`cursor/**` 与评测路径）与 **UTC 06:00 日调度** 上跑单元门禁 + `check-external-release`；仓库变量 `EXTERNAL_GOLD_TESTS=1` 且配置 `BIRD_DATABASE_ROOT` 时额外跑集成 Gold 冒烟。发布前本地仍应执行 `verify-tpcds` / `verify-bird` 并刷新 attestation。

可选集成冒烟（5 条 TPC-DS + 5 条 BIRD）在设置 `EXTERNAL_GOLD_TESTS=1` 且准备好数据库后运行； nightly 或发布前应跑满 verify 并提交更新后的 attestation。

TPC-DS 派生用例在 `cases.yaml` 中带 `semantic_contract`（由问句与 `expected_columns` 生成，不反解析 Gold SQL）。发布前运行 `check-external-release`；通过表示两份 attestation 均为 `gold_matched` 且快照哈希已写入。

### 2.6 外部模型评测（P2）

- 命令：`python -m app.evaluation.external_model --source bird|tpcds-derived`；全量加 `--full`（要求 `gold_matched`）。默认 `--variant self_healing`、`--max-repair-rounds 4`（5 次模型调用）、`--timeout 180`。
- 粗分类：`matched` / `sql_error` / `other_result_mismatch`（用于 EX 汇总）。
- 细分类：复用自建 badcase 规则（如 `missing_required_table`、`grouping_grain`、`join_semantics`），写入 `diagnosis_class` 与 `symptoms`；Gold 只在此阶段读取，且 **按 `case.dialect` 解析 Gold SQL**（BIRD SQLite 不再误报 `response_shape`）。`join_semantics` 对 **GROUP BY 仅差表别名** 的情况不再误报（与电商 `order_id` 去重区分）。
- 报告额外统计：`context_recall`、`sql_table_recall`、维度/实体/度量覆盖、串库次数、`diagnosis_histogram`。
- Generic Prompt 版本 `text-to-sql-generic-v9`：在 v8 基础上增加窗口函数分层写法提示；v8 强调 SQLite 双引号别名、多属性/SAT/charter；v7 增加 TPC-DS 促销 join 与实体表提示。TPC-DS 冻结契约含 `core_tables=`（审计表清单，Prompt 提示）并在未涉及促销时禁止多余 `promotion` JOIN。
- 外部模型评测会把 cases.yaml 中的 **`semantic_contract`**（与问句一并冻结，非 Gold SQL）注入输出形状，并在自愈阶段做投影/缺表复核。TPC-DS 契约含 `primary_fact=`、`core_tables=` 与 **`audit_tables_strict=true`**（自愈阶段禁止 JOIN 审计清单外业务表）；BIRD 含 `core_tables=`（Prompt 提示）与 `order_sensitive`。
- 环境变量（外部模型评测最低要求）：
  - `DEEPSEEK_API_KEY`（必填）
  - BIRD：`--database-root` 指向 `dev_databases`；可选 `BIRD_DATABASE_ROOT` 供集成测试
  - TPC-DS：`POSTGRES_USER` / `POSTGRES_PASSWORD` 或 `TPCDS_POSTGRES_*`，库名默认 `tpcds`
  - 不再要求电商 `SANDBOX_DB_PASSWORD`（`external_model` 使用独立 LLM 配置）
- 可选集成：`EXTERNAL_MODEL_TESTS=1` 且具备 API 与 BIRD 路径时跑 1 条 BIRD 模型冒烟；`EXTERNAL_GOLD_TESTS=1` 跑 Gold 执行冒烟。
- **Measured 基线（2026-10-05，DeepSeek Chat，本地快照）**：报告在 `reports/`（不入 Git）。
  - **v9 + TPC-DS 冻结 repair（audit / UNION / 直邮 IN / 库存卖过子查询）**（`self_healing`，180s）：TPC-DS 当前最佳 **10/30（EX 0.333）**（`run_20261005T193700Z_e4360d4_*`，含 `002`+`009`）；上一档 **9/30**（`1d55618` / `bc26f6f`）。较 v8 **4/30** 提升。
  - **`90bd539` 契约修正**：`promotion_channel=dmail` / `promotion_via_item_sk_subquery` 仅对问句含 **直邮** 生效（不再误伤「促销名称/目的」类用例，如 `tpcds_complex_011`）；`multi_channel_union` 时跳过对 per-channel `item_sk` CTE 的 sk-heavy 误报（`008` Gold 可通过复核）；Prompt 增加 `promo_name` / `call_center_state` / `page_type` 等列映射。
  - **同提交全量复跑**（`self_healing`，180s）：TPC-DS **11/30（EX 0.367）**（`run_20261005T194537Z_90bd539_*`），新增匹配 **`011`**（促销名称 JOIN）；`002` 本 run 未匹配（方差）。后续 shape 修正：目录/网站**退货**不再误要 `*_sales`/`store` 维表；退货金额列与收入带 JOIN 路径提示。
  - **`907a5f9` 冻结复核 + shape**（`self_healing`，180s）：TPC-DS **17/30（EX 0.567）**（`run_20261005T195230Z_907a5f9_*`）。新增 **`005–008、013、028`** 等；`010` 仍因「门店销售」误要 `store` 维表在 repair 中摇摆（`aaad221` 将「门店销售」仅绑定 `store_sales`）。
  - **`9b50e5d` 契约分派**（cross-channel / pivot / returns union + 销售实体收紧）（`self_healing`，180s）：TPC-DS **23/30（EX 0.767）**（`run_20261005T195921Z_9b50e5d_*`）。新增 **`010、015、019、025、026、029`** 等；未匹配 7 条。
  - **`0b127cb` 尾部用例**（inventory sold join / return-linked sales / pivot INNER / catalog demo）（`self_healing`，180s）：TPC-DS **28/30（EX 0.933）**（`run_20261005T200505Z_0b127cb_*`）；未匹配 **`013、024`**。同提交 BIRD 全量 **2/50**（`run_20261005T200401Z_0b127cb_*`，低于历史 **4/50** 峰值，作方差/回归对照）。
  - **`f28fa5c` audit 全覆盖 + pivot web 禁 warehouse**（`self_healing`，180s）：**`013`、`024` 匹配**（`run_20261005T201136Z_f28fa5c_*`）；本 run 方差未匹配 **`023、030`**（仍为 **28/30**）。Oracle 对比：`024` 失败主因是 web CTE 误 JOIN `warehouse`；`013` 缺 `customer` JOIN 多 1 行。
  - **`1957e34` 度量/库存契约**（`self_healing`，180s）：**`013、030` 匹配**（`run_20261005T202139Z_1957e34_*`）；**28/30**；未匹配 **`023`（熔断 sql_error，终态 SQL 本地 EX=1）**、**`024`（LEFT JOIN+COALESCE）**。`quantity_on_hand` 不再误入 GROUP BY 键。
  - **`c86d822` pivot LEFT 禁 COALESCE**（`self_healing`，180s）：**29/30**（`run_20261005T203139Z_c86d822_*`）；仅 **`023`** 因 workflow `failed` 未计 EX（终态 SQL 本地 **EX=1**）。**`external_model.score_prediction`** 现对可执行终态 SQL 仍算 EX（熔断不再假阴性）。
  - **BIRD badcase 方言修复后**（`f9ff550`）：EX 仍 **4/50**；诊断从误报 **26× response_shape** 变为 **12× join_semantics / 15× other** 等可行动类别（`run_20261005T185929Z_f9ff550_*`）。`4d1608f` 再修正 alias GROUP BY 误报 **join_semantics**（**5×** vs 12×，EX 2/50 为方差，见 `run_20261005T192405Z_*`）。
  - **v8 + BIRD/TPC-DS `semantic_contract`**（`self_healing`，180s）：BIRD 最佳 **4/50（EX 0.08）**（`run_20261005T165629Z_*`）；软校验后复跑 **3/50**（`run_20261005T170258Z_*`，熔断更少）。TPC-DS 早期 **3/30**（`run_20261005T160104Z_*`）。
  - 早期 v7 无 BIRD contract：**0/50** BIRD。
  - 迭代时对比 `reports/*/summary.json` 的 `measured.execution_accuracy` 与 `diagnosis_histogram`。

## 3. 用例生命周期

每条用例依次通过：

1. 把自然语言问题拆成投影、分组、过滤、时间窗口、实体范围和去重粒度六项语义契约；
2. Schema 和 Gold SQL 静态校验；
3. Gold SQL 在固定数据快照执行成功；
4. 结果非空且具有区分度；
5. `required_tables` 与 Gold SQL 实际引用一致；
6. 独立 Oracle SQL 或人工枚举结果与 Gold 结果一致；
7. 同组自然语言和规范化 SQL 去重；
8. Junction Table 不存在于 Seed 检索库；
9. 固定随机种子下重复执行结果一致；
10. 固化结果摘要、复核人和数据库快照；
11. 冻结为不可变 Benchmark Case。

评测 Prompt 只包含问题、允许的工具结果和当前策略召回的 Schema，不包含 Gold SQL、Gold 结果、`required_tables` 或难度标签。

### 3.1 自建 Gold 正确性分级

自建用例必须分别记录以下状态，不能用“Gold 已验证”笼统表示：

| 状态 | 含义 | 可用于正式 EX |
| --- | --- | --- |
| `executable` | SQL 可解析、只读、可执行且结果非空 | 否 |
| `contract_checked` | SQL 的投影、分组、过滤、时间和去重粒度与问题契约逐项一致 | 否 |
| `oracle_matched` | 独立实现的 Oracle 结果与 Gold 结果一致 | 是 |
| `reviewed` | 至少两名复核者确认问题、契约和 Oracle 没有共同歧义 | 是 |

Oracle 不能由主 Gold SQL 做字符串改写得到。允许的独立校验方式包括：

- 对 Basic 小结果集手工枚举主键和值；
- 用不同查询结构重写，例如相关子查询对照 `JOIN + GROUP BY`；
- 先在 Python 中按主键集合计算，再与数据库结果比较；
- 对复杂金额题分别核对“订单去重集合”和最终聚合，避免两个 SQL 共享同一个重复聚合错误。

每条冻结用例新增或伴随保存：

```text
semantic_contract:
  projections: [...]
  group_keys: [...]
  filters: [...]
  category_scope: exact|descendants
  time_window: {start: ..., end: ..., anchor_date: ...}
  dedup_key: null|order_id
oracle:
  method: manual|independent_sql|python
  result_digest: sha256:...
  row_count: ...
  reviewer_ids: [...]
```

`result_digest` 必须基于 Canonical Cell 结果生成，且绑定数据库快照。修改问题、Gold SQL、造数逻辑或语义契约后，原摘要立即失效，必须重新审核。

## 4. 消融矩阵

| 组 | Schema 输入 | 图扩展 | 错误反馈 |
| --- | --- | --- | --- |
| A Zero-Shot | 无检索上下文或约定的最小数据库说明 | 否 | 否 |
| B Schema-RAG | 动态召回的种子表 | 否 | 否 |
| C Schema Graph | 动态召回的种子表 | 是 | 否 |
| D Self-Healing | 动态召回的种子表 | 是 | 是 |

D 组在 SQL 已经执行成功时仍做静态复核，检查投影、问句点名的实体、外键 JOIN、聚合粒度、笛卡尔积、空结果或触顶结果，以及 EXPLAIN 计划行数。复核失败才把这些发现交给模型。C 组执行成功后结束。复核只有问题、当前 SQL、已选 Schema 和执行规模，没有 Gold SQL、Gold 结果、`required_tables` 或难度。

四组必须固定：

- 模型名称和版本；
- System Prompt 版本；
- 数据库快照；
- 最大输出 token；
- 用例顺序；
- Baseline 所需的采样温度。

报告同时给出每组整体 EX 和 Basic/Medium/Complex 分层 EX，不能只展示最佳分组。

## 5. Execution Accuracy

### 5.1 判定

Agent SQL 与 Gold SQL 在同一数据库快照中执行。比较执行结果而不是 SQL 字符串：

```text
EX(case) = 1  当且仅当结果集语义等价
EX(case) = 0  其他情况，包括生成失败、语法错误、超时和熔断
```

无 `ORDER BY` 时按行多重集比较，保留重复行数量；有顶层 `ORDER BY` 且顺序属于问题语义时按顺序比较。

### 5.2 Canonical Cell

语义模式采用以下规则：

- `NULL` 独立标记；
- Boolean 与 Numeric 分离；
- 有限 `int`、`BIGINT` 和 `Decimal` 统一转为精确 Decimal，默认精确比较；
- Float 通过 `Decimal(str(value))` 消除二进制表示噪声，但不做全局四位量化；
- 只有用例显式声明 `numeric_tolerance` 时才允许误差比较；
- NaN、正无穷和负无穷分别标记；
- 无时区 Timestamp 按 Benchmark 配置的 UTC 解释；
- 有时区 Timestamp 转换为 UTC 并保留微秒；
- Date 保留 `YYYY-MM-DD`；
- 字符串只移除首尾空白，不默认忽略大小写。

数值归一化不能先转为二进制 Float，以免损失 BIGINT 精度。容差是用例契约的一部分，不能由比较器隐式放宽，否则会产生 EX 假阳性。

### 5.3 列语义

默认要求列数和列顺序一致，但不要求 Alias 文本一致。需要忽略列顺序的特殊用例必须显式声明，不能由比较器自动猜测。

## 6. Pass、OptimizePass 与 Recovery

- Text-to-SQL `Pass@1`：温度 `0.0`，无反馈的单次候选；
- Text-to-SQL `Pass@3`：温度 `0.3`，三个相互独立的候选，任一通过 EX 即成功；
- `Recovery@3`：首次生成失败后，基于结构化沙箱错误最多执行三轮连续修复。
- 慢 SQL `OptimizePass@1`：单个改写候选同时满足结果等价、达到用例声明的 `min_primary_drop`，且次要指标没有突破退化上限；
- 慢 SQL `OptimizePass@3`：三个独立改写候选中至少一个满足上述条件。

Text-to-SQL Pass、慢 SQL OptimizePass 与 Recovery 必须分别报告，不能把独立采样、性能优化和反馈修复混为同一指标。

当 OptimizePass@3 有多个合格候选时，按“主指标降幅最高、Execution Time 更低、候选序号更小”的稳定顺序选择一个代表候选。逐条报告只能使用该候选，不能人工挑选不同候选分别计算不同指标。

## 7. Schema Graph 指标

### 7.1 Junction Table Recall

```text
recall =
  成功补全的必需 Junction Table 数
  / Gold SQL 所需 Junction Table 总数
```

只在 `required_junctions` 非空的用例上计算。表必须由图扩展加入，若曾作为向量种子返回则该用例标记为检索泄漏并从有效报告中单独列出，不能算成功。

### 7.2 Context Token

使用最终请求 DeepSeek 的 tokenizer 对 Schema Context 单独计数。报告：

- Baseline Schema token；
- Enhanced Schema token；
- 平均值、中位数和 P95；
- 超过 3.5k 预算的用例数。

“降低 70%”在产生报告前属于目标值。

## 8. 慢 SQL 等价性与性能

改写 SQL 必须先通过结果等价校验，再进入性能改善统计。失败或不等价候选不能通过仅改善 Cost 获得成功。

### 8.1 指标

```text
planner_cost_drop =
  (raw_total_cost - optimized_total_cost) / raw_total_cost

execution_time_drop =
  (raw_median_ms - optimized_median_ms) / raw_median_ms

shared_buffer_access =
  shared_hit_blocks + shared_read_blocks

shared_buffer_access_drop =
  (raw_access - optimized_access) / raw_access

shared_read_blocks_drop =
  (raw_read - optimized_read) / raw_read
```

`Shared Read Blocks` 表示共享缓冲区未命中后读取的块，可能来自操作系统页缓存或存储层，不能严格表述为物理磁盘读取。

分母为零时该降幅记为 `null/not_applicable`，不能强行记为 0% 或 100%。

### 8.2 测量协议

```text
PostgreSQL 16
CPU: 2
Memory: 2 GB
Concurrency: 1
max_parallel_workers_per_gather: 0
```

每个用例：

1. 从固定快照创建隔离数据库；
2. 应用该用例的索引前置条件；
3. 执行 `ANALYZE`；
4. 原 SQL 和优化 SQL 各预热一次；
5. 按交替顺序各运行 5 次；
6. 使用 Execution Time 中位数；
7. 记录 Planner Cost、Hit Blocks 和 Read Blocks；
8. 丢弃该用例数据库。

聚合报告同时展示：

- 所有 50 条用例的成功率；
- 结果等价且优化成功用例的性能分布；
- 负优化、超时和不等价数量；
- P50、P90，而不只展示平均值。

Target 对应的性能降幅使用 `macro_drop_all_eligible`：对所有指标分母有效的慢 SQL 用例做算术平均；生成失败、不等价、超时或没有改善的用例按 0 计入，负优化保留负值。原始分母为零的用例记为不适用、从该指标分母排除，并单独报告数量。

报告还应提供 `drop_on_success` 分布作为诊断信息，但不得用它替换 Target 对应的全量宏平均。

68.4%、74.2% 和 81.0% 三项性能 Target 固定基于 **OptimizePass@1 的唯一候选**计算，避免三候选择优造成性能数字膨胀。OptimizePass@3 只对应 86% 成功率目标；其代表候选性能作为独立诊断报告，不与上述三项 Target 混用。

## 9. Target 与 Measured

以下数字在评测运行前一律标记为 Target：

| 指标 | Target |
| --- | ---: |
| 自建整体 EX | 83% |
| Junction Table Recall | 96.8% |
| Planner Cost Drop（全量宏平均） | 68.4% |
| Execution Time Drop（全量宏平均） | 74.2% |
| Shared Read Blocks Drop（全量宏平均） | 81.0% |
| 慢 SQL OptimizePass@1 | 72% |
| 慢 SQL OptimizePass@3 | 86% |

Measured 值只能由带原始 JSON Log 的评测任务产生。README 和简历引用时必须注明数据集、版本、样本量和运行条件。

## 10. 报告最小元数据

```json
{
  "git_commit": "<sha>",
  "benchmark_source": "custom|tpcds-derived|bird",
  "benchmark_version": "<version>",
  "database_snapshot": "<content-hash>",
  "model": "deepseek-chat",
  "embedding_model": "BAAI/bge-m3",
  "prompt_version": "<version>",
  "random_seed": 20261001,
  "started_at": "<UTC timestamp>",
  "environment": {
    "postgres": "16",
    "cpu_limit": 2,
    "memory_limit_gb": 2
  }
}
```

## 11. Badcase 诊断与改进闭环

### 11.1 诊断基线

本节方案来自本地报告
`run_20261005T031840Z_540294bece233a04032a8fb7e006477775742331`。
该报告是一次诊断输入，不替代第 9 节的正式 Measured 发布流程。

Schema Graph 的主要失败不是缺表：Junction Table Recall 为 41/41，
`missing_required_table` 只剩 1 条。主类集中在：

- 82 条 `grouping_grain`；
- 27 条 `projection`；
- 10 条递归 CTE 写法导致的 `undefined_table`；
- 4 条“上个月”查询被函数门禁拒绝；
- 1 条 `filter_scope`。

Self-Healing 中 27 条发生了重试，没有一条在重试后通过 EX；9 条最终熔断。
因此下一轮优先修复答案形状和复核误报，不继续扩大 Schema 召回范围。

诊断是事后步骤，可以读取 Gold、`required_tables` 和难度，但这些字段仍禁止进入生成、
复核和修复 Prompt。每条 badcase 保存预测 SQL 的结构摘要，不把完整 Gold SQL复制到模型上下文。

### 11.2 统一 badcase 分类

每条结果只进入一个主类，按以下优先级分类：

1. `matched`；
2. `circuit_breaker`；
3. SQL 门禁或数据库错误；
4. `missing_required_table`；
5. `time_anchor`；
6. `grouping_grain`；
7. `filter_scope`；
8. `join_shape`；
9. `projection`；
10. `other_result_mismatch`。

同时保存非互斥症状，至少包括：

- 缺少和多出的投影；
- Gold 与预测的外层分组键；
- 聚合是否只存在于 CTE；
- 缺少的过滤字面量；
- `exact` 被改成 `descendants` 的品类范围；
- JOIN 等号对和 JOIN 类型差异；
- 固定时间窗口是否被运行时日期替换；
- 递归 CTE 是否声明 `WITH RECURSIVE`；
- 每次修复的错误类别和规范化错误哈希。

主类用于汇总，症状用于定位；不能因为主类是 `grouping_grain` 就丢弃同一条 SQL 的投影、
过滤和 JOIN 差异。

### 11.3 P0：先加回归护栏

在调整 Prompt 或模型策略之前，先完成以下确定性改动：

1. **Gold 独立校验**
   - 为 132 条自建用例补齐第 3.1 节的语义契约和结果摘要；
   - Basic 使用手工枚举或 Python Oracle，Medium/Complex 使用独立查询结构；
   - 对“末级品类”“品类是否包含子类”“统计数量是否回显维度”等歧义逐条定稿；
   - 新增测试，要求 132 条全部达到 `oracle_matched`，否则正式 EX 任务拒绝启动。
2. **函数门禁名称归一化**
   - 在 SQLGlot AST 类型和 PostgreSQL 表面函数名之间建立显式映射；
   - `TimestampTrunc` 按渲染后的 `DATE_TRUNC` 审计，不能因为内部 `sql_name()` 是
     `TIMESTAMP_TRUNC` 而误拒绝；
   - 不扩大未知函数白名单；运行时钟函数和固定 `anchor_date` 的语义冲突由时间规则单独检查。
3. **递归 CTE 静态检查**
   - CTE 在自身定义内被引用时，必须存在 `WITH RECURSIVE`；
   - 在查询数据库前返回 `recursive_cte_missing`，修复 Prompt 明确要求补关键字或改成非递归等值过滤；
   - 用报告中的 10 条 CTE 自引用 case 建回归测试。
4. **CTE 血缘感知的 JOIN 检查**
   - 为每个 CTE 记录输出列到物理表列的血缘；
   - 物理表与 CTE JOIN 时，沿血缘验证底层 FK；无法证明时记为
     `join_unverified`，不能直接判为 `join_not_on_graph`；
   - `custom_medium_047`–`050` 和 `custom_complex_023` 必须不再因可解释的
     CTE JOIN 重复熔断。
5. **诊断器遍历完整查询树**
   - 分别保存外层和每个 CTE 的投影、聚合、分组及 JOIN；
   - 不再把“CTE 内已分组、外层改写结果形状”简化为“完全没有聚合”。

P0 只消除评测不确定性和确定性误报，不以提高 EX 为验收条件。

### 11.4 P1：生成前先建立答案契约

新增不读取 Gold 的 `AnswerContract`，从问题和固定业务词典提取：

```text
dimensions       要逐行返回的实体，如会员等级、商家、地区、品类
dimension_fields 要回显的名称、编号和常量标签
measures         count、sum(quantity)、sum(quantity * price) 等
filters          状态、VIP、地区、券类型、自营标记
category_scope   exact 或 descendants，默认 exact
time_window      由 anchor_date 展开的半开区间 [start, end)
dedup_key        金额汇总前需要去重的业务主键
```

生成 Prompt 在 Schema Context 之前显示这个契约，并要求：

- 每个 `dimension` 必须出现在最终投影；多行答案必须出现在最终结果粒度中；
- 问句给定单个维度值时，若输出契约要求回显该维度，不能只返回一个标量；
- 月份、状态和类型是否作为结果列由契约决定，不能只凭模型偏好增删；
- 品类名默认精确匹配。只有问题明确表达“及其子类、全部下级”时才能递归展开；
- “上个月”必须用用例提供的 `anchor_date` 展开为固定常量，不能使用
  `CURRENT_DATE`、`CURRENT_TIMESTAMP` 或 `clock_timestamp`；
- 复杂金额题先按 `dedup_key` 形成合格事实集合，再做最终聚合。

`AnswerContract` 来自问题和业务规则，不读取 Gold。评测报告保存契约摘要，便于判断是契约抽取错误还是
SQL 生成错误。

### 11.5 P2：执行成功后的契约复核

Self-Healing 在 SQL 执行成功后，使用同一个 `AnswerContract` 做确定性复核：

1. 最终结果投影覆盖 `dimension_fields + measures`；
2. 最终结果粒度覆盖 `dimensions`，包括聚合位于 CTE 的情况；
3. `exact` 品类不能出现额外的 `parent_id` 展开或递归品类树；
4. 时间谓词与展开后的固定半开区间一致；
5. 聚合前去重键符合契约；
6. CTE JOIN 只在血缘证明违反 FK 时才报错；
7. 执行成功但契约不满足时，错误消息列出“期望”和“实际”，只触发一次定向修复。

修复后先重跑 AST 和契约复核，再执行 SQL。若修复没有改变对应症状，不消耗三轮相同提示；
直接标记 `no_progress` 并熔断。报告必须区分：

- SQL/数据库错误修复成功；
- 契约复核修复成功；
- 执行成功但 EX 仍失败；
- 复核误报或无进展熔断。

### 11.6 实施文件与测试映射

| 工作项 | 主要落点 | 必需测试 |
| --- | --- | --- |
| Gold 语义契约和 Oracle 摘要 | `app/evaluation/custom_cases.py`、`benchmarks/custom_ecommerce/` | 132 条 Oracle 与 Gold Canonical Rows 一致 |
| AST 函数名归一化 | `app/sandbox/gate.py` | `DATE_TRUNC` 不因 `TimestampTrunc` 内部名误拒绝；未知函数仍拒绝 |
| 递归 CTE 检查 | `app/sandbox/gate.py` 或独立 AST 检查器 | 10 条自引用样例均在执行前定位 |
| CTE 血缘 JOIN | `app/agents/text_to_sql/semantic.py` | 物理 FK、合法 CTE JOIN、非法 CTE JOIN 各有正反例 |
| AnswerContract | `app/agents/text_to_sql/` 新模块 | 投影、粒度、品类范围、时间锚点、去重键单测 |
| Prompt 接入 | `app/agents/text_to_sql/prompt.py` | Prompt 含契约，不含 Gold、难度和 `required_tables` |
| 自愈路由 | `app/agents/text_to_sql/workflow.py` | 定向修复、`no_progress`、最大调用数和 SQL 隐藏契约 |
| 完整 SQL 形状 | `app/evaluation/sql_shape.py` | 外层与 CTE 分开报告，解析失败保留局部诊断 |
| badcase 汇总 | `app/evaluation/ablation.py` | 分类总数等于分母，主类与症状均可追溯到 case JSON |

### 11.7 验收门槛

按 P0、P1、P2 顺序提交，每一步都保留相同模型、温度、数据库快照和用例顺序，做配对比较。

P0：

- 132/132 自建用例达到 `oracle_matched`，且复核元数据完整；
- Gold、Oracle 和结果摘要与数据库快照绑定；
- 10 条递归 CTE 错误能在执行前稳定分类；
- `DATE_TRUNC` AST 名称误判和 5 条 CTE JOIN 复核误报都有回归测试；
- 所有未知或有副作用的函数仍被拒绝。

P1：

- 报告中的 27 条投影 case 和 82 条粒度 case 均生成 AnswerContract 回归夹具；
- 夹具只验证契约抽取和静态发现，不把 Gold 内容送进 Prompt；
- 品类精确范围、固定时间窗口、订单去重分别有正反例。

P2：

- 所有 `attempts > 1` 的 case 都保存“触发症状 → 修复变化 → 最终结果”链路；
- 相同 SQL 或相同症状不允许无变化地连续消耗三轮；
- Recovery@3 必须单独报告，不能把首轮随机命中算作恢复；
- Schema Graph 的 Junction Table Recall 和 Required Table Recall 不得回退；
- EX、分类计数和组间转移矩阵由原始 case JSON 重算，不能手工填写。

一次新消融只有在 P0 全部通过后才可用于比较模型正确性。若 Gold 审核导致问题、SQL 或结果摘要变化，
必须提升 `benchmark_version`，旧报告只保留为历史基线，不能与新版本直接计算提升比例。
