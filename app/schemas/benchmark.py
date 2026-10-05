"""评测用例契约。Gold SQL 只供评测进程读取。"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BenchmarkSource = Literal["custom", "tpcds-derived", "bird"]
BenchmarkDifficulty = Literal["basic", "medium", "complex"]
CategoryScope = Literal["exact", "descendants"]
OracleMethod = Literal["manual", "independent_sql", "python"]
GoldAssurance = Literal["executable", "contract_checked", "oracle_matched", "reviewed"]


class TimeWindow(BaseModel):
    """由锚点日展开的半开时间窗口。"""

    model_config = ConfigDict(extra="forbid")

    start: str
    end: str
    anchor_date: date


class SemanticContract(BaseModel):
    """问句定稿后的答案形状。它不从 Gold SQL 反推。"""

    model_config = ConfigDict(extra="forbid")

    projections: list[str] = Field(min_length=1)
    group_keys: list[str]
    filters: list[str]
    category_scope: CategoryScope
    time_window: TimeWindow | None
    dedup_key: Literal["order_id"] | None


class OracleRecord(BaseModel):
    """独立于 Gold SQL 文本的结果证据。"""

    model_config = ConfigDict(extra="forbid")

    method: OracleMethod
    result_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    row_count: int = Field(ge=0)
    reviewer_ids: list[str]
    status: GoldAssurance


class BenchmarkCase(BaseModel):
    """一条可执行的 Gold SQL 用例。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    source: BenchmarkSource
    source_version: str
    database_id: str
    difficulty: BenchmarkDifficulty
    dialect: Literal["postgres", "sqlite"]
    question: str = Field(min_length=1)
    gold_sql: str = Field(min_length=1)
    required_tables: list[str]
    required_junctions: list[str]
    order_sensitive: bool
    numeric_tolerance: float | None
    expected_columns: list[str] = Field(min_length=1)
    anchor_date: date
    tags: list[str]
    semantic_contract: SemanticContract | None = None
    oracle: OracleRecord | None = None
