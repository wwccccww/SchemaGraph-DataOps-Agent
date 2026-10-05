# 系统架构

## 1. 目标与边界

SchemaGraph-DataOps-Agent 面向两类彼此独立的任务：

1. 将自然语言问题转换为可执行 SQL，并解决复杂数仓中无语义中间表无法被普通向量检索召回的问题。
2. 对已有慢 SQL 做静态诊断、执行计划分析、自动改写和结果等价性验证。

两类任务共享模型网关、SQL 解析器、只读数据库沙箱、可观测性和评测框架，但从入口开始分流，不在同一条工作流中串行执行。

当前交付目标是 **Benchmark-grade 企业原型（M2）**。多租户、企业 RBAC、高可用、数据脱敏和生产 SLA 不属于首期范围。

## 2. 技术栈

| 层级 | 选型 |
| --- | --- |
| 语言与 API | Python 3.12、FastAPI、Pydantic v2 |
| Agent 编排 | LangGraph |
| 工具协议 | MCP Protocol |
| 大模型 | DeepSeek-V3（OpenAI-compatible API） |
| Embedding | BAAI/bge-m3，1024 维 |
| 元数据与向量库 | PostgreSQL 16、pgvector |
| 图计算 | NetworkX |
| SQL 解析 | SQLGlot |
| 数据访问 | SQLAlchemy 2、AsyncPG |
| 沙箱 | Docker、PostgreSQL 只读 Role 与只读事务 |
| 评测 | Pytest、Pandas、NumPy、Faker |
| 可观测性 | OpenTelemetry |

## 3. 逻辑架构

```text
                              ┌─────────────────────┐
                              │ FastAPI / CLI Router│
                              └──────────┬──────────┘
                           ┌─────────────┴─────────────┐
                           │                           │
                    natural_language               slow_sql
                           │                           │
                           ▼                           ▼
               ┌──────────────────────┐     ┌──────────────────────┐
               │ Text-to-SQL Workflow │     │ Slow SQL Workflow    │
               └──────────┬───────────┘     └──────────┬───────────┘
                          │                            │
             Tool-RAG + Schema-RAG              SQLGlot 只读检查
                          │                            │
                 Schema Graph 扩展               静态规则诊断
                          │                            │
                   DeepSeek 生成                 EXPLAIN 分析
                          │                            │
                    SQLGlot 校验                  DeepSeek 改写
                          └────────────┬───────────────┘
                                       ▼
                           ┌──────────────────────┐
                           │ PostgreSQL 只读沙箱  │
                           └──────────┬───────────┘
                          ┌───────────┴────────────┐
                          │                        │
                     执行成功                  执行失败
                          │                        │
                   EX/结果等价校验          Error Hash 自愈
                                                   │
                                         同错连续 3 次熔断
```

## 4. Text-to-SQL 工作流

### 4.1 状态

| 状态 | 输入 | 输出 |
| --- | --- | --- |
| `route_tools` | 自然语言问题 | Top-3 MCP 工具定义 |
| `retrieve_schema` | 自然语言问题 | 注释命中的实体种子；无命中时向量最多 5 张 |
| `expand_schema_graph` | 种子表集合 | 受约束的 Schema 子图 |
| `build_prompt` | 问题、子图、工具结果 | 不超过预算的模型上下文 |
| `generate_sql` | 模型上下文 | SQL 候选 |
| `validate_sql` | SQL 候选 | AST 校验结果 |
| `execute_sql` | 合法只读 SQL | 结果集或结构化错误 |
| `repair_sql` | SQL、错误与上下文 | 修复后的 SQL |
| `finish` | 成功结果或熔断状态 | API 响应 |

### 4.2 不变量

- Junction Table 不能成为 Schema-RAG 种子表。
- 图扩展后的表数量不超过 12。
- Schema Context 使用 DeepSeek 对应 tokenizer 计数，不超过 3.5k token。
- 生成 SQL 必须通过应用层 AST 门禁和数据库层只读门禁。
- 同一规范化错误连续出现 3 次时立即熔断。
- 工作流必须设置最大总迭代数，避免不同错误交替出现导致无限循环。

## 5. 慢 SQL 工作流

```text
Raw SQL
  → SQLGlot AST 只读检查
  → 静态规则诊断
  → EXPLAIN (FORMAT JSON)
  → 可选 EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
  → LLM 生成改写候选
  → 原 SQL / 改写 SQL 结果等价性校验
  → Planner Cost、Execution Time、Buffer Access 对比
```

静态规则首期覆盖：

- `SELECT *`
- 缺失过滤条件的大表扫描
- 索引列上的函数或隐式类型转换
- 非必要相关子查询
- 可提前聚合却在多对多 Join 后聚合
- 无界排序、重复去重和冗余 Join

只有同时满足以下条件的候选才算优化成功：

1. 改写 SQL 仍为只读查询；
2. 与原 SQL 的执行结果通过语义 EX；
3. 达到慢 SQL 用例声明的主指标最小改善阈值；
4. 次要指标没有突破用例声明的最大退化比例；
5. 没有超过执行时间、结果行数和资源限制。

## 6. MCP Tool-RAG

首期注册 10 个只读工具：

1. `get_table_schema`
2. `get_column_enums`
3. `get_foreign_keys`
4. `get_table_row_count`
5. `get_partition_keys`
6. `explain_sql_cost`
7. `check_sql_syntax`
8. `get_etl_status`
9. `get_data_owner`
10. `get_metric_definition`

工具定义完整上下文 3.8k token、Top-3 上下文 1.1k token 均为设计预算。实际 token 必须由固定工具 Schema 和模型 tokenizer 测量；71% 降幅在评测完成前属于目标值。

MCP 负责标准化工具接口；实际数据库权限、安全校验和超时仍由工具实现负责，不能依赖协议本身保证安全。

## 7. 可观测性

每个请求建立一条 OpenTelemetry Trace，并至少记录：

- `request_type`
- `model_name`
- `retrieved_seed_tables`
- `expanded_tables`
- `schema_context_tokens`
- `selected_tools`
- `generation_attempt`
- `sql_hash`
- `error_hash`
- `db_execution_ms`
- `planner_total_cost`
- `result_row_count`
- `circuit_breaker_triggered`

不得在 Trace 中记录数据库密码、API Key、完整用户隐私字段或未经脱敏的大结果集。

## 8. 交付成熟度

| 等级 | 定义 |
| --- | --- |
| M0 | 架构、数据模型和验收规范完成 |
| M1 | 10 条冒烟用例打通端到端链路 |
| M2 | 自建、TPC-DS 派生和 BIRD 三轨评测可复现 |
| M3 | 多租户、RBAC、审计、脱敏、HA 与生产 SLA |

首期以 M2 为目标，README 和简历不得在评测报告生成前将目标指标描述为实测成果。
