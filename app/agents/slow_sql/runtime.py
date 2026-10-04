"""组装慢 SQL 诊断的默认依赖。启动时不下载模型。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncConnection

from app.agents.slow_sql.plan import PlanSummary
from app.agents.slow_sql.workflow import SlowSqlServices
from app.config.settings import get_settings
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
) -> SlowSqlServices:
    """用调用方提供的模型构造诊断服务。connection 指向隔离库时不使用全局池。"""

    async def explain(sql: str, *, analyze: bool) -> PlanSummary | ExecutionError:
        return await explain_readonly(sql, analyze=analyze, connection=connection)

    async def execute(sql: str, *, max_rows: int) -> ExecutionSuccess | ExecutionError:
        return await execute_readonly(sql, max_rows=max_rows, connection=connection)

    return SlowSqlServices(model=model, explain=explain, execute=execute)


def get_default_services() -> SlowSqlServices:
    """返回进程内默认服务。缺少密钥时，只有真正改写才会失败。"""

    return build_slow_sql_services(_LazyDeepSeek())
