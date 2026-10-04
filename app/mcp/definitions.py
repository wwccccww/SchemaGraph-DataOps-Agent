"""10 个只读 MCP 工具定义。本阶段只提供契约和检索文本，不执行工具。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.retrieval.text import tool_document_text

_IDENTIFIER = r"^[A-Za-z_][A-Za-z0-9_]{0,62}$"
_TABLE = {"type": "string", "minLength": 1, "maxLength": 63, "pattern": _IDENTIFIER}

TOOL_ERROR_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ok", "data", "error"],
    "properties": {
        "ok": {"type": "boolean"},
        "data": {"type": "null"},
        "error": {
            "type": "object",
            "additionalProperties": False,
            "required": ["code", "message", "retryable"],
            "properties": {
                "code": {"type": "string", "minLength": 1},
                "message": {"type": "string", "minLength": 1},
                "retryable": {"type": "boolean"},
            },
        },
    },
}


class ToolDefinition(BaseModel):
    """一条可被 Tool-RAG 召回的工具定义。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z_][a-z0-9_]{0,62}$")
    description: str = Field(min_length=1)
    input_schema: dict[str, object]
    output_schema: dict[str, object]

    def embedding_text(self) -> str:
        return tool_document_text(self.name, self.description)


def _object_schema(
    properties: dict[str, object],
    required: list[str],
) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def _nullable_number() -> dict[str, object]:
    return {"type": ["number", "null"]}


TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="get_table_schema",
        description="获取一张或多张表的列名、数据类型、空值约束和中文注释。",
        input_schema=_object_schema(
            {
                "tables": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 12,
                    "uniqueItems": True,
                    "items": _TABLE,
                }
            },
            ["tables"],
        ),
        output_schema=_object_schema(
            {"ddl_list": {"type": "array", "items": {"type": "string"}}},
            ["ddl_list"],
        ),
    ),
    ToolDefinition(
        name="get_column_enums",
        description="查看某个列在样本范围内的不同取值，用来确认枚举或状态值。",
        input_schema=_object_schema(
            {
                "table": _TABLE,
                "column": _TABLE,
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            ["table", "column", "limit"],
        ),
        output_schema=_object_schema(
            {
                "distinct_values": {"type": "array"},
                "truncated": {"type": "boolean"},
            },
            ["distinct_values", "truncated"],
        ),
    ),
    ToolDefinition(
        name="get_foreign_keys",
        description="查询一张表的外键、被引用表和连接列，用来补齐 Join 路径。",
        input_schema=_object_schema({"table": _TABLE}, ["table"]),
        output_schema=_object_schema(
            {"fk_relations": {"type": "array", "items": {"type": "object"}}},
            ["fk_relations"],
        ),
    ),
    ToolDefinition(
        name="get_table_row_count",
        description="获取一张表的估计或精确行数，用来判断过滤条件和扫描规模。",
        input_schema=_object_schema(
            {"table": _TABLE, "exact": {"type": "boolean", "default": False}},
            ["table"],
        ),
        output_schema=_object_schema(
            {
                "row_count": {"type": "integer", "minimum": 0},
                "estimated": {"type": "boolean"},
            },
            ["row_count", "estimated"],
        ),
    ),
    ToolDefinition(
        name="get_partition_keys",
        description="查询一张表的分区键。普通表返回空列表。",
        input_schema=_object_schema({"table": _TABLE}, ["table"]),
        output_schema=_object_schema(
            {"partition_columns": {"type": "array", "items": {"type": "string"}}},
            ["partition_columns"],
        ),
    ),
    ToolDefinition(
        name="explain_sql_cost",
        description="查看一条只读 SQL 的规划代价；只有显式要求时才读取执行时间和缓冲区。",
        input_schema=_object_schema(
            {
                "sql": {"type": "string", "minLength": 1},
                "analyze": {"type": "boolean", "default": False},
            },
            ["sql"],
        ),
        output_schema=_object_schema(
            {
                "is_read_only": {"type": "boolean"},
                "planner_cost": {"type": "number"},
                "execution_time_ms": _nullable_number(),
                "shared_hit_blocks": _nullable_number(),
                "shared_read_blocks": _nullable_number(),
            },
            [
                "is_read_only",
                "planner_cost",
                "execution_time_ms",
                "shared_hit_blocks",
                "shared_read_blocks",
            ],
        ),
    ),
    ToolDefinition(
        name="check_sql_syntax",
        description="检查一条 SQL 的语法是否成立，不连接数据库执行。",
        input_schema=_object_schema(
            {"sql": {"type": "string", "minLength": 1}},
            ["sql"],
        ),
        output_schema=_object_schema(
            {
                "is_valid": {"type": "boolean"},
                "error": {"type": ["string", "null"]},
            },
            ["is_valid", "error"],
        ),
    ),
    ToolDefinition(
        name="get_etl_status",
        description="查询一张表最近一次同步的状态和时间，用来判断数据是否可用。",
        input_schema=_object_schema({"table": _TABLE}, ["table"]),
        output_schema=_object_schema(
            {
                "last_sync_time": {"type": ["string", "null"]},
                "status": {"type": "string"},
            },
            ["last_sync_time", "status"],
        ),
    ),
    ToolDefinition(
        name="get_data_owner",
        description="查询一张表的数据负责人内部 ID，不返回个人邮箱。",
        input_schema=_object_schema({"table": _TABLE}, ["table"]),
        output_schema=_object_schema({"owner_id": {"type": "string"}}, ["owner_id"]),
    ),
    ToolDefinition(
        name="get_metric_definition",
        description="查询指标的计算公式和可用维度，用来对齐口径。",
        input_schema=_object_schema(
            {"metric_name": {"type": "string", "minLength": 1, "maxLength": 128}},
            ["metric_name"],
        ),
        output_schema=_object_schema(
            {
                "formula": {"type": "string"},
                "dimensions": {"type": "array", "items": {"type": "string"}},
            },
            ["formula", "dimensions"],
        ),
    ),
)

TOOLS_BY_NAME: dict[str, ToolDefinition] = {tool.name: tool for tool in TOOLS}

if len(TOOLS) != 10 or len(TOOLS_BY_NAME) != 10:
    raise RuntimeError("MCP catalog must contain exactly 10 tools")
