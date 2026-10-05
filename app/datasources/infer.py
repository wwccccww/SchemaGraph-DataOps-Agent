"""为没有显式外键的库补充高置信连接。低置信边不会从这里产生。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.schemas.catalog import SchemaEdge, TableDocument

# 较长的后缀放在前面。只在目标列真实存在时建边。
_SURROGATE_KEYS = (
    ("catalog_page_sk", "catalog_page", "cp_catalog_page_sk"),
    ("call_center_sk", "call_center", "cc_call_center_sk"),
    ("income_band_sk", "income_band", "ib_income_band_sk"),
    ("ship_mode_sk", "ship_mode", "sm_ship_mode_sk"),
    ("web_page_sk", "web_page", "wp_web_page_sk"),
    ("web_site_sk", "web_site", "web_site_sk"),
    ("warehouse_sk", "warehouse", "w_warehouse_sk"),
    ("customer_sk", "customer", "c_customer_sk"),
    ("promo_sk", "promotion", "p_promo_sk"),
    ("reason_sk", "reason", "r_reason_sk"),
    ("addr_sk", "customer_address", "ca_address_sk"),
    ("cdemo_sk", "customer_demographics", "cd_demo_sk"),
    ("hdemo_sk", "household_demographics", "hd_demo_sk"),
    ("item_sk", "item", "i_item_sk"),
    ("store_sk", "store", "s_store_sk"),
    ("date_sk", "date_dim", "d_date_sk"),
    ("time_sk", "time_dim", "t_time_sk"),
)
_KEY_ALIASES = (frozenset({"cds", "cdscode"}),)
_INFERRED_CONFIDENCE = 0.95


def infer_reference_edges(
    documents: Sequence[TableDocument],
    *,
    single_keys: Mapping[str, set[str]],
    existing: Sequence[SchemaEdge],
) -> list[SchemaEdge]:
    """用代理键后缀和唯一键同名列补边。一对列只保留一条边。"""

    columns: dict[str, set[str]] = {}
    for document in documents:
        columns[document.table_name] = {column.name for column in document.columns}
    occupied = {
        (
            edge.source_table,
            edge.source_columns[0],
            edge.target_table,
            edge.target_columns[0],
        )
        for edge in existing
        if len(edge.source_columns) == 1 and len(edge.target_columns) == 1
    }
    edges: list[SchemaEdge] = []

    def add(source: str, source_column: str, target: str, target_column: str) -> None:
        key = (source, source_column, target, target_column)
        reverse = (target, target_column, source, source_column)
        if source == target or key in occupied or reverse in occupied:
            return
        occupied.add(key)
        edges.append(
            SchemaEdge(
                source_table=source,
                source_columns=[source_column],
                target_table=target,
                target_columns=[target_column],
                constraint_name=f"inferred_{source}_{source_column}_{target}",
                weight=1.0,
                inferred=True,
                confidence=_INFERRED_CONFIDENCE,
            )
        )

    for document in documents:
        for column in document.columns:
            matched = _surrogate_target(column.name, document.table_name, columns)
            if matched is not None:
                target, target_column = matched
                add(document.table_name, column.name, target, target_column)
            key_match = _unique_key_target(column.name, document.table_name, single_keys)
            if key_match is not None:
                target, target_column = key_match
                add(document.table_name, column.name, target, target_column)
    return edges


def _surrogate_target(
    column_name: str,
    table_name: str,
    columns: Mapping[str, set[str]],
) -> tuple[str, str] | None:
    lowered = column_name.lower()
    for suffix, target, target_column in _SURROGATE_KEYS:
        if lowered != suffix and not lowered.endswith("_" + suffix):
            continue
        if target == table_name:
            return None
        available = columns.get(target)
        if available is not None and target_column in available:
            return target, target_column
        return None
    return None


def _unique_key_target(
    column_name: str,
    table_name: str,
    single_keys: Mapping[str, set[str]],
) -> tuple[str, str] | None:
    normalized = _normalize(column_name)
    matches: list[tuple[str, str]] = []
    for target, keys in single_keys.items():
        if target == table_name:
            continue
        for key in keys:
            if _same_key(normalized, _normalize(key)):
                matches.append((target, key))
    if len(matches) != 1:
        return None
    return matches[0]


def _same_key(left: str, right: str) -> bool:
    if left == right:
        return True
    return frozenset({left, right}) in _KEY_ALIASES


def _normalize(name: str) -> str:
    return name.lower().replace("_", "")
