"""构造问数 Prompt。Gold SQL 和评测标签不得进入这里。"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from app.agents.text_to_sql.contract import AnswerContract, format_answer_contract
from app.schemas.retrieval import ToolHit

PROMPT_VERSION = "text-to-sql-v1"
SYSTEM_PROMPT = (
    "你是 PostgreSQL 只读 SQL 生成器。只输出一条 SELECT 或 WITH ... SELECT，"
    "不要解释，不要写入数据，不要使用未给出的工具。"
)
_FENCE = re.compile(r"```(?:sql|postgresql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_sql(content: str) -> str:
    """从模型输出中取出 SQL。没有代码块时使用整段文本。"""

    match = _FENCE.search(content)
    body = match.group(1) if match else content
    return body.strip()


def render_generation_prompt(
    *,
    question: str,
    schema_context: str,
    tools: Sequence[ToolHit],
    contract: AnswerContract | None = None,
) -> str:
    """组装首轮上下文。Schema 文本由调用方保证不超过预算。"""

    return _render(
        question=question,
        schema_context=schema_context,
        tools=tools,
        contract=contract,
        repair=None,
    )


def render_repair_prompt(
    *,
    question: str,
    schema_context: str,
    tools: Sequence[ToolHit],
    previous_sql: str,
    error_category: str,
    error_message: str,
    contract: AnswerContract | None = None,
) -> str:
    """把结构化错误附到下一轮。不附带原始异常。"""

    return _render(
        question=question,
        schema_context=schema_context,
        tools=tools,
        contract=contract,
        repair=(previous_sql, error_category, error_message),
    )


def _render(
    *,
    question: str,
    schema_context: str,
    tools: Sequence[ToolHit],
    contract: AnswerContract | None,
    repair: tuple[str, str, str] | None,
) -> str:
    tool_lines = [
        json.dumps(
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for tool in tools
    ]
    sections = [f"问题：\n{question}"]
    if contract is not None:
        sections.append(format_answer_contract(contract))
    sections.extend(
        (
            f"可用表：\n{schema_context}",
            "已选择的工具定义：\n" + ("\n".join(tool_lines) if tool_lines else "无"),
        )
    )
    if repair is not None:
        previous_sql, category, message = repair
        sections.append(
            "\n".join(
                (
                    "上一次 SQL：",
                    previous_sql,
                    "结构化错误：",
                    f"category: {category}",
                    f"message: {message}",
                    "请修复为一条只读 SQL。",
                )
            )
        )
    return "\n\n".join(sections)
