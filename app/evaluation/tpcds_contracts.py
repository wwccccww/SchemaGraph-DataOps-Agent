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
    filters = _filters_from_question(case.question)
    filters.extend(_fact_filters(case.required_tables, case.question))
    if case.required_tables:
        filters.append(f"core_tables={','.join(sorted(case.required_tables))}")
        filters.append("audit_tables_strict=true")
    return SemanticContract(
        projections=projections,
        group_keys=group_keys,
        filters=filters,
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


def _fact_filters(required_tables: list[str], question: str) -> list[str]:
    """事实表提示来自冻结用例审计字段，不进入 Prompt 的 required_tables 列表。"""

    sales = [
        name
        for name in required_tables
        if name.endswith("_sales") or name.endswith("_returns")
    ]
    if not sales:
        return []
    if len(sales) == 1:
        return [f"primary_fact={sales[0]}"]
    chosen: list[str] = []
    if "目录" in question:
        chosen.extend(name for name in sales if name.startswith("catalog"))
    if "门店" in question:
        chosen.extend(name for name in sales if name.startswith("store"))
    if "网站" in question or "网页" in question:
        chosen.extend(name for name in sales if name.startswith("web"))
    chosen = list(dict.fromkeys(chosen))
    if len(chosen) == 1:
        return [f"primary_fact={chosen[0]}"]
    filters = [f"primary_facts={','.join(sorted(sales))}"]
    if "退货" in question and "销售" in question:
        filters.append("returns_vs_sales=separate_cte")
        return filters
    if re.search(r"既在.+又在", question) and len(sales) >= 2:
        filters.append("cross_channel_buyers=customer_and_item")
        return filters
    if "比较" in question and len([name for name in sales if name.endswith("_sales")]) >= 2:
        filters.append("channel_pivot_compare=true")
        return filters
    if len(sales) >= 2 and all(name.endswith("_returns") for name in sales):
        filters.append("multi_returns_union=true")
        return filters
    if _multi_channel_sales_union_question(question):
        filters.append("multi_channel_union=true")
    return filters


def _multi_channel_sales_union_question(question: str) -> bool:
    if "渠道" in question:
        return True
    return bool(re.search(r"门店、目录和网站|三条渠道", question))


def _filters_from_question(question: str) -> list[str]:
    filters: list[str] = []
    match = _YEAR_IN_QUESTION.search(question)
    year = int(match.group(1)) if match else SALES_YEAR
    if str(year) in question:
        filters.append(f"calendar_year={year}")
    if "直邮" in question or re.search(r"\bdmail\b", question, re.IGNORECASE):
        filters.append("promotion_channel=dmail")
        filters.append("promotion_via_item_sk_subquery=true")
    if "退货" in question:
        filters.append("returns_present=true")
    if "库存" in question and re.search(r"卖|售", question):
        filters.append("inventory_sold_items=subquery")
    if "出生年份" in question or re.search(r"birth year", question, re.IGNORECASE):
        filters.append("birth_year_not_null=true")
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
