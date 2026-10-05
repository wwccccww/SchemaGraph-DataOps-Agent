"""构造问数 Prompt。Gold SQL 和评测标签不得进入这里。"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from app.agents.text_to_sql.contract import AnswerContract, format_answer_contract
from app.schemas.retrieval import ToolHit

PROMPT_VERSION = "text-to-sql-v3"
GENERIC_PROMPT_VERSION = "text-to-sql-generic-v10"
SYSTEM_PROMPT = (
    "你是 PostgreSQL 只读 SQL 生成器。只输出一条 SELECT 或 WITH ... SELECT，"
    "不要解释，不要写入数据，不要使用未给出的工具。"
)
_GENERIC_SHAPE = (
    "问句中的分组维度必须出现在最终 SELECT 和 GROUP BY 中，不能只写在 WHERE。"
    "年份若既是过滤又是汇总轴，也要投影出来。度量要聚合，排序要求要写 ORDER BY。"
    "若问句列举多项属性或 characteristics，最终 SELECT 应逐条回答，并为每列写清晰的 AS 别名。"
    "charter school、grades served、SAT performance level 等语义优先从 schools/satscores 等实体表取字段，"
    "SAT performance level 用 AvgScrRead+AvgScrMath+AvgScrWrite 总和（不要除以 3）做 CASE 分档，不要只输出原始分列。"
    "California schools：县名/学区/学校名与 free meal、NSLP、Enrollment 等优先用 frpm 带空格列名；"
    "Magnet、GSserved、Charter 等在 schools；问句同时涉及 magnet/grade span 与 NSLP/Provision 时必须 JOIN frpm 与 schools。"
    "SQLite 输出列别名若含空格或括号，必须与冻结契约一致并使用双引号。"
    "窗口函数（RANK/DENSE_RANK/ROW_NUMBER）写在最终 SELECT 中，不要在同一层再对窗口列做 GROUP BY；"
    "可先 CTE 算基础列，再在外层 SELECT 窗口函数并 ORDER BY。"
)
_POSTGRES_JOIN = (
    " 事实表与维表优先用 *_sk 连接键；先按业务键聚合再 JOIN，避免无关桥表造成笛卡尔积。"
)
SQLITE_SYSTEM_PROMPT = (
    "你是 SQLite 只读 SQL 生成器。只输出一条 SELECT 或 WITH ... SELECT，"
    "不要解释，不要写入数据，不要使用未给出的工具。"
    "表名和列名必须与可用表中的写法一致；包含空格、括号或百分号时使用双引号。"
    "可以使用 julianday、strftime、group_concat 这些 SQLite 只读函数。"
)


def system_prompt_for(*, dialect: str, profile: str) -> str:
    """电商问数继续使用原来的 PostgreSQL 系统提示。"""

    if profile == "ecommerce":
        return SYSTEM_PROMPT
    if dialect == "sqlite":
        return f"{SQLITE_SYSTEM_PROMPT}{_GENERIC_SHAPE}"
    return f"{SYSTEM_PROMPT}{_GENERIC_SHAPE}{_POSTGRES_JOIN}"


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
    plan: str | None = None,
    output_shape: str | None = None,
) -> str:
    """组装首轮上下文。Schema 文本由调用方保证不超过预算。"""

    return _render(
        question=question,
        schema_context=schema_context,
        tools=tools,
        contract=contract,
        plan=plan,
        output_shape=output_shape,
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
    plan: str | None = None,
    output_shape: str | None = None,
) -> str:
    """把结构化错误附到下一轮。不附带原始异常。"""

    return _render(
        question=question,
        schema_context=schema_context,
        tools=tools,
        contract=contract,
        plan=plan,
        output_shape=output_shape,
        repair=(previous_sql, error_category, error_message),
    )


def _render(
    *,
    question: str,
    schema_context: str,
    tools: Sequence[ToolHit],
    contract: AnswerContract | None,
    plan: str | None,
    output_shape: str | None,
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
    if plan:
        sections.append(plan)
    if output_shape:
        sections.append(output_shape)
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
