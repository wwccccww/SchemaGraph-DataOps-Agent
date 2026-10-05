"""TPC-DS 派生 Gold 的结构 Oracle。不替代数据库执行，只校验审计规则。"""

from __future__ import annotations

import re

from app.evaluation.tpcds import SALES_YEAR
from app.schemas.benchmark import BenchmarkCase

_YEAR_FILTER = re.compile(rf"\b{SALES_YEAR}\b|d_year\s*=\s*{SALES_YEAR}|d_year\s*=\s*__YEAR__")


def structural_oracle_passed(case: BenchmarkCase) -> bool:
    """Gold SQL 必须显式锚定销售年，且不能依赖 runtime 时钟。"""

    if case.source != "tpcds-derived":
        return False
    lowered = case.gold_sql.lower()
    if "now()" in lowered or "current_date" in lowered or "localtimestamp" in lowered:
        return False
    if str(SALES_YEAR) not in case.question:
        return True
    return _YEAR_FILTER.search(case.gold_sql) is not None
