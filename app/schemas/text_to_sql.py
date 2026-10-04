"""Text-to-SQL API 契约。"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

JsonValue = str | int | float | bool | None
_JS_SAFE_INTEGER = 2**53 - 1


class TextToSqlRequest(BaseModel):
    """问数请求。"""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)
    database_id: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
    execute: bool = True
    max_rows: int = Field(default=1000, ge=1, le=1000)

    @field_validator("question")
    @classmethod
    def require_question_text(cls, value: str) -> str:
        stripped = value.strip()
        if stripped == "":
            raise ValueError("question must contain non-whitespace text")
        return stripped


class SchemaContextView(BaseModel):
    """返回给调用方的 Schema 子图摘要。"""

    model_config = ConfigDict(extra="forbid")

    seed_tables: list[str]
    expanded_tables: list[str]
    token_count: int = Field(ge=0)
    truncated: bool


class ApiError(BaseModel):
    """外部错误。不包含 SQLSTATE、堆栈或连接信息。"""

    model_config = ConfigDict(extra="forbid")

    category: str
    message: str
    retryable: bool


class TextToSqlResponse(BaseModel):
    """问数响应。失败时省略 SQL 和结果。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    status: Literal["succeeded", "failed"]
    sql: str | None = None
    columns: list[str] | None = None
    rows: list[list[JsonValue]] | None = None
    schema_context: SchemaContextView | None = None
    attempts: int | None = None
    error: ApiError | None = None


def json_cell(value: object) -> JsonValue:
    """把数据库值变成 JSON 安全值。大整数和 Decimal 使用字符串。"""

    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) > _JS_SAFE_INTEGER:
            return str(value)
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        return value
    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return moment.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def json_rows(
    rows: list[tuple[object, ...]] | tuple[tuple[object, ...], ...],
) -> list[list[JsonValue]]:
    """序列化整张结果表。"""

    return [[json_cell(cell) for cell in row] for row in rows]
