"""TPC-DS 派生用例的语义契约。只读问句与已定稿投影，不解析 Gold SQL。"""

from __future__ import annotations

import re
from datetime import date

from app.schemas.benchmark import BenchmarkCase, SemanticContract, TimeWindow

ANCHOR = date(2026, 10, 1)
SALES_YEAR = 2001

_MEASURE_SUFFIX = (
    "_amount",
    "_profit",
    "_cost",
    "_revenue",
    "_quantity",
    "_count",
    "_sales",
    "_returns",
    "_tax",
    "_fee",
)
_MEASURE_NAMES = frozenset(
    {
        "net_profit",
        "sales_amount",
        "return_amount",
        "total_sales",
        "avg_sales",
        "order_count",
        "customer_count",
        "inventory_qty",
    }
)
_YEAR_IN_QUESTION = re.compile(r"(\d{4})\s*年")


def contract_for(case: BenchmarkCase) -> SemanticContract:
    """从中文问句与 expected_columns 生成契约。"""

    if case.source != "tpcds-derived":
        raise ValueError("tpcds contracts only apply to tpcds-derived cases")
    projections = list(case.expected_columns)
    measures = _measure_columns(projections)
    group_keys = [name for name in projections if name not in measures]
    return SemanticContract(
        projections=projections,
        group_keys=group_keys,
        filters=_filters_from_question(case.question),
        category_scope="exact",
        time_window=_time_window(case.question),
        dedup_key=None,
    )


def _measure_columns(projections: list[str]) -> list[str]:
    measures: list[str] = []
    for name in projections:
        if name in _MEASURE_NAMES or any(name.endswith(suffix) for suffix in _MEASURE_SUFFIX):
            measures.append(name)
    if measures:
        return measures
    if len(projections) >= 2:
        return [projections[-1]]
    return []


def _filters_from_question(question: str) -> list[str]:
    filters: list[str] = []
    match = _YEAR_IN_QUESTION.search(question)
    year = int(match.group(1)) if match else SALES_YEAR
    if str(year) in question:
        filters.append(f"calendar_year={year}")
    if "促销" in question or "直邮" in question:
        filters.append("promotion_channel=dmail")
    if "退货" in question:
        filters.append("returns_present=true")
    return filters


def _time_window(question: str) -> TimeWindow | None:
    match = _YEAR_IN_QUESTION.search(question)
    if match is None and str(SALES_YEAR) not in question:
        return None
    year = int(match.group(1)) if match else SALES_YEAR
    return TimeWindow(
        start=f"{year}-01-01",
        end=f"{year + 1}-01-01",
        anchor_date=ANCHOR,
    )
