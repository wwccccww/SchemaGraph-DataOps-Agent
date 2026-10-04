"""Schema-RAG 与 Tool-RAG 的检索结果。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SchemaSeed(BaseModel):
    """一条实体种子表。Junction Table 不能出现在这里。"""

    model_config = ConfigDict(extra="forbid")

    database_id: str
    schema_name: str
    table_name: str
    content_hash: str
    embedding_model: str
    embedding_version: str
    score: float


class ToolHit(BaseModel):
    """一条召回的 MCP 工具定义。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    input_schema: dict[str, object]
    score: float
