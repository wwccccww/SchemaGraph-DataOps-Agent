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

## 阶段 4 — Sync / Admin API（已落地）

- `POST /v1/schema/sync?index=true`：extract → staging → 可选索引 → 门禁 → 条件 activate
- `POST /v1/schema/activate?force=`、`GET /v1/schema/active`、`GET /v1/schema/audit`
- **持久化（可选）**：`SCHEMA_REGISTRY_PERSIST=1` → `app/schema_registry/persistence.py` + `app/db/registry_sync.py`
- 待做：多 datasource

## 阶段 5 — Schema Mutation 回归集（已落地 canary）

- `tests/unit/test_schema_mutation.py`：增表 / 删表 / staging→activate
- `benchmarks/schema_mutation/canary.yaml` + `app/evaluation/schema_mutation.py`（Gold EX 回放）
- `tests/integration/test_schema_mutation_canary.py`：增表 + `live_public` sync + baseline/smoke 子集 EX 仍通过
- 待做：完整 Text-to-SQL Agent EX 回放（需 LLM）、删表 canary

## 阶段 6 — 慢 SQL OptimizerContext（已落地）

- `app/agents/slow_sql/optimizer_context.py`：PG 统计 / 索引列 + active 快照 → `RuleCatalog`
- `build_slow_sql_services_with_context()`、`diagnose_sql(..., catalog=)`
- 单测：`tests/unit/test_rule_catalog.py`

## 阶段 7 — 元数据驱动 autofix（已落地）

- `autofix.py`：`SELECT *`、大表 guard、**通用索引列 cast/算术**（`RuleCatalog.indexed_columns`）
- 电商模板 fast path 保留
- 单测：`tests/unit/test_autofix_metadata.py`

## 阶段 8 — staging → gate → activate（已落地）

- `gate.py`、`SCHEMA_REGISTRY_REQUIRE_EMBEDDINGS`、sync/activate 门禁
- 单测：`tests/unit/test_schema_activation_gate.py`

## 阶段 9 — 隔离 / 审计（部分）

- 进程内 `ActivationAudit` + `GET /v1/schema/audit`
- 持久化审计表 `schema_registry_activation_audit`（`SCHEMA_REGISTRY_PERSIST=1`）
- `tests/integration/test_schema_registry_persistence.py`
- 待做：多租户 datasource 隔离、生产强制激活策略
