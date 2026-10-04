"""Catalog、外键边和图扩展的 Pydantic 契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GraphFailureCode = Literal[
    "no_path",
    "path_too_deep",
    "budget_exceeded",
    "low_confidence_only",
]


class ColumnDocument(BaseModel):
    """列元数据。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    data_type: str
    nullable: bool
    comment: str | None = None


class TableDocument(BaseModel):
    """表级文档。Catalog 提取时向量字段为空，索引行另行保存模型、版本和向量。"""

    model_config = ConfigDict(extra="forbid")

    database_id: str
    schema_name: str
    table_name: str
    table_comment: str | None = None
    columns: list[ColumnDocument]
    is_junction: bool
    content_hash: str
    embedding_model: str | None = None
    embedding_version: str | None = None


class SchemaEdge(BaseModel):
    """一条保留方向的 Join 边。搜索时按无向边使用。"""

    model_config = ConfigDict(extra="forbid")

    source_table: str
    source_columns: list[str]
    target_table: str
    target_columns: list[str]
    constraint_name: str
    weight: float = Field(gt=0)
    inferred: bool
    confidence: float = Field(ge=0, le=1)


class GraphDiagnostic(BaseModel):
    """图扩展失败时返回的结构化诊断。"""

    model_config = ConfigDict(extra="forbid")

    code: GraphFailureCode
    message: str
    seeds: list[str]


class GraphExpansionResult(BaseModel):
    """Schema Graph 扩展结果。expanded_tables 不重复 Seed。"""

    model_config = ConfigDict(extra="forbid")

    seed_tables: list[str]
    expanded_tables: list[str]
    edges: list[SchemaEdge]
    connected: bool
    context_tokens: int = Field(ge=0)
    context_truncated: bool
    warnings: list[str] = Field(default_factory=list)
    diagnostic: GraphDiagnostic | None = None
