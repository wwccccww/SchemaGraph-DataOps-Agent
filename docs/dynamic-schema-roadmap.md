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

## 阶段 3 — 版本化 Embedding + Graph（待做）

- `schema_embedding` 主键增加 `schema_version`
- 按 fingerprint 增量 upsert / tombstone
- Graph 边集按 version 缓存

## 阶段 4 — Sync / Admin API（最小接口已落地）

- `POST /v1/schema/sync`：提取 Catalog、登记 Registry、返回 diff 摘要
- `GET /v1/schema/active`：当前 active fingerprint
- 待做：多 datasource、`/activate` 显式切换、持久化 Registry

## 阶段 5 — Schema Mutation 回归集（待做）

- 增删表、改列、改 FK、改索引的自动化 canary

## 阶段 6–9 — 慢 SQL OptimizerContext、元数据 autofix、门禁激活、多租户（待做）

见产品方案讨论；慢 SQL 仍绑定电商静态规则，动态 Schema 下需单独演进。
