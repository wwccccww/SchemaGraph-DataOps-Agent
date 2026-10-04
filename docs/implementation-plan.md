# 工程实施计划

## 1. 实施原则

先建立可运行的纵向闭环，再扩展用例数量和外部数据集。禁止在核心链路尚未跑通时一次性生成全部 212 条 Text-to-SQL 用例。

每个阶段必须具备：

- 可执行测试；
- 明确输入输出契约；
- 可回滚数据库状态；
- 不依赖未实现模块的伪造指标。

## 2. 建议目录

```text
app/
├── api/                    # FastAPI 路由与响应模型
├── agents/
│   ├── text_to_sql/       # LangGraph 问数工作流
│   └── slow_sql/          # LangGraph 慢 SQL 工作流
├── config/                # 环境配置，不包含 Secret
├── db/                    # SQLAlchemy、Catalog 与沙箱连接
├── evaluation/            # EX、运行器、报告生成
├── graph/                 # Schema Graph 构建与扩展
├── llm/                   # DeepSeek/OpenAI-compatible 网关
├── mcp/                   # 只读 MCP 工具
├── observability/         # OpenTelemetry
├── retrieval/             # BGE-M3 与 pgvector
├── sandbox/               # AST 门禁、执行器、Error Hash
└── schemas/               # Pydantic 契约

benchmarks/
├── custom_ecommerce/
├── tpcds_derived/
└── bird_complex/

tests/
├── unit/
├── integration/
├── security/
└── evaluation/
```

## 3. 交付阶段

### 阶段 0：工程基础

- Python 项目、依赖锁文件和代码质量工具；
- Docker Compose：API、PostgreSQL 16、pgvector；
- 环境变量模板；
- 数据库初始化和健康检查；
- CI 中的单元测试与集成测试入口。

退出条件：空 API、数据库和测试框架能在干净环境启动。

### 阶段 1：Schema 与数据

- 落地 12 表 DDL、注释和索引；
- 固定随机种子的 Faker 造数器；
- Catalog 元数据提取；
- 造数后 `ANALYZE`；
- 10 条经过人工审计的冒烟 Gold SQL。

退出条件：相同随机种子产生相同数据摘要，10 条 Gold SQL 均返回非空稳定结果。

### 阶段 2：Schema Graph

- 显式外键解析；
- Junction Table 标记；
- 1-Hop-per-Seed Junction 扩展；
- 受限最短路径兜底；
- 表数量和 token 预算；
- 图诊断和失败语义。

退出条件：单元测试覆盖三条 Junction 路径、长链补全、超深路径、预算不足和断图。

### 阶段 3：Schema-RAG 与 Tool-RAG

- BGE-M3 表级文档向量化；
- pgvector 索引；
- Junction Seed 屏蔽；
- Top-3～5 Schema 检索；
- 10 个 MCP 工具定义；
- Top-3 Tool-RAG。

退出条件：Junction Table 不出现在 Seed 结果中，图扩展仍可补全必需映射表。

### 阶段 4：Text-to-SQL 纵向闭环

- DeepSeek 模型网关；
- Prompt 构造；
- LangGraph 状态机；
- SQLGlot 语法与只读检查；
- PostgreSQL 沙箱执行；
- Error Hash、Recovery@3 和熔断；
- FastAPI 与 CLI。

退出条件：10 条冒烟用例可生成、执行和计算 EX，失败路径可稳定熔断。

### 阶段 5：慢 SQL

- 静态诊断规则；
- JSON 执行计划解析；
- 改写候选；
- 语义 EX；
- Planner、Time 和 Buffer 指标；
- 快照级用例隔离。

退出条件：至少覆盖全表扫描、索引失效、隐式转换和重复聚合四类用例。

### 阶段 6：自建完整评测

- 扩展为 50 Basic、50 Medium、32 Complex；
- 运行 A/B/C/D 四组消融；
- 生成逐条 JSON 和汇总报告；
- Target 与本次 Measured 并列保存，不覆盖目标字段，也不改写历史报告。

退出条件：132 条用例全部可执行且报告可追溯。

### 阶段 7：外部评测

- 固定 TPC-DS 工具版本和许可记录；
- 生成 SF=1 数据并适配 30 条查询；
- 固定 BIRD 版本并筛选 50 条复杂用例；
- 使用受限 SQLite Adapter 执行入选 BIRD 用例；
- 按来源独立生成报告。

退出条件：外部数据可由脚本重新获取或生成，且不与自建指标混合。

### 阶段 8：可观测性与加固

- OpenTelemetry Trace；
- Secret 扫描；
- 容器资源和网络策略；
- 安全测试与失败注入；
- README 实测结果更新。

## 4. 首个纵向切片

首个切片只使用 10 条用例：

- 3 条 Basic；
- 3 条 Medium；
- 4 条 Complex，其中至少两条依赖 Junction Table。

该切片必须包含一次成功执行、一次语法修复、一次数据库错误修复和一次连续同错熔断，以同时验证正常路径和失败路径。

## 5. Definition of Done

功能完成不等于文档中的目标数字达成。M2 完成必须满足：

- 212 条 Text-to-SQL 用例按来源独立运行；
- 50 条慢 SQL 用例隔离运行；
- 所有指标均由原始结果生成；
- 代码、Prompt、数据和模型版本可追溯；
- 安全门禁具备自动化负向测试；
- README 只展示实际跑出的 Measured，并保留运行条件；
- 干净环境可以根据文档重新启动和复现。
