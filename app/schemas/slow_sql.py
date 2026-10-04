"""慢 SQL 诊断 API 契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.text_to_sql import ApiError


class SlowSqlRequest(BaseModel):
    """诊断请求。database_id 只接受标识符。"""

    model_config = ConfigDict(extra="forbid")

    database_id: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
    sql: str = Field(min_length=1, max_length=8000)
    run_analyze: bool = True
    rewrite: bool = True

    @field_validator("sql")
    @classmethod
    def require_sql_text(cls, value: str) -> str:
        stripped = value.strip()
        if stripped == "":
            raise ValueError("sql must contain non-whitespace text")
        return stripped


class SlowSqlFinding(BaseModel):
    """一条静态规则或计划规则。"""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    severity: Literal["high", "medium", "low"]
    message: str


class SlowSqlPlan(BaseModel):
    """计划摘要。run_analyze 为 false 时运行时字段必须为空。"""

    model_config = ConfigDict(extra="forbid")

    total_cost: float
    execution_time_ms: float | None = None
    shared_hit_blocks: int | None = None
    shared_read_blocks: int | None = None


class SlowSqlCandidate(BaseModel):
    """一个改写候选。降幅分母无效时对应字段为空。"""

    model_config = ConfigDict(extra="forbid")

    sql: str
    equivalent: bool
    planner_cost_drop: float | None = None
    execution_time_drop: float | None = None
    shared_buffer_access_drop: float | None = None


class SlowSqlResponse(BaseModel):
    """诊断响应。失败时仍可带上已经得到的规则。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    status: Literal["succeeded", "failed"]
    findings: list[SlowSqlFinding] = Field(default_factory=list)
    original_plan: SlowSqlPlan | None = None
    candidate: SlowSqlCandidate | None = None
    error: ApiError | None = None
