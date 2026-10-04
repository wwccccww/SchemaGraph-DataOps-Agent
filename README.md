# 🕸️ Enterprise Text-to-SQL & Slow Query Diagnosis Agent Platform

> **面向复杂 Join 场景的企业级 Text-to-SQL 与慢查询诊断 Agent 平台**


---

## 📌 项目背景

针对企业级 **7~12 表复杂 Join** 场景下 Text-to-SQL 准确率低、Schema 上下文过长及 SQL 性能不可控的问题，设计并实现基于 **Agentic Workflow** 的智能问数与慢查询诊断平台。

项目基于企业级 Schema 与真实分析需求，自建了 **132 条复杂数仓问数 Benchmark** 及 **50 条生产级慢 SQL 优化测试集** 进行离线评测与闭环验证。

---

## ✨ 核心技术亮点

### 1. 🕸️ 外键图拓扑扩展 (Schema Graph)
* **解决 Join 链路断裂**：针对跨 7~12 张表取数时“传统向量 RAG 无法召回无语义缩写中间表”的痛点，提取 DDL 外键约束与字段依赖构建外键图拓扑。
* **1-Hop 路径扩展**：采用 **“种子表语义召回 + 1-Hop 图拓扑路径扩展”** 算法，自动补全跨表 Join 链条。
* **上下文极简压缩**：将 Schema 上下文 Token 平均从 **12k 精简压缩至 3.5k (压缩 70%)**。

### 2. 🔍 慢查询诊断与自动改写 Agent
* **闭环诊断架构**：构建具备“**感知-诊断-改写-验证**”闭环的慢查询诊断 Agent（非静态脚本）。
* **静态 AST + 物理探查**：结合 `sqlglot` 静态 AST 结构化解析与 Docker 沙箱物理 `EXPLAIN` 探查，动态识别全表扫描、隐式类型转换及索引失效等性能瓶颈。
* **二次验证与 Cost 骤降**：驱动 LLM 结合优化规则集推理并自动改写 SQL，在沙箱二次验证物理 Cost 平均降低 **68%**。

### 3. 🔌 MCP 动态热插拔与 Tool-RAG 工具路由
* **工具动态热插拔**：针对 MySQL、ClickHouse 与 DolphinScheduler 等异构工具新增/变更时需改码重启的痛点，基于 **MCP (Model Context Protocol) 协议** 实现工具的运行时动态热插拔 (Hot-Plugging)。
* **Tool-RAG 路由防膨胀**：针对多工具挂载导致 Prompt 膨胀问题，引入 Tool-RAG 机制，利用 `pgvector` 动态注入 **Top-3** 相关工具描述，将工具上下文 Token 降低 **70%**。

### 4. 🛡️ 沙箱熔断与副作用隔离评测 (Runtime & Eval Harness)
* ** Volume Snapshot 隔离**：基于数据库容器快照恢复 (Volume Snapshot) 构建离线评测套件，隔离写/改操作侧效应。
* **Error Hash 幂等熔断**：引入运行时 Error Hash 幂等熔断机制，针对 Agent 死循环报错连续 3 次拦截并中断，避免无效重试耗尽 Token（**API Token 浪费减少 48%**）。
* **极速 CI 回归**：支撑 **3 分钟** CI/CD 自动化回归。

---

## 📊 核心量化成果

| 评估维度 | 测试集基数 | 核心指标与成果 |
| :--- | :--- | :--- |
| **问数执行准确率 (EX)** | 132 条复杂数仓 Benchmark | **38% (单轮 Zero-Shot) 提升至 83%** |
| **慢 SQL 诊断改写** | 50 条生产级慢 SQL | **Pass@1 达到 72%，Pass@3 升至 86%**<br>*(物理 Cost 平均降低 68%)* |
| **算力与 Token 控制** | Runtime Harness | **死循环任务 API Token 浪潮减少 48%** |
| **自动化回归效率** | Eval Harness | **规则变更回归耗时缩短至 3 分钟** |

---

## 🏗️ 系统架构设计

```text
                             [ 用户 Query / 慢 SQL 请求 ]
                                          │
                                          ▼
                      ┌──────────────────────────────────────┐
                      │    FastAPI + LangGraph Gateway       │
                      └──────────────────┬───────────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
      【 智能问数 Agent Pipeline 】                【 慢 SQL 诊断 Agent Pipeline 】
                   │                                           │
 1. 向量召回 (pgvector Top-K 种子表)                          1. sqlglot 静态 AST 结构化解析
                   │                                           │
 2. 1-Hop 图拓扑路径扩展 (补全无语义中间表)                   2. Docker 沙箱物理 EXPLAIN 探查
                   │ (12k -> 3.5k Token)                       │ (感知全表扫描/索引失效/隐式转换)
 3. MCP Tool-RAG 动态注入 (Top-3 工具)                        │
                   │                                3. 规则集推理 + LLM 自动改写 SQL
 4. LLM 生成 SQL + Error Hash 幂等熔断                        │
                   │                                4. 沙箱二次验证 (Cost 降低 68%)
                   └─────────────────────┬─────────────────────┘
                                         │
                                         ▼
                   ┌──────────────────────────────────────────┐
                   │    Docker 沙箱 (Volume Snapshot 隔离)    │
                   └──────────────────────────────────────────┘
