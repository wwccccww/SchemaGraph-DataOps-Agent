# 数据与接口契约

## 1. 约定

- 所有外部时间使用带时区 ISO 8601 UTC 字符串；
- 所有 ID 在 JSON 中使用字符串，避免 JavaScript 丢失 BIGINT 精度；
- SQL 文本只在受保护字段中传输，不写入普通业务日志；
- 契约使用 Pydantic v2 和 JSON Schema 生成；
- 增加字段应保持向后兼容，删除或改变语义必须提升契约版本。

## 2. API

### 2.1 Text-to-SQL

`POST /v1/text-to-sql`

```json
{
  "question": "统计上个月华东大区VIP3以上用户……",
  "database_id": "ecommerce",
  "execute": true,
  "max_rows": 1000
}
```

成功响应：

```json
{
  "request_id": "req_...",
  "status": "succeeded",
  "sql": "SELECT ...",
  "columns": ["merchant_name", "total_orders", "net_pay_amount"],
  "rows": [["自营美妆一店", 120, "35200.1200"]],
  "schema_context": {
    "seed_tables": [
      "t_user_level",
      "t_region",
      "t_coupon",
      "t_category",
      "t_merchant"
    ],
    "expanded_tables": [
      "t_user",
      "t_user_region_map",
      "t_order",
      "t_order_coupon_rel",
      "t_order_detail",
      "t_product"
    ],
    "token_count": 3180,
    "truncated": false
  },
  "attempts": 2
}
```

失败响应：

```json
{
  "request_id": "req_...",
  "status": "failed",
  "error": {
    "category": "schema_path_budget_exceeded",
    "message": "必需路径超过Schema上下文预算",
    "retryable": false
  }
}
```

### 2.2 慢 SQL 诊断

`POST /v1/slow-sql/diagnose`

```json
{
  "database_id": "ecommerce",
  "sql": "SELECT ...",
  "run_analyze": true,
  "rewrite": true
}
```

响应至少包含：

```json
{
  "request_id": "req_...",
  "status": "succeeded",
  "findings": [
    {
      "rule_id": "implicit-cast-on-index-column",
      "severity": "high",
      "message": "索引列发生隐式类型转换"
    }
  ],
  "original_plan": {
    "total_cost": 12345.67,
    "execution_time_ms": 820.2,
    "shared_hit_blocks": 1200,
    "shared_read_blocks": 400
  },
  "candidate": {
    "sql": "SELECT ...",
    "equivalent": true,
    "planner_cost_drop": 0.68,
    "execution_time_drop": 0.72
  }
}
```

`run_analyze=false` 时，实际执行时间和 Buffer 字段必须为 `null`，不能用 0 代替未知。

## 3. BenchmarkCase

```yaml
contract_version: "1.0"
id: custom_complex_001
source: custom
source_version: ecommerce-v1
database_id: ecommerce
difficulty: complex
dialect: postgres
question: 统计上个月华东大区VIP3以上用户……
gold_sql: |
  WITH qualified_orders AS (...)
required_tables:
  - t_user
  - t_region
  - t_order
required_junctions:
  - t_user_region_map
  - t_order_coupon_rel
order_sensitive: false
numeric_tolerance: null
expected_columns:
  - merchant_name
  - total_orders
  - net_pay_amount
anchor_date: "2026-10-01"
tags:
  - long-join
  - aggregation
  - junction-recall
```

规则：

- `source` 枚举为 `custom`、`tpcds-derived`、`bird`；
- `gold_sql` 只允许评测进程读取；
- `required_tables` 是评测标签，不能传给生成 Agent；
- `order_sensitive=true` 必须由自然语言问题明确要求排序；Gold SQL 自身的 `ORDER BY` 不能单独证明顺序属于答案语义；
- `numeric_tolerance` 默认为 `null`，表示精确数值比较；仅对明确允许误差的用例设置绝对或相对容差；
- 外部数据必须附带来源版本和许可证记录。

## 4. Schema 元数据

### 4.1 TableDocument

```json
{
  "database_id": "ecommerce",
  "schema_name": "public",
  "table_name": "t_order",
  "table_comment": "交易订单主事实表",
  "columns": [
    {
      "name": "order_id",
      "data_type": "bigint",
      "nullable": false,
      "comment": "订单流水号主键"
    }
  ],
  "is_junction": false,
  "content_hash": "sha256:...",
  "embedding_model": "BAAI/bge-m3",
  "embedding_version": "<pinned-version>"
}
```

### 4.2 SchemaEdge

```json
{
  "source_table": "t_order_coupon_rel",
  "source_columns": ["order_id"],
  "target_table": "t_order",
  "target_columns": ["order_id"],
  "constraint_name": "t_order_coupon_rel_order_id_fkey",
  "weight": 1.0,
  "inferred": false,
  "confidence": 1.0
}
```

### 4.3 GraphExpansionResult

```json
{
  "seed_tables": ["t_order", "t_coupon"],
  "expanded_tables": ["t_order_coupon_rel"],
  "edges": [],
  "connected": true,
  "context_tokens": 920,
  "context_truncated": false,
  "warnings": []
}
```

`expanded_tables` 只包含图算法新增的表，不重复 Seed。

## 5. 沙箱结果

### 5.1 ExecutionResult

```json
{
  "status": "succeeded",
  "columns": [
    {"name": "total_orders", "database_type": "int8"}
  ],
  "rows": [[120]],
  "row_count": 1,
  "truncated": false,
  "execution_time_ms": 12.4
}
```

### 5.2 ExecutionError

```json
{
  "status": "failed",
  "category": "undefined_column",
  "sqlstate": "42703",
  "exception_type": "UndefinedColumnError",
  "normalized_message": "column <identifier> does not exist",
  "error_hash": "sha256:...",
  "retryable": true
}
```

外部 API 默认不暴露原始数据库异常；原始错误只在受保护的内部诊断存储中保留。

## 6. Agent 状态

```json
{
  "request_id": "req_...",
  "request_type": "text_to_sql",
  "question": "...",
  "database_id": "ecommerce",
  "selected_tools": [],
  "seed_tables": [],
  "expanded_tables": [],
  "schema_context": "",
  "generated_sql": null,
  "attempt": 0,
  "consecutive_error_hash": null,
  "consecutive_error_count": 0,
  "total_error_count": 0,
  "execution_result": null,
  "final_error": null
}
```

持久化 Agent 状态时必须对问题和 SQL 应用数据保留策略；默认 Trace 不保存完整状态。

## 7. MCP 工具契约

所有工具具有统一错误外壳：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "TIMEOUT",
    "message": "工具执行超时",
    "retryable": true
  }
}
```

### 7.1 `explain_sql_cost`

输入：

```json
{
  "type": "object",
  "properties": {
    "sql": {"type": "string", "minLength": 1},
    "analyze": {"type": "boolean", "default": false}
  },
  "required": ["sql"],
  "additionalProperties": false
}
```

输出数据：

```json
{
  "is_read_only": true,
  "planner_cost": 1234.5,
  "execution_time_ms": null,
  "shared_hit_blocks": null,
  "shared_read_blocks": null
}
```

当 `analyze=false` 时，运行期字段为 `null`。JSON Schema 使用 `["number", "null"]` 等联合类型表达可空值，不使用非标准 `nullable`。

### 7.2 工具最小输入

| 工具 | 必需输入 | 返回数据 |
| --- | --- | --- |
| `get_table_schema` | `tables: string[]` | `ddl_list` |
| `get_column_enums` | `table`, `column`, `limit` | `distinct_values`, `truncated` |
| `get_foreign_keys` | `table` | `fk_relations` |
| `get_table_row_count` | `table`, `exact=false` | `row_count`, `estimated` |
| `get_partition_keys` | `table` | `partition_columns` |
| `explain_sql_cost` | `sql`, `analyze=false` | 计划与运行指标 |
| `check_sql_syntax` | `sql` | `is_valid`, `error` |
| `get_etl_status` | `table` | `last_sync_time`, `status` |
| `get_data_owner` | `table` | `owner_id` |
| `get_metric_definition` | `metric_name` | `formula`, `dimensions` |

`get_data_owner` 默认返回内部主体 ID，不直接向模型暴露个人邮箱。

## 8. 评测报告

每条结果必须保留：

```json
{
  "case_id": "custom_complex_001",
  "variant": "schema_graph",
  "passed": true,
  "attempts": 1,
  "seed_tables": [],
  "expanded_tables": [],
  "junction_recall": 1.0,
  "schema_tokens": 3180,
  "latency_ms": 1420,
  "error_category": null
}
```

汇总报告必须可追溯到逐条结果，禁止只保存一个不可审计的平均值。
