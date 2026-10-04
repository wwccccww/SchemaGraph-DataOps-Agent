"""评测用例契约。Gold SQL 只供评测进程读取。"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BenchmarkSource = Literal["custom", "tpcds-derived", "bird"]
BenchmarkDifficulty = Literal["basic", "medium", "complex"]


class BenchmarkCase(BaseModel):
    """一条可执行的 Gold SQL 用例。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    source: BenchmarkSource
    source_version: str
    database_id: str
    difficulty: BenchmarkDifficulty
    dialect: Literal["postgres"]
    question: str = Field(min_length=1)
    gold_sql: str = Field(min_length=1)
    required_tables: list[str]
    required_junctions: list[str]
    order_sensitive: bool
    numeric_tolerance: float | None
    expected_columns: list[str] = Field(min_length=1)
    anchor_date: date
    tags: list[str]
