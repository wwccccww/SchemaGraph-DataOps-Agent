# 动态 Schema 九阶段验证清单

在仓库根目录执行（需本地 PostgreSQL + `.env`）：

```bash
# 阶段 1–3、8
python3 -m pytest tests/unit/test_schema_registry.py tests/unit/test_schema_mutation.py \
  tests/unit/test_schema_activation_gate.py tests/unit/test_schema_embedding_version.py -q

# 阶段 2（默认 live_public）
python3 -m pytest tests/unit/test_default_live_public_catalog.py -q

# 阶段 4–5、9（集成）
python3 -m pytest tests/integration/test_schema_registry_live.py \
  tests/integration/test_schema_registry_persistence.py \
  tests/integration/test_schema_mutation_canary.py \
  tests/integration/test_schema_mutation_live_agent.py -q

# 阶段 6–7
python3 -m pytest tests/unit/test_rule_catalog.py tests/unit/test_autofix_metadata.py \
  tests/unit/test_slow_sql_workflow.py -q

# 租户 / API
python3 -m pytest tests/unit/test_schema_tenant.py tests/unit/test_schema_tenant_api.py -q
```

Admin API（进程启动后）：

- `POST /v1/schema/sync?index=true`
- `GET /v1/schema/active`
- `POST /v1/schema/activate`
- `GET /v1/schema/audit`

环境变量见 `.env.example` 与 `docs/dynamic-schema-roadmap.md`。
