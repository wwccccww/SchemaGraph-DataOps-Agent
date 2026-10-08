"""组装慢 SQL 诊断的默认依赖。启动时不下载模型。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncConnection

from app.agents.slow_sql.optimizer_context import OptimizerContext, load_optimizer_context
from app.agents.slow_sql.plan import PlanSummary
from app.agents.slow_sql.rule_catalog import DEFAULT_RULE_CATALOG, RuleCatalog
from app.agents.slow_sql.workflow import SlowSqlServices
from app.config.settings import get_settings
from app.db.catalog_loader import get_schema_registry
from app.llm.gateway import ChatModel, DeepSeekGateway
from app.sandbox.errors import ExecutionError
from app.sandbox.execute import ExecutionSuccess, execute_readonly
from app.sandbox.explain import explain_readonly


class _LazyDeepSeek:
    """第一次改写时才读取密钥并创建网关。"""

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float,
    ) -> str:
        settings = get_settings()
        gateway = DeepSeekGateway(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        )
        return await gateway.complete(messages, temperature=temperature)


def build_slow_sql_services(
    model: ChatModel,
    *,
    connection: AsyncConnection | None = None,
    rule_catalog: RuleCatalog | None = None,
    optimizer_context: OptimizerContext | None = None,
) -> SlowSqlServices:
    """用调用方提供的模型构造诊断服务。connection 指向隔离库时不使用全局池。"""

    async def explain(sql: str, *, analyze: bool) -> PlanSummary | ExecutionError:
        return await explain_readonly(sql, analyze=analyze, connection=connection)

    async def execute(sql: str, *, max_rows: int) -> ExecutionSuccess | ExecutionError:
        return await execute_readonly(sql, max_rows=max_rows, connection=connection)

    return SlowSqlServices(
        model=model,
        explain=explain,
        execute=execute,
        rule_catalog=rule_catalog,
        optimizer_context=optimizer_context,
    )


async def build_slow_sql_services_with_context(
    model: ChatModel,
    *,
    connection: AsyncConnection,
) -> SlowSqlServices:
    """从 Registry active 快照与 PG 统计加载 RuleCatalog。"""

    settings = get_settings()
    database_id = (
        settings.postgres_db if settings.text_to_sql_catalog_mode == "live_public" else "ecommerce"
    )
    snapshot = get_schema_registry().active_snapshot(database_id)
    context = await load_optimizer_context(connection, snapshot)
    return build_slow_sql_services(
        model,
        connection=connection,
        rule_catalog=context.catalog,
        optimizer_context=context,
    )


def get_default_services() -> SlowSqlServices:
    """返回进程内默认服务。缺少密钥时，只有真正改写才会失败。"""

    return build_slow_sql_services(_LazyDeepSeek())
