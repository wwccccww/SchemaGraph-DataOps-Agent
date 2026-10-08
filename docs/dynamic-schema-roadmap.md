# 动态 Schema 产品化路线

本文档对应 `/goal 按建议的顺序推进` 的实施顺序与当前落地状态。

## 阶段 1 — SchemaSnapshot / SchemaDiff / Registry（已落地）

- `app/schema_registry/snapshot.py`：不可变快照与 `snapshot_fingerprint`
- `app/schema_registry/diff.py`：表增删改与外键边变化
- `app/schema_registry/registry.py`：进程内 staging / active 版本
- `app/schema_registry/extract.py`：`fixed_ecommerce` 与 `live_public` 两种提取
- `app/db/catalog_loader.py`：问数运行时统一入口
- 单测：`tests/unit/test_schema_registry.py`

## 阶段 2 — 默认问数接入动态 Catalog（已落地）

环境变量：

| 变量 | 默认 | 含义 |
| --- | --- | --- |
| `TEXT_TO_SQL_CATALOG_MODE` | `fixed_ecommerce` | `live_public` 时从 PostgreSQL public 实时读表 |
| `SCHEMA_REGISTRY_AUTO_ACTIVATE` | `true` | 新 fingerprint 是否自动切 active |

`app/agents/text_to_sql/runtime.py` 经 `load_catalog_for_runtime()` 加载目录，不再硬编码只走 12 表 loader（在 `live_public` 模式下）。

`live_public` 会排除 `schema_embedding`、`tool_embedding` 等系统表。

## 阶段 3 — 版本化 Embedding + Graph（已落地）

- `schema_embedding` 主键含 `schema_version`（旧库自动迁移）
- `upsert_schema_embeddings(..., schema_version=)` 与检索按 active fingerprint 过滤
- `POST /v1/schema/sync?index=true` 或 `SCHEMA_REGISTRY_AUTO_INDEX=1` 重建该版本向量
- Graph 边集随 `SchemaSnapshot` / Registry active 版本切换（`load_catalog_for_runtime`）

## 阶段 4 — Sync / Admin API（部分落地）

- `POST /v1/schema/sync?index=true`
- `POST /v1/schema/activate`（body: `fingerprint`）
- `GET /v1/schema/active`
- 待做：多 datasource、持久化 Registry、staging→gate 自动激活

## 阶段 5 — Schema Mutation 回归集（起步）

- `tests/unit/test_schema_mutation.py`：增表 / 删表 / Registry staging→activate
- 待做：集成级 canary、Text-to-SQL EX 回放

## 阶段 6–9 — 慢 SQL OptimizerContext、元数据 autofix、门禁激活、多租户（待做）

见产品方案讨论；慢 SQL 仍绑定电商静态规则，动态 Schema 下需单独演进。
