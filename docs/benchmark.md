# Benchmark 与验收规范

## 1. 原则

评测必须可复现、可解释并避免数据泄漏：

- 自建、TPC-DS 派生和 BIRD 三套结果独立报告；
- Baseline 与 Enhanced 使用相同数据、模型和采样参数；
- Gold SQL 只存在于评测侧，不能进入 Agent Prompt 或检索库；
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

## 3. 用例生命周期

每条用例依次通过：

1. Schema 和 Gold SQL 静态校验；
2. Gold SQL 在固定数据快照执行成功；
3. 结果非空且具有区分度；
4. `required_tables` 与 Gold SQL 实际引用一致；
5. 同组自然语言和规范化 SQL 去重；
6. Junction Table 不存在于 Seed 检索库；
7. 固定随机种子下重复执行结果一致；
8. 冻结为不可变 Benchmark Case。

评测 Prompt 只包含问题、允许的工具结果和当前策略召回的 Schema，不包含 Gold SQL、Gold 结果、`required_tables` 或难度标签。

## 4. 消融矩阵

| 组 | Schema 输入 | 图扩展 | 错误反馈 |
| --- | --- | --- | --- |
| A Zero-Shot | 无检索上下文或约定的最小数据库说明 | 否 | 否 |
| B Schema-RAG | 动态召回的种子表 | 否 | 否 |
| C Schema Graph | 动态召回的种子表 | 是 | 否 |
| D Self-Healing | 动态召回的种子表 | 是 | 是 |

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
