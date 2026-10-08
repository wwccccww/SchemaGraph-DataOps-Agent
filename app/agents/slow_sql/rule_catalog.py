"""慢 SQL 规则元数据。默认电商静态集，可与 Catalog 快照合并。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.db.tables import JUNCTION_TABLES
from app.schemas.catalog import TableDocument

_STATIC_LARGE_TABLES = frozenset({"t_order", "t_order_detail"})
_STATIC_CHILD_TABLES = frozenset(JUNCTION_TABLES) | frozenset({"t_order_detail"})
_STATIC_INDEXED_COLUMNS = frozenset(
    {
        ("t_user_level", "level_id"),
        ("t_region", "region_id"),
        ("t_user", "user_id"),
        ("t_user", "user_level_id"),
        ("t_user_region_map", "map_id"),
        ("t_user_region_map", "user_id"),
        ("t_user_region_map", "region_id"),
        ("t_merchant", "merchant_id"),
        ("t_category", "category_id"),
        ("t_product", "product_id"),
        ("t_product", "category_id"),
        ("t_product", "merchant_id"),
        ("t_coupon", "coupon_id"),
        ("t_order", "order_id"),
        ("t_order", "user_id"),
        ("t_order", "created_at"),
        ("t_order", "order_status"),
        ("t_order_coupon_rel", "rel_id"),
        ("t_order_coupon_rel", "order_id"),
        ("t_order_coupon_rel", "coupon_id"),
        ("t_order_detail", "detail_id"),
        ("t_order_detail", "order_id"),
        ("t_order_detail", "product_id"),
        ("t_promo_sku_rel", "rel_id"),
        ("t_promo_sku_rel", "product_id"),
        ("t_promo_sku_rel", "coupon_id"),
    }
)


@dataclass(frozen=True)
class RuleCatalog:
    large_tables: frozenset[str]
    child_tables: frozenset[str]
    indexed_columns: frozenset[tuple[str, str]]


DEFAULT_RULE_CATALOG = RuleCatalog(
    large_tables=_STATIC_LARGE_TABLES,
    child_tables=_STATIC_CHILD_TABLES,
    indexed_columns=_STATIC_INDEXED_COLUMNS,
)


@dataclass(frozen=True)
class TableStat:
    est_rows: float
    total_bytes: int


def build_rule_catalog(
    documents: Sequence[TableDocument],
    stats: Mapping[str, TableStat],
    indexed_columns: frozenset[tuple[str, str]],
    *,
    large_row_threshold: float = 5_000,
    large_bytes_threshold: int = 8_000_000,
) -> RuleCatalog:
    """合并 Catalog 快照、统计信息与索引列。"""

    names = {document.table_name for document in documents}
    large = set(_STATIC_LARGE_TABLES & names)
    for table_name, item in stats.items():
        if table_name not in names:
            continue
        if item.est_rows >= large_row_threshold or item.total_bytes >= large_bytes_threshold:
            large.add(table_name)
    child = {document.table_name for document in documents if document.is_junction}
    child |= _STATIC_CHILD_TABLES & names
    static_indexed = frozenset(
        item for item in _STATIC_INDEXED_COLUMNS if item[0] in names
    )
    live_indexed = frozenset(item for item in indexed_columns if item[0] in names)
    indexed = static_indexed | live_indexed
    if not indexed:
        indexed = _STATIC_INDEXED_COLUMNS
    return RuleCatalog(
        large_tables=frozenset(large),
        child_tables=frozenset(child),
        indexed_columns=indexed,
    )
