"""BIRD 用例的冻结语义契约。只读问句与 expected_columns，不解析 Gold SQL 文本。"""

from __future__ import annotations

from app.evaluation.tpcds_contracts import _measure_columns
from app.schemas.benchmark import BenchmarkCase, SemanticContract


def contract_for(case: BenchmarkCase) -> SemanticContract:
    if case.source != "bird":
        raise ValueError("bird contracts only apply to bird cases")
    projections = list(case.expected_columns)
    measures = _measure_columns(projections)
    group_keys = [name for name in projections if name not in measures]
    filters: list[str] = []
    if case.order_sensitive:
        filters.append("order_sensitive=true")
    if case.required_tables:
        filters.append(f"core_tables={','.join(sorted(case.required_tables))}")
    return SemanticContract(
        projections=projections,
        group_keys=group_keys,
        filters=filters,
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
