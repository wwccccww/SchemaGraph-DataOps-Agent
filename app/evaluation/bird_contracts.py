"""BIRD 用例的冻结语义契约。只读问句与 expected_columns，不解析 Gold SQL 文本。"""

from __future__ import annotations

from app.evaluation.tpcds_contracts import _MEASURE_NAMES, _MEASURE_SUFFIX
from app.schemas.benchmark import BenchmarkCase, SemanticContract

_BIRD_MEASURE_TOKENS = (
    "rate",
    "ratio",
    "percent",
    "percentage",
    "avg",
    "average",
    "count",
    "total",
    "sum",
    "num",
    "score",
)


def _bird_measure_columns(projections: list[str]) -> list[str]:
    """BIRD 投影多为混合维度；不用 TPC-DS「最后一列当度量」启发式。"""

    measures: list[str] = []
    for name in projections:
        lowered = name.lower()
        if name in _MEASURE_NAMES or any(name.endswith(suffix) for suffix in _MEASURE_SUFFIX):
            measures.append(name)
        elif any(token in lowered for token in _BIRD_MEASURE_TOKENS):
            measures.append(name)
    return measures


def contract_for(case: BenchmarkCase) -> SemanticContract:
    if case.source != "bird":
        raise ValueError("bird contracts only apply to bird cases")
    projections = list(case.expected_columns)
    measures = _bird_measure_columns(projections)
    group_keys = [name for name in projections if name not in measures] if measures else []
    filters: list[str] = []
    if case.order_sensitive:
        filters.append("order_sensitive=true")
    if case.required_tables:
        # 仅作 Prompt 提示；硬校验由投影列推导的表承担，避免一次报 8 条缺表导致熔断。
        filters.append(f"core_tables={','.join(sorted(case.required_tables))}")
    filters.append(f"anchor_date={case.anchor_date.isoformat()}")
    return SemanticContract(
        projections=projections,
        group_keys=group_keys,
        filters=filters,
        category_scope="exact",
        time_window=None,
        dedup_key=None,
    )
