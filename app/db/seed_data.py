"""固定种子的电商造数。

摘要在锁定的 Faker 版本上稳定。所有时间都显式写入，不调用 now()。
"""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from faker import Faker

from app.db.tables import TABLE_NAMES, TABLE_SPECS

SEED = 20261001
ANCHOR_DATE = datetime(2026, 10, 1)
LAST_MONTH_START = datetime(2026, 9, 1)
LAST_MONTH_END = ANCHOR_DATE
RANDOM_START = datetime(2025, 1, 1)
SPAN_MINUTES = (LAST_MONTH_END - RANDOM_START) // timedelta(minutes=1)

USER_COUNT = 20_000
MERCHANT_COUNT = 200
CATEGORY_COUNT = 50
PRODUCT_COUNT = 10_000
COUPON_COUNT = 100
ORDER_COUNT = 120_000
DETAIL_COUNT = 300_000
PRODUCTS_PER_MERCHANT = 50
GROUPS_PER_MERCHANT = 10
PRODUCTS_PER_GROUP = 5
TWO_DETAIL_ORDERS = 60_000
COHORT_ORDERS = 6
EXTRA_ADDRESS_COUNT = 1
FULL_REDUCTION_COUPONS = 40

MONEY = Decimal("0.01")
COHORT_DISCOUNT = Decimal("8.00")
BEAUTY_CATEGORY_ID = 11
BEAUTY_NAME = "美妆"
PAID = "PAID"
CANCELLED = "CANCELLED"
FULL_REDUCTION = "full_reduction"
DISCOUNT = "discount"

ROOT_CATEGORIES = (
    "美妆个护",
    "数码",
    "服饰",
    "食品",
    "家居",
    "母婴",
    "运动",
    "图书",
    "家电",
    "汽车",
)
LEAF_CATEGORIES = (
    "美妆",
    "护肤",
    "彩妆",
    "香水",
    "手机",
    "电脑",
    "耳机",
    "相机",
    "男装",
    "女装",
    "鞋靴",
    "箱包",
    "零食",
    "饮料",
    "生鲜",
    "粮油",
    "家具",
    "灯具",
    "收纳",
    "厨具",
    "奶粉",
    "纸尿裤",
    "玩具",
    "童装",
    "跑步",
    "瑜伽",
    "球类",
    "户外",
    "小说",
    "教材",
    "童书",
    "文具",
    "冰箱",
    "洗衣机",
    "空调",
    "电视",
    "汽配",
    "车载",
    "保养",
    "摩托",
)
REGIONS = (
    ("华北", "北京"),
    ("华北", "天津"),
    ("华北", "河北"),
    ("华北", "山西"),
    ("华北", "内蒙古"),
    ("华北", "辽宁"),
    ("华北", "吉林"),
    ("华北", "黑龙江"),
    ("华东", "上海"),
    ("华东", "江苏"),
    ("华东", "浙江"),
    ("华东", "安徽"),
    ("华东", "福建"),
    ("华东", "江西"),
    ("华东", "山东"),
    ("华中", "河南"),
    ("华中", "湖北"),
    ("华中", "湖南"),
    ("华南", "广东"),
    ("华南", "广西"),
    ("华南", "海南"),
    ("西南", "重庆"),
    ("西南", "四川"),
    ("西南", "贵州"),
    ("西南", "云南"),
    ("西南", "西藏"),
    ("西北", "陕西"),
    ("西北", "甘肃"),
    ("西北", "青海"),
    ("西北", "宁夏"),
    ("西北", "新疆"),
)
LEVELS = (
    (1, "VIP1", Decimal("1.00")),
    (2, "VIP2", Decimal("0.98")),
    (3, "VIP3", Decimal("0.95")),
    (4, "VIP4", Decimal("0.90")),
    (5, "VIP5", Decimal("0.85")),
)
# 订单、用户、商家。前 4 单给自营美妆一店，后 2 单给自营美妆二店。
COHORT = (
    (1, 1, 1),
    (2, 2, 1),
    (3, 3, 1),
    (4, 4, 1),
    (5, 5, 2),
    (6, 6, 2),
)


@dataclass(frozen=True)
class SeedDataset:
    """一次确定性造数的全部行和摘要。"""

    rows: Mapping[str, tuple[tuple[object, ...], ...]]
    digest: str

    def count(self, table: str) -> int:
        return len(self.rows[table])


def build_dataset(seed: int = SEED) -> SeedDataset:
    """生成默认规模的数据。相同种子得到相同摘要。"""

    _check_scale()
    rng = random.Random(seed)
    fake = Faker("zh_CN")
    fake.seed_instance(seed)
    rows = _generate(rng, fake)
    validate_dataset(rows)
    frozen = {name: tuple(rows[name]) for name in TABLE_NAMES}
    return SeedDataset(rows=frozen, digest=digest_rows(frozen))


def digest_rows(rows: Mapping[str, Sequence[Sequence[object]]]) -> str:
    """按表名和主键顺序计算 sha256。内存行和数据库回读共用这一格式。"""

    hasher = hashlib.sha256()
    for spec in TABLE_SPECS:
        hasher.update(spec.name.encode())
        hasher.update(b"\0")
        for record in rows[spec.name]:
            if len(record) != len(spec.columns):
                raise ValueError(f"{spec.name} row width mismatch")
            for value in record:
                hasher.update(normalize(value).encode())
                hasher.update(b"\x1f")
            hasher.update(b"\n")
    return hasher.hexdigest()


def normalize(value: object) -> str:
    """把造数单元格转成稳定文本。"""

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return format(value.quantize(MONEY), "f")
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            raise ValueError("timestamps must be naive")
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, str):
        return value
    raise TypeError(f"unsupported seed value: {type(value).__name__}")


def validate_dataset(rows: Mapping[str, Sequence[Sequence[object]]]) -> None:
    """检查规模、金额、同商同类和复杂 Gold 条件。"""

    if set(rows) != set(TABLE_NAMES):
        raise ValueError("seed tables do not match the ecommerce schema")
    expected = {
        "t_user_level": len(LEVELS),
        "t_region": len(REGIONS),
        "t_user": USER_COUNT,
        "t_user_region_map": USER_COUNT + EXTRA_ADDRESS_COUNT,
        "t_merchant": MERCHANT_COUNT,
        "t_category": CATEGORY_COUNT,
        "t_product": PRODUCT_COUNT,
        "t_coupon": COUPON_COUNT,
        "t_order": ORDER_COUNT,
        "t_order_detail": DETAIL_COUNT,
    }
    for name, count in expected.items():
        if len(rows[name]) != count:
            raise ValueError(f"{name} has {len(rows[name])} rows, expected {count}")
    for name in TABLE_NAMES:
        _assert_primary_keys(name, rows[name])

    levels = {_as_int(record[0]): _as_str(record[1]) for record in rows["t_user_level"]}
    regions = {_as_int(record[0]): _as_str(record[1]) for record in rows["t_region"]}
    if set(regions.values()) != {"华北", "华东", "华中", "华南", "西南", "西北"}:
        raise ValueError("regions must cover six areas")
    users = {_as_int(record[0]): _as_int(record[2]) for record in rows["t_user"]}
    user_regions: dict[int, list[int]] = defaultdict(list)
    for record in rows["t_user_region_map"]:
        user_regions[_as_int(record[1])].append(_as_int(record[2]))
    merchants = {_as_int(record[0]): _as_bool(record[2]) for record in rows["t_merchant"]}
    categories = {
        _as_int(record[0]): (_as_str(record[1]), _as_int(record[2]))
        for record in rows["t_category"]
    }
    if categories[BEAUTY_CATEGORY_ID] != (BEAUTY_NAME, 1):
        raise ValueError("美妆 must be a leaf category")
    products = {
        _as_int(record[0]): (
            _as_int(record[2]),
            _as_int(record[3]),
            _as_decimal(record[4]),
        )
        for record in rows["t_product"]
    }
    for category_id, _merchant_id, _price in products.values():
        if categories[category_id][1] == 0:
            raise ValueError("products must reference leaf categories")
    coupons = {_as_int(record[0]): _as_str(record[2]) for record in rows["t_coupon"]}
    if coupons[1] != FULL_REDUCTION:
        raise ValueError("coupon 1 must be full_reduction")
    orders = {
        _as_int(record[0]): (
            _as_int(record[1]),
            _as_decimal(record[2]),
            _as_str(record[3]),
            _as_datetime(record[4]),
        )
        for record in rows["t_order"]
    }
    rels: dict[int, list[tuple[int, Decimal]]] = defaultdict(list)
    for record in rows["t_order_coupon_rel"]:
        rels[_as_int(record[1])].append((_as_int(record[2]), _as_decimal(record[3])))
    details: dict[int, list[tuple[int, int, Decimal]]] = defaultdict(list)
    for record in rows["t_order_detail"]:
        details[_as_int(record[1])].append(
            (_as_int(record[2]), _as_int(record[3]), _as_decimal(record[4]))
        )
    promos = {(_as_int(record[1]), _as_int(record[2])) for record in rows["t_promo_sku_rel"]}

    paid = cancelled = 0
    for order_id in range(1, ORDER_COUNT + 1):
        user_id, total, status, _created = orders[order_id]
        order_details = details[order_id]
        expected_lines = 2 if order_id <= TWO_DETAIL_ORDERS else 3
        if len(order_details) != expected_lines:
            raise ValueError(f"order {order_id} has {len(order_details)} details")
        merchant_ids = set()
        category_ids = set()
        gross = Decimal("0.00")
        for product_id, quantity, price in order_details:
            category_id, merchant_id, catalog_price = products[product_id]
            if price != catalog_price:
                raise ValueError(f"order {order_id} price snapshot drifted")
            merchant_ids.add(merchant_id)
            category_ids.add(category_id)
            gross += price * Decimal(quantity)
        if len(merchant_ids) != 1 or len(category_ids) != 1:
            raise ValueError(f"order {order_id} mixes merchants or categories")
        discount = sum((amount for _coupon_id, amount in rels[order_id]), Decimal("0.00"))
        if discount > gross or total != (gross - discount).quantize(MONEY):
            raise ValueError(f"order {order_id} total_amount is inconsistent")
        if status == PAID:
            paid += 1
        elif status == CANCELLED:
            cancelled += 1
        else:
            raise ValueError(f"unexpected order status {status}")
        if user_id not in users:
            raise ValueError(f"order {order_id} user is missing")
    if paid == 0 or cancelled == 0:
        raise ValueError("seed must contain both paid and cancelled orders")

    groups: dict[int, int] = defaultdict(int)
    join_rows = 0
    matched = _complex_orders(
        orders,
        users,
        levels,
        user_regions,
        regions,
        details,
        products,
        categories,
        merchants,
        rels,
        coupons,
    )
    for order_id, merchant_id in matched:
        groups[merchant_id] += 1
        user_id = orders[order_id][0]
        east = sum(1 for region_id in user_regions[user_id] if regions[region_id] == "华东")
        reduction = sum(
            1 for coupon_id, _amount in rels[order_id] if coupons[coupon_id] == FULL_REDUCTION
        )
        join_rows += east * len(details[order_id]) * reduction
        for product_id, _quantity, _price in details[order_id]:
            if (product_id, 1) not in promos and order_id <= COHORT_ORDERS:
                raise ValueError(f"cohort product {product_id} is not in the promo")
    if groups[1] < 4 or groups[2] < 2 or len(groups) < 2:
        raise ValueError("complex gold filters are empty or not distinguishable")
    if join_rows <= sum(groups.values()):
        raise ValueError("complex gold join must fan out before order deduplication")


def category_for(merchant_id: int, group: int) -> int:
    """同一商家的一个商品组只对应一个末级品类。商家 2 的第一组固定为美妆。"""

    if merchant_id == 2 and group == 0:
        return BEAUTY_CATEGORY_ID
    return BEAUTY_CATEGORY_ID + (merchant_id - 1 + group) % len(LEAF_CATEGORIES)


def group_product_ids(merchant_id: int, group: int) -> list[int]:
    start = (merchant_id - 1) * PRODUCTS_PER_MERCHANT + group * PRODUCTS_PER_GROUP + 1
    return list(range(start, start + PRODUCTS_PER_GROUP))


def product_price(product_id: int) -> Decimal:
    cents = 1000 + (product_id % 500) * 10
    return (Decimal(cents) / Decimal(100)).quantize(MONEY)


def _generate(rng: random.Random, fake: Faker) -> dict[str, list[tuple[object, ...]]]:
    # Faker 调用顺序是摘要的一部分：用户名、地址、补充地址、商家、商品、优惠券。
    usernames = [_text(_as_fake(fake.user_name()), 64) for _ in range(USER_COUNT)]
    addresses = [_text(_as_fake(fake.address()), 255) for _ in range(USER_COUNT)]
    extra_address = _text(_as_fake(fake.address()), 255)
    merchant_names = [_text(_as_fake(fake.company()), 128) for _ in range(MERCHANT_COUNT)]
    merchant_names[0] = "自营美妆一店"
    merchant_names[1] = "自营美妆二店"
    product_names = [
        _text(f"{_as_fake(fake.word())}-{product_id}", 128)
        for product_id in range(1, PRODUCT_COUNT + 1)
    ]
    coupon_names = [_text(_as_fake(fake.word()), 64) for _ in range(COUPON_COUNT)]

    rows: dict[str, list[tuple[object, ...]]] = {name: [] for name in TABLE_NAMES}
    for level_id, level_name, discount_rate in LEVELS:
        rows["t_user_level"].append(_row(level_id, level_name, discount_rate))
    for region_id, (region_name, province_name) in enumerate(REGIONS, start=1):
        rows["t_region"].append(_row(region_id, region_name, province_name))

    shanghai = _province_id("上海")
    jiangsu = _province_id("江苏")
    for user_id in range(1, USER_COUNT + 1):
        created_at = datetime(2024, 1, 1) + timedelta(minutes=user_id)
        rows["t_user"].append(_row(user_id, usernames[user_id - 1], _level_id(user_id), created_at))
        rows["t_user_region_map"].append(
            _row(user_id, user_id, _region_for_user(user_id, shanghai), addresses[user_id - 1])
        )
    rows["t_user_region_map"].append(_row(USER_COUNT + 1, 1, jiangsu, extra_address))

    for merchant_id, name in enumerate(merchant_names, start=1):
        rows["t_merchant"].append(_row(merchant_id, name, _self_operated(merchant_id)))
    for index, name in enumerate(ROOT_CATEGORIES, start=1):
        rows["t_category"].append(_row(index, name, 0))
    for index, name in enumerate(LEAF_CATEGORIES):
        rows["t_category"].append(_row(BEAUTY_CATEGORY_ID + index, name, 1 + index % 10))

    products: dict[int, tuple[int, int, Decimal]] = {}
    for product_id, name in enumerate(product_names, start=1):
        merchant_id, group = _product_location(product_id)
        category_id = category_for(merchant_id, group)
        price = product_price(product_id)
        products[product_id] = (category_id, merchant_id, price)
        rows["t_product"].append(_row(product_id, name, category_id, merchant_id, price))

    for coupon_id, name in enumerate(coupon_names, start=1):
        coupon_type = FULL_REDUCTION if coupon_id <= FULL_REDUCTION_COUPONS else DISCOUNT
        minimum = Decimal(coupon_id % 5 * 10).quantize(MONEY)
        rows["t_coupon"].append(_row(coupon_id, name, coupon_type, minimum))

    promo_pairs = _promo_pairs()
    for rel_id, (product_id, coupon_id) in enumerate(sorted(promo_pairs), start=1):
        rows["t_promo_sku_rel"].append(_row(rel_id, product_id, coupon_id))

    detail_id = 1
    rel_id = 1
    for order_id in range(1, ORDER_COUNT + 1):
        chosen: list[int]
        quantities: tuple[int, ...]
        applied_coupon: int | None
        discount: Decimal
        if order_id <= COHORT_ORDERS:
            _order_id, user_id, merchant_id = COHORT[order_id - 1]
            chosen = group_product_ids(merchant_id, 0)[:2]
            quantities = (1, 2)
            created_at = datetime(2026, 9, 10, 9, 0, 0) + timedelta(hours=order_id)
            status = PAID
            applied_coupon = 1
            discount = COHORT_DISCOUNT
        else:
            # 随机数消费顺序固定，不能在分支之间重排。
            merchant_id = rng.randrange(1, MERCHANT_COUNT + 1)
            group = rng.randrange(GROUPS_PER_MERCHANT)
            user_id = rng.randrange(1, USER_COUNT + 1)
            created_at = RANDOM_START + timedelta(minutes=rng.randrange(SPAN_MINUTES))
            status = PAID if rng.randrange(10) < 7 else CANCELLED
            line_count = 2 if order_id <= TWO_DETAIL_ORDERS else 3
            chosen = rng.sample(group_product_ids(merchant_id, group), line_count)
            quantities = tuple(rng.randrange(1, 4) for _ in range(line_count))
            if rng.randrange(2) == 0:
                applied_coupon = rng.randrange(1, COUPON_COUNT + 1)
                discount = Decimal(rng.randrange(0, 21))
            else:
                applied_coupon = None
                discount = Decimal(0)
        line_amounts: list[Decimal] = []
        for product_id, quantity in zip(chosen, quantities, strict=True):
            price = products[product_id][2]
            line_amounts.append((price * Decimal(quantity)).quantize(MONEY))
            rows["t_order_detail"].append(_row(detail_id, order_id, product_id, quantity, price))
            detail_id += 1
        gross = sum(line_amounts, Decimal("0.00"))
        if order_id > COHORT_ORDERS:
            discount = (gross * discount / Decimal(100)).quantize(MONEY)
        if discount > gross:
            discount = gross
        total = (gross - discount).quantize(MONEY)
        rows["t_order"].append(_row(order_id, user_id, total, status, created_at))
        if applied_coupon is not None:
            rows["t_order_coupon_rel"].append(_row(rel_id, order_id, applied_coupon, discount))
            rel_id += 1
    return rows


def _complex_orders(
    orders: Mapping[int, tuple[int, Decimal, str, datetime]],
    users: Mapping[int, int],
    levels: Mapping[int, str],
    user_regions: Mapping[int, Sequence[int]],
    regions: Mapping[int, str],
    details: Mapping[int, Sequence[tuple[int, int, Decimal]]],
    products: Mapping[int, tuple[int, int, Decimal]],
    categories: Mapping[int, tuple[str, int]],
    merchants: Mapping[int, bool],
    rels: Mapping[int, Sequence[tuple[int, Decimal]]],
    coupons: Mapping[int, str],
) -> list[tuple[int, int]]:
    matched: list[tuple[int, int]] = []
    for order_id, (user_id, _total, status, created_at) in orders.items():
        if status != PAID or not (LAST_MONTH_START <= created_at < LAST_MONTH_END):
            continue
        if levels[users[user_id]] not in {"VIP3", "VIP4", "VIP5"}:
            continue
        if not any(regions[region_id] == "华东" for region_id in user_regions[user_id]):
            continue
        order_details = details[order_id]
        merchant_ids = {products[product_id][1] for product_id, _quantity, _price in order_details}
        category_ids = {products[product_id][0] for product_id, _quantity, _price in order_details}
        if len(merchant_ids) != 1 or len(category_ids) != 1:
            continue
        merchant_id = next(iter(merchant_ids))
        category_id = next(iter(category_ids))
        if categories[category_id][0] != BEAUTY_NAME or not merchants[merchant_id]:
            continue
        if not any(coupons[coupon_id] == FULL_REDUCTION for coupon_id, _amount in rels[order_id]):
            continue
        matched.append((order_id, merchant_id))
    return matched


def _promo_pairs() -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for merchant_id in (1, 2):
        for product_id in group_product_ids(merchant_id, 0):
            pairs.add((product_id, 1))
    for coupon_id in range(1, COUPON_COUNT + 1):
        for offset in range(20):
            product_id = (coupon_id - 1) * 20 + offset
            pairs.add((product_id % PRODUCT_COUNT + 1, coupon_id))
    return pairs


def _product_location(product_id: int) -> tuple[int, int]:
    index = product_id - 1
    merchant_id = index // PRODUCTS_PER_MERCHANT + 1
    group = (index % PRODUCTS_PER_MERCHANT) // PRODUCTS_PER_GROUP
    return merchant_id, group


def _level_id(user_id: int) -> int:
    if user_id <= COHORT_ORDERS:
        return 3 + (user_id - 1) % 3
    return (user_id - 1) % 5 + 1


def _region_for_user(user_id: int, shanghai: int) -> int:
    if user_id <= COHORT_ORDERS:
        return shanghai
    return (user_id - 1) % len(REGIONS) + 1


def _self_operated(merchant_id: int) -> bool:
    return merchant_id in {1, 2} or merchant_id % 17 == 0


def _province_id(province: str) -> int:
    for index, (_region_name, name) in enumerate(REGIONS, start=1):
        if name == province:
            return index
    raise KeyError(province)


def _check_scale() -> None:
    if len(ROOT_CATEGORIES) + len(LEAF_CATEGORIES) != CATEGORY_COUNT:
        raise RuntimeError("category scale drifted")
    if LEAF_CATEGORIES[0] != BEAUTY_NAME:
        raise RuntimeError("beauty category drifted")
    if len({name for name, _province in REGIONS}) != 6 or len(REGIONS) != 31:
        raise RuntimeError("region scale drifted")
    if MERCHANT_COUNT * PRODUCTS_PER_MERCHANT != PRODUCT_COUNT:
        raise RuntimeError("product scale drifted")
    if PRODUCTS_PER_GROUP * GROUPS_PER_MERCHANT != PRODUCTS_PER_MERCHANT:
        raise RuntimeError("product group scale drifted")
    if TWO_DETAIL_ORDERS * 2 + (ORDER_COUNT - TWO_DETAIL_ORDERS) * 3 != DETAIL_COUNT:
        raise RuntimeError("detail scale drifted")
    if len(COHORT) != COHORT_ORDERS or COHORT_ORDERS > TWO_DETAIL_ORDERS:
        raise RuntimeError("cohort scale drifted")


def _assert_primary_keys(name: str, records: Sequence[Sequence[object]]) -> None:
    keys = [_as_int(record[0]) for record in records]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError(f"{name} primary keys are not strictly increasing")


def _text(value: str, limit: int) -> str:
    cleaned = " ".join(value.split())
    if cleaned == "":
        cleaned = "未命名"
    return cleaned[:limit]


def _as_fake(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("faker returned a non-string")
    return value


def _row(*values: object) -> tuple[object, ...]:
    return values


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(type(value).__name__)
    return value


def _as_str(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(type(value).__name__)
    return value


def _as_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError(type(value).__name__)
    return value


def _as_decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(type(value).__name__)
    return value.quantize(MONEY)


def _as_datetime(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise TypeError("expected a naive datetime")
    return value
