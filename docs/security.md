# 数据库沙箱与安全设计

## 1. 威胁模型

系统执行的 SQL 由模型生成或由用户提交，必须默认视为不可信输入。需要防御：

- DDL、DML、写操作 CTE 和多语句注入；
- `nextval`、用户自定义函数和 Advisory Lock 等隐式副作用；
- `pg_sleep`、笛卡尔积和递归查询造成的资源耗尽；
- 超大结果集导致应用进程内存耗尽；
- 通过异常信息泄漏凭据或内部路径；
- 自愈状态机无限重试；
- Benchmark 用例之间的数据和索引污染。

安全边界采用纵深防御，SQLGlot 只负责快速拒绝，不被视为最终权限边界。

## 2. 防御层级

```text
请求大小与类型限制
  → SQLGlot 全 AST 只读检查
  → 单语句检查与函数策略
  → PostgreSQL 最小权限 Role
  → READ ONLY 事务
  → Statement / Lock / Idle Timeout
  → 容器 CPU、内存、网络限制
  → 最大结果行数
  → 无条件 ROLLBACK
```

## 3. 应用层 AST 门禁

解析器必须遍历整棵 AST，而不是只检查根节点。首期仅允许单条 `SELECT` 或只读 `WITH ... SELECT`，拒绝：

- `INSERT`、`UPDATE`、`DELETE`、`MERGE`
- `CREATE`、`ALTER`、`DROP`、`TRUNCATE`
- `COPY`、`CALL`、`DO`
- 写操作 CTE
- 多语句输入
- 未在配置允许列表中的函数

AST 检查失败时不得把 SQL 发送给数据库。解析失败默认拒绝，不能降级为字符串关键字检查后执行。

函数策略采用默认拒绝：

- 解析所有函数调用并解析其 Schema；
- 只允许配置中固定版本的 `pg_catalog` 只读函数与聚合函数；
- 禁止 `pg_sleep`、Advisory Lock、`set_config`、序列函数和未知函数；
- `public` 及业务 Schema 中的用户自定义函数默认禁止；
- PostgreSQL 扩展使用允许列表，沙箱镜像不安装文件、网络或跨库访问扩展。

数据库只读事务不能阻止所有外部副作用，因此函数允许列表、容器网络隔离和扩展控制缺一不可。

## 4. PostgreSQL 最小权限 Role

密码由部署环境中的 `SANDBOX_DB_PASSWORD` 注入，禁止出现在源码、镜像层、日志和文档示例中。

沙箱数据库应为独立数据库。初始化原则如下：

```sql
CREATE ROLE sandbox_readonly LOGIN;

GRANT CONNECT ON DATABASE text2sql_db TO sandbox_readonly;
GRANT USAGE ON SCHEMA public TO sandbox_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sandbox_readonly;

REVOKE TEMP ON DATABASE text2sql_db FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

ALTER ROLE sandbox_readonly SET default_transaction_read_only = on;
ALTER ROLE sandbox_readonly SET statement_timeout = '5s';
ALTER ROLE sandbox_readonly SET lock_timeout = '1s';
ALTER ROLE sandbox_readonly
    SET idle_in_transaction_session_timeout = '2s';
```

部署脚本使用管理连接从 Secret 为角色设置密码。`sandbox_readonly` 不加入任何高权限角色，也不授予 `CREATE`、`TEMP`、序列写入或 Role 切换能力。

如果运行时会创建新表，所有者还需配置受控的 Default Privileges；不能假设 `GRANT SELECT ON ALL TABLES` 会自动覆盖未来对象。

## 5. 事务执行协议

以下是同步 SQLAlchemy 伪代码；异步实现必须保持同样的事务语义。

```python
def execute_in_sandbox(
    engine,
    sql,
    *,
    max_rows=1_000,
    max_result_bytes=8 * 1024 * 1024,
):
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
            conn.exec_driver_sql("SET LOCAL lock_timeout = '1s'")
            conn.exec_driver_sql(
                "SET LOCAL idle_in_transaction_session_timeout = '2s'"
            )

            streaming_conn = conn.execution_options(
                stream_results=True,
                max_row_buffer=100,
            )
            result = streaming_conn.execute(text(sql))

            rows = []
            result_bytes = 0
            while batch := result.fetchmany(100):
                rows.extend(batch)
                result_bytes += estimate_serialized_size(batch)
                if len(rows) > max_rows:
                    raise ResultLimitExceeded(max_rows)
                if result_bytes > max_result_bytes:
                    raise ResultSizeExceeded(max_result_bytes)

            return ResultSet(columns=list(result.keys()), rows=rows)
        finally:
            tx.rollback()
```

关键要求：

- `SET TRANSACTION READ ONLY` 必须是事务中的首批指令；
- 无论成功、失败、超限或取消都执行回滚；
- PostgreSQL 驱动必须经集成测试确认启用服务端游标或真正的流式读取，不能只在已完整缓冲的结果上调用 `fetchmany`；
- `max_rows` 与 `max_result_bytes` 同时限制应用内存，计算本身仍由 `statement_timeout` 限制；
- 不拼接用户可控的超时、Role、Schema 或 SQL 片段；
- 数据库连接池归还连接前必须完成事务清理。

## 6. EXPLAIN 安全

`EXPLAIN` 不天然等于安全：

```sql
EXPLAIN (ANALYZE) DELETE FROM t_order;
```

会真实执行写操作。因此：

- `EXPLAIN` 与 `EXPLAIN ANALYZE` 使用相同 AST 门禁；
- `ANALYZE=true` 只允许通过门禁的单条只读查询；
- 仍在只读事务和只读 Role 中运行；
- 必须设置 Statement Timeout；
- 结果只返回必要的计划字段，不返回未经限制的原始对象。

## 7. 结构化错误与 Error Hash

错误对象至少包含：

```json
{
  "category": "undefined_column",
  "sqlstate": "42703",
  "exception_type": "UndefinedColumnError",
  "normalized_message": "column <identifier> does not exist",
  "retryable": true
}
```

规范化时移除：

- 行号和字符位置；
- 自动生成的临时对象名；
- UUID、具体参数值和内存地址；
- 凭据、连接串和文件路径。

哈希输入：

```text
sqlstate | exception_type | normalized_message
```

使用稳定摘要算法生成 Error Hash。同一哈希**连续**出现 3 次时触发熔断；任意一次错误类型变化会重置连续计数，但仍受最大总迭代数限制。

错误回传模型时只提供修复所需的最小内容，禁止回传数据库密码、连接地址或完整服务端堆栈。

## 8. 容器隔离

沙箱默认配置：

```text
PostgreSQL 16
CPU: 2
Memory: 2 GB
Concurrency: 1（Benchmark）
Network: 默认禁止不必要的出站访问
```

数据库执行容器不能挂载 Docker Socket、宿主凭据目录或源码写目录。API 容器和数据库管理角色分离；模型执行链只能获得只读连接。

## 9. Benchmark 隔离

评测写操作由独立 Harness 管理角色执行，不能复用 Agent 的只读账号。

涉及删除或创建索引的慢 SQL 用例必须：

1. 从已知快照创建隔离数据库；
2. 应用该用例专属的索引前置条件；
3. 执行 `ANALYZE`；
4. 完成原 SQL 和候选 SQL 测量；
5. 丢弃实例或恢复快照。

不能依赖测试结束时的“尽力重建索引”，否则中途失败可能污染后续用例。

### 9.1 BIRD 原生 SQLite

BIRD 不复用 PostgreSQL 沙箱。入选的原生 SQLite 数据库在独立受限子进程中执行，并要求：

- 使用只读 URI 打开数据库，固定已校验的数据文件摘要；
- 通过 SQLite Authorizer 拒绝写入、`ATTACH`、危险 PRAGMA 和扩展加载；
- 使用 Progress Handler、进程超时和内存限制中止高消耗查询；
- 禁止文件系统写权限和网络访问；
- Gold SQL 与 Agent SQL 使用同一执行器，但 Gold 结果不暴露给 Agent。

首期 BIRD 只接入满足该隔离协议的 SQLite 用例；其他引擎必须先实现等价的只读 Adapter 才能纳入。

## 10. 明确不承诺的能力

首期沙箱不是通用恶意 SQL 执行平台，不承诺抵御 PostgreSQL 或容器运行时的未知漏洞。生产部署还需要：

- 镜像与依赖漏洞扫描；
- 网络策略和 Secret Manager；
- 审计日志与异常告警；
- API 身份认证、授权和限流；
- 独立数据库实例或更强的进程级隔离；
- 定期轮换数据库凭据。
