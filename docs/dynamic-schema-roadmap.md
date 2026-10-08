# 动态 Schema 产品化路线

本文档对应 `/goal 按建议的顺序推进` 的实施顺序与当前落地状态。

## 阶段 1 — SchemaSnapshot / SchemaDiff / Registry（已落地）

- `app/schema_registry/snapshot.py`：不可变快照与 `snapshot_fingerprint`
- `app/schema_registry/diff.py`：表增删改与外键边变化
- `app/schema_registry/registry.py`：进程内 staging / active 版本与 `ActivationAudit`
- `app/schema_registry/extract.py`：`fixed_ecommerce` 与 `live_public` 两种提取
- `app/db/catalog_loader.py`：问数运行时统一入口
- 单测：`tests/unit/test_schema_registry.py`

## 阶段 2 — 默认问数接入动态 Catalog（已落地）

| 变量 | 默认 | 含义 |
| --- | --- | --- |
| `TEXT_TO_SQL_CATALOG_MODE` | `fixed_ecommerce` | `live_public` 时从 PostgreSQL public 实时读表 |
| `SCHEMA_REGISTRY_AUTO_ACTIVATE` | `true` | sync / 运行时新 fingerprint 是否在门禁通过后自动切 active |

`app/agents/text_to_sql/runtime.py` 经 `load_catalog_for_runtime()` 加载目录。

## 阶段 3 — 版本化 Embedding + Graph（已落地）

- `schema_embedding` 主键含 `schema_version`（旧库自动迁移）
- `POST /v1/schema/sync?index=true` 或 `SCHEMA_REGISTRY_AUTO_INDEX=1` 重建该版本向量
- Graph 边集随 Registry active 版本切换

## 阶段 4 — Sync / Admin API（已落地核心）

- `POST /v1/schema/sync?index=true`：extract → **staging** → 可选索引 → **门禁** → 条件 activate
- `POST /v1/schema/activate?force=`：显式激活 staging 版本
- `GET /v1/schema/active`
- `GET /v1/schema/audit`：激活审计记录
- 待做：多 datasource、Registry 持久化

## 阶段 5 — Schema Mutation 回归集（部分）

- `tests/unit/test_schema_mutation.py`：增表 / 删表 / staging→activate
- 待做：集成级 canary、Text-to-SQL EX 回放

## 阶段 6 — 慢 SQL OptimizerContext（已落地）

- `app/agents/slow_sql/optimizer_context.py`：PG `reltuples` / 索引列 + active `SchemaSnapshot` → `RuleCatalog`
- `build_slow_sql_services_with_context()`：`app/evaluation/slow_sql.py` 与 API 路径可注入动态 catalog
- `app/agents/slow_sql/rules.py`：`diagnose_sql(..., catalog=)`
- 单测：`tests/unit/test_rule_catalog.py`

## 阶段 7 — 元数据驱动 autofix（已落地核心）

- `app/agents/slow_sql/autofix.py`：`SELECT *` 展开与大表 guard 使用 `OptimizerContext.table_columns` / `RuleCatalog.large_tables`；电商模板改写保留为 catalog 内表存在时的 fast path
- `workflow`：LLM 改写前先 `try_autofix_sql`
- 单测：`tests/unit/test_autofix_metadata.py`
- 待做：更多通用 AST 改写（非电商模板）

## 阶段 8 — staging → gate → activate（已落地核心）

- `app/schema_registry/gate.py`：`evaluate_activation_gate`
- `SCHEMA_REGISTRY_REQUIRE_EMBEDDINGS`：激活前要求该版本向量行数 > 0
- Sync 默认登记 staging；仅门禁通过且（无 active 或 `SCHEMA_REGISTRY_AUTO_ACTIVATE`）时自动 activate
- 单测：`tests/unit/test_schema_activation_gate.py`

## 阶段 9 — 隔离 / 审计（部分）

- `SchemaRegistry.activate(..., forced=)` 写入 `ActivationAudit`
- `GET /v1/schema/audit`
- 待做：多租户 datasource 隔离、持久化审计、强制激活策略
