"""把 database_id 解析成方言、业务配置和 schema。

未登记的标识保持拒绝。这里不读取评测用例，也不连接数据库。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DialectName = Literal["postgres", "sqlite"]
ProfileName = Literal["ecommerce", "generic"]


@dataclass(frozen=True)
class DataSource:
    """一个已登记的只读问数库。"""

    database_id: str
    dialect: DialectName
    profile: ProfileName
    schema_name: str


_SOURCES: dict[str, DataSource] = {
    "ecommerce": DataSource("ecommerce", "postgres", "ecommerce", "public"),
    "tpcds": DataSource("tpcds", "postgres", "generic", "public"),
    "california_schools": DataSource("california_schools", "sqlite", "generic", "main"),
    "financial": DataSource("financial", "sqlite", "generic", "main"),
}


def resolve_data_source(database_id: str) -> DataSource | None:
    """返回已登记的数据源。未知标识返回 None。"""

    return _SOURCES.get(database_id)


def registered_database_ids() -> frozenset[str]:
    """当前可以问数的 database_id。"""

    return frozenset(_SOURCES)
