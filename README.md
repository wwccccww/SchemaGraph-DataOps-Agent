# 🕸️ SchemaGraph-DataOps-Agent

面向复杂数仓 Join 的 Text-to-SQL 与慢 SQL 智能诊断 Agent。

本项目通过 Schema-RAG、外键图拓扑和只读执行沙箱，解决 7～12 表关联中无语义中间映射表无法被普通向量检索召回的问题；同时提供基于 SQLGlot 与 PostgreSQL 执行计划的慢 SQL 诊断、改写和结果等价性验证。

> 当前状态：阶段 0–8 已完成（工程基础、12 表确定性数据、Schema Graph、Schema-RAG 与 Tool-RAG、Text-to-SQL 纵向闭环、慢 SQL 诊断与四类冒烟用例、自建 132 条用例以及 A/B/C/D 消融和可追溯报告、TPC-DS 派生 30 条查询和 BIRD 50 条复杂用例、OpenTelemetry Trace、密钥扫描、容器资源与网络策略）。50 条慢 SQL 报告尚未实现。性能与准确率百分比均为 Benchmark Target，尚不是实测结果。TPC-DS 派生结果不是官方 TPC-DS 成绩。BIRD 结果只表示公开 Benchmark 兼容性。

---

## 核心能力

### Schema Graph

- 表名、中文表注释、列注释和品类取值命中的实体表直接成为种子；没有这类命中时，BGE-M3 按向量分差最多保留 5 张，不再固定补满 Top-5；
- 在 Seed 阶段屏蔽 Junction Table；
- NetworkX 先执行 1-Hop-per-Seed Junction 补全，即桥表距两个 Seed 各 1 hop；
- 未连通种子使用深度不超过 4 的受限最短路径；
- 最终上下文不超过 12 张表和 3.5k Schema token。

### Text-to-SQL 自愈

- DeepSeek-V3 为主业务生成 PostgreSQL SQL；BIRD 外部评测使用独立 SQLite 方言 Adapter；
- SQLGlot 做语法和全 AST 只读检查；
- PostgreSQL 最小权限 Role + READ ONLY 事务；
- 将 SQLSTATE 和规范化错误反馈给模型；
- 执行成功后复核投影、问句点名的实体、外键 JOIN、聚合粒度、笛卡尔积、空结果或过大结果，以及 EXPLAIN 计划行数；复核通过不再调用模型，只有自愈组在复核失败时进入原有修复；
- 同一 Error Hash 连续出现 3 次时熔断；
- 独立统计 Pass@1、Pass@3 和 Recovery@3。

### 慢 SQL 诊断

- 静态识别全表扫描、隐式转换、索引失效和重复聚合；
- 解析 `EXPLAIN (FORMAT JSON)` 的 Planner Cost；
- 受控执行 `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`；
- 自动改写后先验证结果等价，再比较 Cost、时间和 Buffer；
- 每个性能用例使用隔离数据库快照，避免索引和数据污染。

### Tool-RAG 与可观测性

- 10 个只读 MCP 元数据/诊断工具；
- 每次动态注入 Top-3 工具定义；
- OpenTelemetry 记录检索、图扩展、模型和数据库执行链路。

## 架构

```text
                          FastAPI / CLI Router
                         ┌─────────┴─────────┐
                         │                   │
                 Natural Language        Raw Slow SQL
                         │                   │
               Schema/Tool RAG          AST Diagnostics
                         │                   │
                  Schema Graph          EXPLAIN / Rewrite
                         │                   │
                    SQL Generate             │
                         └─────────┬─────────┘
                                   ▼
                      PostgreSQL Read-only Sandbox
                         ┌─────────┴─────────┐
                         │                   │
                    EX / Result         Error Hash
                    Equivalence         Self-Healing
```

Text-to-SQL 与慢 SQL 是两条入口分流的工作流，只共享底层模型、SQL 解析器、沙箱、可观测性和评测能力。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| API 与契约 | Python 3.12、FastAPI、Pydantic v2 |
| Agent 与工具 | LangGraph、MCP Protocol |
| 模型与检索 | DeepSeek-V3、BAAI/bge-m3、pgvector |
| 数据与图 | PostgreSQL 16、SQLAlchemy 2、AsyncPG、NetworkX |
| SQL 与沙箱 | SQLGlot、Docker |
| 评测与追踪 | Pytest、Pandas、NumPy、Faker、OpenTelemetry |

## Benchmark 规划

| 轨道 | 数量 | 用途 |
| --- | ---: | --- |
| 自建电商 Text-to-SQL | 132 | 主 EX、桥表召回和自愈 |
| TPC-DS 派生复杂查询 | 30 | 大型雪花 Schema 压力测试 |
| BIRD Complex | 50 | 公开跨领域泛化测试 |
| 慢 SQL | 50 | 等价改写与性能评测 |

三套 Text-to-SQL 数据分别报告，不计算混合准确率。TPC-DS 部分属于派生工作负载，不代表官方 TPC-DS 成绩。

### Target Metrics

| 指标 | 目标 |
| --- | ---: |
| 自建整体 EX | 83% |
| Junction Table Recall | 96.8% |
| Planner Cost Drop（全量宏平均） | 68.4% |
| Execution Time Drop（全量宏平均） | 74.2% |
| 慢 SQL OptimizePass@1 / @3 | 72% / 86% |

这些值只有在固定数据、模型、Prompt 和代码版本的评测任务完成后，才能由报告转换为 Measured。

### Measured

模型执行准确率、Junction Table Recall 和慢 SQL 降幅尚未测量。下表只记录已经跑完的 Gold 可执行性，运行条件写在同一行。

| 项目 | 结果 | 运行条件 |
| --- | --- | --- |
| 自建 132 条 Gold SQL | 可执行、非空、结果可区分 | PostgreSQL 16 + pgvector，数据库 `ecommerce`，集成测试 `test_custom_gold_sql_is_executable_and_discriminative` |
| TPC-DS 派生 30 条 | Gold 执行 30/30，非空且摘要唯一 | gregrahn/tpcds-kit `5a3a81796992b725c2a8b216767e142609966752`，本地 SF=1。不是官方 TPC-DS 成绩 |
| BIRD 复杂用例 50 条 | Gold 执行 50/50 | birdsql/bird_sql_dev_20251106 `3c11fb193e5439b338e23677fa0aae11e8b85db9`，受限 SQLite。只表示公开 Benchmark 兼容性 |
| 自建 EX / 桥表召回 | 未测量 | 需要配置模型后运行消融；报告里的 Measured 保持为空 |
| 慢 SQL 50 条报告 | 尚未运行 | 当前仓库只有 4 条冒烟用例 |

## 阶段 0–8 启动

阶段 0 提供 API、PostgreSQL 16 + pgvector、沙箱只读角色和测试入口。阶段 1 在显式执行造数后提供 12 表和 10 条冒烟 Gold SQL。阶段 2 提供外键图扩展。阶段 3 在显式建索引后提供 BGE-M3 Schema-RAG 和 Top-3 Tool-RAG。阶段 4 提供 DeepSeek 网关、LangGraph 问数、SQLGlot 只读门禁、沙箱执行和 Error Hash 熔断。阶段 5 提供独立的慢 SQL 诊断：静态规则、JSON 执行计划、改写候选、语义 EX，以及 Planner、Time 和 Buffer 降幅。四类冒烟用例各自使用隔离数据库。阶段 6 把自建评测扩到 50 Basic、50 Medium、32 Complex，并提供 A/B/C/D 消融。报告把 Target 和本次 Measured 分开保存，已有运行目录不会被覆盖。没有带日志的模型运行时，Measured 保持为空。阶段 7 增加 TPC-DS 派生 30 条 PostgreSQL 查询、BIRD 50 条复杂用例，以及受限 SQLite Adapter。外部报告按 `tpcds-derived` 和 `bird` 分开写入，不抄自建 Target，模型执行准确率保持为空。生成的 TPC-DS 数据和 BIRD 的 SQLite 文件不进入 Git，由脚本按固定版本重新获取或生成。API 启动不会自动造数、下载向量模型或下载 tokenizer。Gold SQL、Gold 结果、`required_tables` 和难度标签也不会进入生成 Prompt。阶段 8 为每次问数和慢 SQL 诊断写入一条 OpenTelemetry Trace，字段只有架构规定的检索、尝试、摘要、耗时和熔断标记；问题、SQL、Prompt、结果行、数据库密码和 API Key 不进入 Trace。默认不把 Span 发到收集器，只有 `OTEL_TRACES_EXPORTER=console` 时才打印。已跟踪文件用高置信规则扫描密钥。数据库容器只接入 internal 网络，API 同时保留出站网络；两边限制 2 CPU 和 2 GB，不挂载 Docker Socket、凭据目录或源码目录。Benchmark 并发为 1。

配置数据库并显式造数后，可以运行消融。未配置 `DEEPSEEK_API_KEY` 时，命令会在真正调用模型时失败：

```bash
uv run python -m app.evaluation.ablation
uv run python -m app.evaluation.external_data verify-bird --database-root /path/to/dev_databases
uv run python -m app.evaluation.external_data verify-tpcds
```

后两条命令只执行 Gold SQL 并写下独立报告，不会调用 DeepSeek。来源、许可证和重新生成步骤写在 `benchmarks/tpcds_derived/SOURCE.md` 与 `benchmarks/bird_complex/SOURCE.md`。

配置 `DEEPSEEK_API_KEY` 后可以提问或诊断：

```bash
uv run python -m app.agents.text_to_sql "按等级编号升序查询全部会员等级的名称和折扣率"
uv run python -m app.agents.slow_sql --sql "SELECT order_id FROM t_order WHERE user_id::text = '1'"
```

`POST /v1/text-to-sql` 接收 `question`、`database_id`、`execute` 和 `max_rows`。同一规范化错误连续出现 3 次会熔断，总模型调用不超过 4 次。`POST /v1/slow-sql/diagnose` 接收 `database_id`、`sql`、`run_analyze` 和 `rewrite`。`run_analyze` 为 false 时，执行时间和 Buffer 字段为 null。慢 SQL 不会作为问数成功后的默认步骤。

真实向量索引需要额外安装检索依赖，并在 12 表已经创建后执行：

```bash
uv sync --group retrieval
uv run python -m app.retrieval.index
```

```bash
cp .env.example .env
# 替换 .env 中的占位密码
uv sync --frozen --group dev
docker compose up --build --wait
curl --fail http://127.0.0.1:8000/health
uv run python -m app.db.seed
```

本地质量检查：

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -m "not integration"
INTEGRATION_TESTS=1 uv run pytest -m integration
```

容器内 API 通过服务名 `db` 连接数据库。宿主机上的集成测试使用 `.env` 中的 `POSTGRES_HOST=localhost` 和发布端口。不要把 `.env` 或真实密码提交到仓库。

## 文档

- [系统架构](docs/architecture.md)
- [Schema 与图拓扑设计](docs/schema-and-graph.md)
- [数据库沙箱与安全设计](docs/security.md)
- [Benchmark 与验收规范](docs/benchmark.md)
- [数据与接口契约](docs/data-contracts.md)
- [工程实施计划](docs/implementation-plan.md)
- [核心架构决策 ADR](docs/adr/0001-core-architecture-decisions.md)

## 实施顺序

1. 建立 Docker、PostgreSQL、pgvector 和测试框架；
2. 落地 12 表 DDL、确定性造数器和 10 条冒烟用例；
3. 实现 Schema Graph 与检索；
4. 打通 Text-to-SQL 生成、执行、自愈和 EX；
5. 实现慢 SQL 诊断与改写复验；
6. 扩展自建 132 条用例；
7. 接入 TPC-DS 派生与 BIRD，并按来源分开报告；
8. 接入 OpenTelemetry，扫描密钥，并收紧容器资源和网络策略。

首个工程里程碑是 10 条用例的端到端纵向闭环，而不是一次性生成全部评测数据。
