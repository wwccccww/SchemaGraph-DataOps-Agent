"""BIRD 用例的冻结语义契约。只读问句与 expected_columns，不解析 Gold SQL 文本。"""

from __future__ import annotations

from app.schemas.benchmark import BenchmarkCase, SemanticContract


def contract_for(case: BenchmarkCase) -> SemanticContract:
    if case.source != "bird":
        raise ValueError("bird contracts only apply to bird cases")
    projections = list(case.expected_columns)
    # BIRD 答案形态差异大；冻结契约只约束投影列，不在 Prompt 里写 GROUP BY 键（易诱发多余 GROUP BY）。
    group_keys: list[str] = []
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
