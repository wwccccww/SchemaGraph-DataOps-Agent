"""电商 12 表的稳定标识。表名来自基准 DDL，不接受外部输入。"""

from __future__ import annotations

from dataclasses import dataclass

IDENTIFIER_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]{0,62}$"


@dataclass(frozen=True)
class TableSpec:
    """一张业务表的列顺序。第一列是主键。"""

    name: str
    columns: tuple[str, ...]

    @property
    def primary_key(self) -> str:
        return self.columns[0]


@dataclass(frozen=True)
class ForeignKeySpec:
    """PostgreSQL 对单列外键的默认约束名和方向。"""

    constraint_name: str
    source_table: str
    source_column: str
    target_table: str
    target_column: str


TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec("t_user_level", ("level_id", "level_name", "discount_rate")),
    TableSpec("t_region", ("region_id", "region_name", "province_name")),
    TableSpec("t_user", ("user_id", "username", "user_level_id", "created_at")),
    TableSpec(
        "t_user_region_map",
        ("map_id", "user_id", "region_id", "address_detail"),
    ),
    TableSpec("t_merchant", ("merchant_id", "merchant_name", "is_self_operated")),
    TableSpec("t_category", ("category_id", "category_name", "parent_id")),
    TableSpec(
        "t_product",
        ("product_id", "product_name", "category_id", "merchant_id", "price"),
    ),
    TableSpec("t_coupon", ("coupon_id", "coupon_name", "coupon_type", "min_amount")),
    TableSpec(
        "t_order",
        ("order_id", "user_id", "total_amount", "order_status", "created_at"),
    ),
    TableSpec(
        "t_order_coupon_rel",
        ("rel_id", "order_id", "coupon_id", "discount_amount"),
    ),
    TableSpec(
        "t_order_detail",
        ("detail_id", "order_id", "product_id", "quantity", "price"),
    ),
    TableSpec("t_promo_sku_rel", ("rel_id", "product_id", "coupon_id")),
)

TABLE_NAMES: tuple[str, ...] = tuple(spec.name for spec in TABLE_SPECS)

JUNCTION_TABLES: frozenset[str] = frozenset(
    {
        "t_user_region_map",
        "t_order_coupon_rel",
        "t_promo_sku_rel",
    }
)

FOREIGN_KEYS: tuple[ForeignKeySpec, ...] = (
    ForeignKeySpec(
        "t_user_user_level_id_fkey",
        "t_user",
        "user_level_id",
        "t_user_level",
        "level_id",
    ),
    ForeignKeySpec(
        "t_user_region_map_user_id_fkey",
        "t_user_region_map",
        "user_id",
        "t_user",
        "user_id",
    ),
    ForeignKeySpec(
        "t_user_region_map_region_id_fkey",
        "t_user_region_map",
        "region_id",
        "t_region",
        "region_id",
    ),
    ForeignKeySpec(
        "t_product_category_id_fkey",
        "t_product",
        "category_id",
        "t_category",
        "category_id",
    ),
    ForeignKeySpec(
        "t_product_merchant_id_fkey",
        "t_product",
        "merchant_id",
        "t_merchant",
        "merchant_id",
    ),
    ForeignKeySpec("t_order_user_id_fkey", "t_order", "user_id", "t_user", "user_id"),
    ForeignKeySpec(
        "t_order_coupon_rel_order_id_fkey",
        "t_order_coupon_rel",
        "order_id",
        "t_order",
        "order_id",
    ),
    ForeignKeySpec(
        "t_order_coupon_rel_coupon_id_fkey",
        "t_order_coupon_rel",
        "coupon_id",
        "t_coupon",
        "coupon_id",
    ),
    ForeignKeySpec(
        "t_order_detail_order_id_fkey",
        "t_order_detail",
        "order_id",
        "t_order",
        "order_id",
    ),
    ForeignKeySpec(
        "t_order_detail_product_id_fkey",
        "t_order_detail",
        "product_id",
        "t_product",
        "product_id",
    ),
    ForeignKeySpec(
        "t_promo_sku_rel_product_id_fkey",
        "t_promo_sku_rel",
        "product_id",
        "t_product",
        "product_id",
    ),
    ForeignKeySpec(
        "t_promo_sku_rel_coupon_id_fkey",
        "t_promo_sku_rel",
        "coupon_id",
        "t_coupon",
        "coupon_id",
    ),
)

INDEX_NAMES: tuple[str, ...] = (
    "idx_user_level",
    "idx_user_region_user",
    "idx_user_region_region",
    "idx_order_user",
    "idx_order_created_at",
    "idx_order_status",
    "idx_order_coupon_order",
    "idx_order_coupon_coupon",
    "idx_order_detail_order",
    "idx_order_detail_product",
    "idx_product_category",
    "idx_product_merchant",
)
