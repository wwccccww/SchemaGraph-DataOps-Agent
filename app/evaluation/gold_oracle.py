"""用造数行独立计算自建 Gold 结果。

这里不读取、不改写 Gold SQL。问句里的品类默认只匹配该节点；
末级品类定稿为 parent_id 不等于 0；VIP3以上定稿为 VIP3、VIP4、VIP5；
上个月按锚点日 2026-10-01 展开为 [2026-09-01, 2026-10-01)。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.db.seed_data import SEED, SeedDataset, build_dataset
from app.evaluation.ex import canonical_cell
from app.schemas.benchmark import (
    BenchmarkCase,
    OracleRecord,
    SemanticContract,
    TimeWindow,
)

ATTESTATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "custom_ecommerce"
    / "oracle_attestation.json"
)
_ANCHOR = "2026-10-01"
_SEP = ("2026-09-01 00:00:00", "2026-10-01 00:00:00")
_YEAR = ("2026-01-01 00:00:00", "2026-10-01 00:00:00")
_VIP3 = ("VIP3", "VIP4", "VIP5")
_GROUP_LABELS = {
    frozenset(
        ("美妆", "护肤", "彩妆", "香水", "手机", "电脑", "耳机", "相机", "男装", "女装")
    ): "个护数码",
    frozenset(
        ("零食", "饮料", "生鲜", "粮油", "家具", "灯具", "收纳", "厨具", "冰箱", "洗衣机")
    ): "食品家居",
}
_DATASET: SeedDataset | None = None


def dataset() -> SeedDataset:
    """返回种子 20261001 的内存行。同一进程只生成一次。"""

    global _DATASET
    if _DATASET is None:
        _DATASET = build_dataset(SEED)
    return _DATASET


def result_digest(rows: list[tuple[object, ...]], *, order_sensitive: bool) -> str:
    """按 Execution Accuracy 的单元格规则计算摘要。"""

    materialized = [tuple(canonical_cell(cell) for cell in row) for row in rows]
    if not order_sensitive:
        materialized.sort()
    payload = json.dumps(materialized, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def contract_for(case: BenchmarkCase) -> SemanticContract:
    """从问句和已定稿的投影生成语义契约。"""

    return _interpret(case).contract


def oracle_rows(case: BenchmarkCase, source: SeedDataset | None = None) -> list[tuple[object, ...]]:
    """返回独立 Oracle 的结果行。"""

    return list(_interpret(case, source or dataset()).rows)


def attestation_document(cases: list[BenchmarkCase]) -> dict[str, object]:
    """把已经与 Gold SQL 执行对账过的 Oracle 摘要固化下来。"""

    records: dict[str, object] = {}
    for case in cases:
        if case.oracle is None:
            raise ValueError(f"{case.id} 缺少 Oracle")
        records[case.id] = {
            "method": case.oracle.method,
            "result_digest": case.oracle.result_digest,
            "row_count": case.oracle.row_count,
            "reviewer_ids": ["python-dataset", "gold-sql-execution"],
            "status": "oracle_matched",
        }
    return {
        "snapshot": dataset().digest,
        "benchmark_version": "ecommerce-v1",
        "status": "oracle_matched",
        "cases": records,
    }


def ensure_oracle_matched(cases: list[BenchmarkCase], path: Path | None = None) -> None:
    """正式 EX 只有在 132 条都已与数据库结果对账后才能启动。"""

    document = json.loads((path or ATTESTATION_PATH).read_text(encoding="utf-8"))
    if document.get("status") != "oracle_matched":
        raise RuntimeError("自建 Gold 尚未达到 oracle_matched，拒绝启动正式 EX")
    if document.get("snapshot") != dataset().digest:
        raise RuntimeError("Oracle 摘要与当前造数快照不一致，拒绝启动正式 EX")
    stored = document.get("cases")
    if not isinstance(stored, dict) or len(stored) != len(cases):
        raise RuntimeError("Oracle 摘要没有覆盖全部自建用例，拒绝启动正式 EX")
    for case in cases:
        item = stored.get(case.id)
        if case.oracle is None or not isinstance(item, dict):
            raise RuntimeError(f"{case.id} 缺少 Oracle 对账记录，拒绝启动正式 EX")
        if (
            item.get("status") != "oracle_matched"
            or item.get("result_digest") != case.oracle.result_digest
        ):
            raise RuntimeError(f"{case.id} 的 Oracle 摘要已过期，拒绝启动正式 EX")


def oracle_record(case: BenchmarkCase, source: SeedDataset | None = None) -> OracleRecord:
    """生成尚未与数据库执行对账的 Oracle 记录。"""

    rows = oracle_rows(case, source)
    return OracleRecord(
        method="python",
        result_digest=result_digest(rows, order_sensitive=case.order_sensitive),
        row_count=len(rows),
        reviewer_ids=["python-dataset"],
        status="contract_checked",
    )


class _View:
    def __init__(self, source: SeedDataset) -> None:
        rows = source.rows
        self.levels = {_as_int(row[0]): (str(row[1]), row[2]) for row in rows["t_user_level"]}
        self.level_by_name = {name: level_id for level_id, (name, _) in self.levels.items()}
        self.regions = {_as_int(row[0]): (str(row[1]), str(row[2])) for row in rows["t_region"]}
        self.users = {_as_int(row[0]): _as_int(row[2]) for row in rows["t_user"]}
        self.user_regions: dict[int, set[int]] = defaultdict(set)
        for row in rows["t_user_region_map"]:
            self.user_regions[_as_int(row[1])].add(_as_int(row[2]))
        self.merchants = {
            _as_int(row[0]): (str(row[1]), bool(row[2])) for row in rows["t_merchant"]
        }
        self.categories = {
            _as_int(row[0]): (str(row[1]), _as_int(row[2])) for row in rows["t_category"]
        }
        self.products = {
            _as_int(row[0]): (str(row[1]), _as_int(row[2]), _as_int(row[3]), row[4])
            for row in rows["t_product"]
        }
        self.coupons = {_as_int(row[0]): (str(row[1]), str(row[2])) for row in rows["t_coupon"]}
        self.orders = {
            _as_int(row[0]): (_as_int(row[1]), _as_decimal(row[2]), str(row[3]), row[4])
            for row in rows["t_order"]
        }
        self.order_coupons: dict[int, set[int]] = defaultdict(set)
        for row in rows["t_order_coupon_rel"]:
            self.order_coupons[_as_int(row[1])].add(_as_int(row[2]))
        self.details: dict[int, list[tuple[int, int, int, Decimal]]] = defaultdict(list)
        for row in rows["t_order_detail"]:
            self.details[_as_int(row[1])].append(
                (_as_int(row[0]), _as_int(row[2]), _as_int(row[3]), _as_decimal(row[4]))
            )
        self.promo = {(_as_int(row[1]), _as_int(row[2])) for row in rows["t_promo_sku_rel"]}

    def region_ids(self, name: str) -> set[int]:
        return {region_id for region_id, item in self.regions.items() if item[0] == name}

    def user_in_region(self, user_id: int, region: str) -> bool:
        return bool(self.user_regions[user_id] & self.region_ids(region))


class _Answer:
    def __init__(self, contract: SemanticContract, rows: Sequence[tuple[object, ...]]) -> None:
        self.contract = contract
        self.rows = rows


def _interpret(case: BenchmarkCase, source: SeedDataset | None = None) -> _Answer:
    question = case.question
    view = _View(source) if source is not None else None
    for pattern, builder in _ROUTES:
        matched = pattern.search(question)
        if matched:
            return builder(case, matched, view)
    raise ValueError(f"问句没有独立 Oracle：{case.id} {question}")


def _contract(
    case: BenchmarkCase,
    *,
    group_keys: list[str],
    filters: list[str],
    window: tuple[str, str] | None = None,
    dedup_key: str | None = None,
) -> SemanticContract:
    return SemanticContract(
        projections=list(case.expected_columns),
        group_keys=group_keys,
        filters=[*filters, "品类名称只匹配当前节点，不包含子品类"],
        category_scope="exact",
        time_window=None
        if window is None
        else TimeWindow(start=window[0], end=window[1], anchor_date=case.anchor_date),
        dedup_key=dedup_key,  # type: ignore[arg-type]
    )


def _as_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise TypeError("seed cell must be int")


def _as_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    raise TypeError("seed cell must be Decimal")


def _window_of(year: int, month: int) -> tuple[str, str]:
    start = f"{year:04d}-{month:02d}-01 00:00:00"
    end = (
        f"{year + 1:04d}-01-01 00:00:00"
        if month == 12
        else f"{year:04d}-{month + 1:02d}-01 00:00:00"
    )
    return start, end


def _parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _in_window(moment: object, window: tuple[str, str]) -> bool:
    if not isinstance(moment, datetime):
        raise TypeError("order created_at must be datetime")
    return _parse_time(window[0]) <= moment < _parse_time(window[1])


def _categories(text: str) -> tuple[str, ...]:
    body = text.replace("或", "、")
    return tuple(part for part in body.split("、") if part)


def _routes() -> list[tuple[re.Pattern[str], _Route]]:
    return _ROUTES


_Route = Callable[[BenchmarkCase, re.Match[str], _View | None], _Answer]


def _levels(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(case, group_keys=[], filters=["返回全部会员等级，并按等级编号升序"])
    if view is None:
        return _Answer(contract, [])
    rows = [
        (level_id, name, discount) for level_id, (name, discount) in sorted(view.levels.items())
    ]
    return _Answer(contract, rows)


def _one_level(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    level = match.group(1)
    contract = _contract(case, group_keys=[], filters=[f"level_name = {level}", "按等级编号升序"])
    if view is None:
        return _Answer(contract, [])
    level_id = view.level_by_name[level]
    name, discount = view.levels[level_id]
    return _Answer(contract, [(level_id, name, discount)])


def _users_per_level(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=["level_name"],
        filters=["按会员等级回显名称", "没有用户的等级不出现"],
    )
    if view is None:
        return _Answer(contract, [])
    counts: dict[int, int] = defaultdict(int)
    for level_id in view.users.values():
        counts[level_id] += 1
    rows = [(view.levels[level_id][0], count) for level_id, count in sorted(counts.items())]
    return _Answer(contract, rows)


def _users_of_level(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    level = match.group(1)
    contract = _contract(
        case,
        group_keys=["level_name"],
        filters=[f"level_name = {level}", "回显会员等级名称"],
    )
    if view is None:
        return _Answer(contract, [])
    level_id = view.level_by_name[level]
    count = sum(1 for item in view.users.values() if item == level_id)
    if count == 0:
        return _Answer(contract, [])
    return _Answer(contract, [(level, count)])


def _beauty_products(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=[],
        filters=["category_name = 美妆", "商家为自营", "投影商品编号、商品名称和商家名称"],
    )
    if view is None:
        return _Answer(contract, [])
    rows: list[tuple[object, ...]] = []
    for product_id, (name, category_id, merchant_id, _price) in view.products.items():
        if view.categories[category_id][0] != "美妆":
            continue
        merchant_name, self_operated = view.merchants[merchant_id]
        if self_operated:
            rows.append((product_id, name, merchant_name))
    return _Answer(contract, rows)


def _provinces(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    region = match.group(1)
    contract = _contract(case, group_keys=[], filters=[f"region_name = {region}", "按省份名称升序"])
    if view is None:
        return _Answer(contract, [])
    names = [item[1] for item in view.regions.values() if item[0] == region]
    return _Answer(contract, [(name,) for name in sorted(names)])


def _month_orders(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    month = int(match.group(1))
    label = match.group(2)
    status = "PAID" if label == "已支付" else "CANCELLED"
    window = _window_of(2026, month)
    month_text = window[0][:7]
    contract = _contract(
        case,
        group_keys=[],
        filters=[f"order_month = {month_text}", f"order_status = {status}", "回显月份和状态常量"],
        window=window,
    )
    if view is None:
        return _Answer(contract, [])
    count = sum(
        1
        for _user, _total, order_status, created in view.orders.values()
        if order_status == status and _in_window(created, window)
    )
    return _Answer(contract, [(month_text, status, count)])


def _product_count(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    category = match.group(1)
    contract = _contract(
        case,
        group_keys=["category_name"],
        filters=[f"category_name = {category}", "回显品类名称"],
    )
    if view is None:
        return _Answer(contract, [])
    count = sum(
        1
        for _name, category_id, _merchant, _price in view.products.values()
        if view.categories[category_id][0] == category
    )
    return _Answer(contract, [(category, count)])


def _coupon_count(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    label = match.group(1)
    coupon_type = "full_reduction" if label == "满减" else "discount"
    contract = _contract(
        case,
        group_keys=[],
        filters=[f"coupon_type = {coupon_type}", "回显券类型常量"],
    )
    if view is None:
        return _Answer(contract, [])
    count = sum(1 for _name, item in view.coupons.values() if item == coupon_type)
    return _Answer(contract, [(coupon_type, count)])


def _full_coupons(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=[],
        filters=["coupon_type = full_reduction", "按优惠券编号升序", "回显编号和名称"],
    )
    if view is None:
        return _Answer(contract, [])
    rows = [
        (coupon_id, name)
        for coupon_id, (name, coupon_type) in sorted(view.coupons.items())
        if coupon_type == "full_reduction"
    ]
    return _Answer(contract, rows)


def _merchant_count(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    self_operated = match.group(1) == "自营"
    kind = "self_operated" if self_operated else "third_party"
    contract = _contract(
        case, group_keys=[], filters=[f"is_self_operated = {self_operated}", "回显商家类型常量"]
    )
    if view is None:
        return _Answer(contract, [])
    count = sum(1 for _name, flag in view.merchants.values() if flag is self_operated)
    return _Answer(contract, [(kind, count)])


def _self_merchants(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=[],
        filters=["is_self_operated = true", "按商家名称升序", "回显商家编号和名称"],
    )
    if view is None:
        return _Answer(contract, [])
    rows = [(merchant_id, name) for merchant_id, (name, flag) in view.merchants.items() if flag]
    rows.sort(key=lambda item: str(item[1]))
    return _Answer(contract, rows)


def _root_categories(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=[],
        filters=["一级品类定义为 parent_id = 0", "按品类编号升序", "回显品类编号和名称"],
    )
    if view is None:
        return _Answer(contract, [])
    rows = [
        (category_id, name)
        for category_id, (name, parent_id) in sorted(view.categories.items())
        if parent_id == 0
    ]
    return _Answer(contract, rows)


def _leaf_count(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=[],
        filters=["末级品类定义为 parent_id <> 0", "回显 category_kind = leaf"],
    )
    if view is None:
        return _Answer(contract, [])
    count = sum(1 for _name, parent_id in view.categories.values() if parent_id != 0)
    return _Answer(contract, [("leaf", count)])


def _user_orders(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    user_id = int(match.group(1))
    contract = _contract(
        case,
        group_keys=["user_id"],
        filters=[f"user_id = {user_id}", "回显用户编号"],
    )
    if view is None:
        return _Answer(contract, [])
    count = sum(1 for owner, _total, _status, _created in view.orders.values() if owner == user_id)
    if count == 0:
        return _Answer(contract, [])
    return _Answer(contract, [(user_id, count)])


def _detail_rows(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    category = match.group(1)
    contract = _contract(
        case,
        group_keys=["category_name"],
        filters=[f"category_name = {category}", "按订单明细行计数", "回显品类名称"],
    )
    if view is None:
        return _Answer(contract, [])
    count = 0
    for lines in view.details.values():
        for _detail, product_id, _quantity, _price in lines:
            category_id = view.products[product_id][1]
            if view.categories[category_id][0] == category:
                count += 1
    return _Answer(contract, [(category, count)])


def _vip_group_quantity(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=["level_name"],
        filters=[
            "order_status = PAID",
            "category_name = 美妆",
            "level_name IN VIP3、VIP4、VIP5",
            "按会员等级回显",
        ],
        window=_SEP,
    )
    if view is None:
        return _Answer(contract, [])
    return _Answer(contract, _quantity_by_level(view, set(_VIP3), "美妆", _SEP))


def _one_vip_quantity(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    level = match.group(1)
    category = match.group(2)
    contract = _contract(
        case,
        group_keys=["level_name", "category_name"],
        filters=[
            "order_status = PAID",
            f"level_name = {level}",
            f"category_name = {category}",
            "回显会员等级和品类",
        ],
        window=_SEP,
    )
    if view is None:
        return _Answer(contract, [])
    totals = _quantity_rows(view, {level}, {category}, _SEP, self_operated=None)
    return _Answer(contract, [(level, category, total) for _level, _category, total in totals])


def _self_coupon_orders(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=["merchant_name"],
        filters=["order_status = PAID", "coupon_type = full_reduction", "商家为自营", "按商家回显"],
        dedup_key="order_id",
    )
    if view is None:
        return _Answer(contract, [])
    grouped: dict[int, set[int]] = defaultdict(set)
    for order_id, merchant_id in _distinct_orders(
        view,
        levels=None,
        region=None,
        categories=None,
        coupon_type="full_reduction",
        window=None,
        self_operated=True,
        merchant_name=None,
        promo=False,
    ):
        grouped[merchant_id].add(order_id)
    rows = [
        (view.merchants[merchant_id][0], len(orders))
        for merchant_id, orders in sorted(grouped.items())
    ]
    return _Answer(contract, rows)


def _category_amount(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=["category_name"],
        filters=["order_status = PAID", "商家为自营", "按品类回显销售金额"],
    )
    if view is None:
        return _Answer(contract, [])
    return _Answer(contract, _amount_by_category(view, None, None, True))


def _one_category_amount(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    category = match.group(1)
    contract = _contract(
        case,
        group_keys=["category_name"],
        filters=[
            "order_status = PAID",
            "商家为自营",
            f"category_name = {category}",
            "回显品类名称",
        ],
        window=_SEP,
    )
    if view is None:
        return _Answer(contract, [])
    return _Answer(contract, _amount_by_category(view, {category}, _SEP, True))


def _region_coupon(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    region = match.group(1)
    label = match.group(2)
    coupon_type = "full_reduction" if label == "满减" else "discount"
    contract = _contract(
        case,
        group_keys=["region_name", "coupon_type"],
        filters=[
            "order_status = PAID",
            f"region_name = {region}",
            f"coupon_type = {coupon_type}",
            "回显大区和券类型",
        ],
        window=_SEP,
        dedup_key="order_id",
    )
    if view is None:
        return _Answer(contract, [])
    orders = _distinct_orders(
        view,
        levels=None,
        region=region,
        categories=None,
        coupon_type=coupon_type,
        window=_SEP,
        self_operated=None,
        merchant_name=None,
        promo=False,
    )
    return _Answer(
        contract, [(region, coupon_type, len({order_id for order_id, _merchant in orders}))]
    )


def _level_self_amount(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    level = match.group(1)
    self_operated = match.group(2) == "自营"
    contract = _contract(
        case,
        group_keys=["level_name", "is_self_operated"],
        filters=[
            "order_status = PAID",
            f"level_name = {level}",
            f"is_self_operated = {self_operated}",
            "回显等级和自营标记",
        ],
        window=_SEP,
    )
    if view is None:
        return _Answer(contract, [])
    total = Decimal("0.00")
    matched = False
    for lines in _lines(view, {level}, None, _SEP, self_operated, None, False):
        for _detail, _product, quantity, price in lines:
            matched = True
            total += (price * Decimal(quantity)).quantize(Decimal("0.01"))
    if not matched:
        return _Answer(contract, [])
    return _Answer(contract, [(level, self_operated, total)])


def _having_sales(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    month = int(match.group(1))
    window = _window_of(2026, month)
    contract = _contract(
        case,
        group_keys=["category_name"],
        filters=["order_status = PAID", "商家为自营", "销量不少于 1", "回显月份常量和品类"],
        window=window,
    )
    if view is None:
        return _Answer(contract, [])
    rows = [
        (window[0][:7], category, total)
        for category, total in _amount_or_quantity(view, window)
        if total >= 1
    ]
    return _Answer(contract, rows)


def _group_orders(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    region = match.group(1)
    names = _categories(match.group(2))
    label = _GROUP_LABELS[frozenset(names)]
    contract = _contract(
        case,
        group_keys=["merchant_name"],
        filters=[
            "order_status = PAID",
            f"region_name = {region}",
            "level_name IN VIP3、VIP4、VIP5",
            "coupon_type = full_reduction",
            "商家为自营",
            f"category_group = {label}",
            "品类集合 = " + "、".join(names),
            "回显大区、品类组和商家",
        ],
        window=_YEAR,
        dedup_key="order_id",
    )
    if view is None:
        return _Answer(contract, [])
    return _Answer(
        contract,
        _merchant_order_amounts(
            view, set(_VIP3), region, set(names), _YEAR, None, False, region, label, None
        ),
    )


def _promo_orders(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    level_text = match.group(1)
    merchant_name = match.group(2)
    levels = set(_VIP3) if "VIP3、VIP4和VIP5" in level_text else {level_text}
    contract = _contract(
        case,
        group_keys=["merchant_name"],
        filters=[
            "order_status = PAID",
            "region_name = 华东",
            "coupon_type = full_reduction",
            "category_name = 美妆",
            "商家为自营",
            "优惠券必须适用于所购商品",
            "按商家回显订单数和实付金额",
            f"levels = {'、'.join(sorted(levels))}",
            *([f"merchant_name = {merchant_name}"] if merchant_name else []),
        ],
        window=_SEP,
        dedup_key="order_id",
    )
    if view is None:
        return _Answer(contract, [])
    return _Answer(
        contract,
        _merchant_order_amounts(
            view,
            levels,
            "华东",
            {"美妆"},
            _SEP,
            merchant_name or None,
            True,
            None,
            None,
            None,
        ),
    )


def _beauty_quantity(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    region = match.group(1)
    contract = _contract(
        case,
        group_keys=["merchant_name"],
        filters=[
            "order_status = PAID",
            f"region_name = {region}",
            "VIP3以上定义为 VIP3、VIP4、VIP5",
            "category_name = 美妆",
            "商家为自营",
            "回显大区、品类和商家",
        ],
        window=_YEAR,
    )
    if view is None:
        return _Answer(contract, [])
    grouped: dict[int, int] = defaultdict(int)
    seen: set[int] = set()
    for lines, merchant_id in _detail_lines(view, set(_VIP3), region, {"美妆"}, _YEAR, True):
        for detail_id, _product, quantity, _price in lines:
            if detail_id in seen:
                continue
            seen.add(detail_id)
            grouped[merchant_id] += quantity
    rows = [
        (region, "美妆", view.merchants[merchant_id][0], total)
        for merchant_id, total in sorted(grouped.items())
    ]
    return _Answer(contract, rows)


def _east_level_orders(case: BenchmarkCase, match: re.Match[str], view: _View | None) -> _Answer:
    level = match.group(1)
    contract = _contract(
        case,
        group_keys=["merchant_name"],
        filters=[
            "order_status = PAID",
            "region_name = 华东",
            f"level_name = {level}",
            "coupon_type = full_reduction",
            "category_name = 美妆",
            "商家为自营",
            "回显等级和商家",
        ],
        window=_YEAR,
        dedup_key="order_id",
    )
    if view is None:
        return _Answer(contract, [])
    return _Answer(
        contract,
        _merchant_order_amounts(
            view, {level}, "华东", {"美妆"}, _YEAR, None, False, None, None, level
        ),
    )


def _last_month_orders(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=["merchant_name"],
        filters=[
            "上个月定义为锚点日前一个自然月",
            "region_name = 华东",
            "level_name IN VIP3、VIP4、VIP5",
            "coupon_type = full_reduction",
            "category_name = 美妆",
            "商家为自营",
            "order_status = PAID",
            "按商家回显订单数和实付金额",
        ],
        window=_SEP,
        dedup_key="order_id",
    )
    if view is None:
        return _Answer(contract, [])
    return _Answer(
        contract,
        _merchant_order_amounts(
            view, set(_VIP3), "华东", {"美妆"}, _SEP, None, False, None, None, None
        ),
    )


def _promo_names(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=[],
        filters=[
            "上个月定义为锚点日前一个自然月",
            "order_status = PAID",
            "VIP3以上定义为 VIP3、VIP4、VIP5",
            "category_name = 美妆",
            "商家为自营",
            "coupon_type = full_reduction",
            "优惠券必须适用于所购商品",
            "返回商家、商品和优惠券的不重复组合",
        ],
        window=_SEP,
    )
    if view is None:
        return _Answer(contract, [])
    found: set[tuple[str, str, str]] = set()
    for order_id, (user_id, _total, status, created) in view.orders.items():
        if status != "PAID" or not _in_window(created, _SEP):
            continue
        if view.levels[view.users[user_id]][0] not in _VIP3:
            continue
        for coupon_id in view.order_coupons[order_id]:
            coupon_name, coupon_type = view.coupons[coupon_id]
            if coupon_type != "full_reduction":
                continue
            for _detail, product_id, _quantity, _price in view.details[order_id]:
                product_name, category_id, merchant_id, _product_price = view.products[product_id]
                if view.categories[category_id][0] != "美妆" or not view.merchants[merchant_id][1]:
                    continue
                if (product_id, coupon_id) in view.promo:
                    found.add((view.merchants[merchant_id][0], product_name, coupon_name))
    return _Answer(contract, list(found))


def _last_month_quantity(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=["merchant_name"],
        filters=[
            "上个月定义为锚点日前一个自然月",
            "region_name = 华东",
            "VIP3以上定义为 VIP3、VIP4、VIP5",
            "category_name = 美妆",
            "商家为自营",
            "order_status = PAID",
            "按商家回显购买数量",
        ],
        window=_SEP,
    )
    if view is None:
        return _Answer(contract, [])
    grouped: dict[int, int] = defaultdict(int)
    seen: set[int] = set()
    for lines, merchant_id in _detail_lines(view, set(_VIP3), "华东", {"美妆"}, _SEP, True):
        for detail_id, _product, quantity, _price in lines:
            if detail_id in seen:
                continue
            seen.add(detail_id)
            grouped[merchant_id] += quantity
    return _Answer(
        contract,
        [(view.merchants[merchant_id][0], total) for merchant_id, total in sorted(grouped.items())],
    )


def _last_month_promo(case: BenchmarkCase, _match: re.Match[str], view: _View | None) -> _Answer:
    contract = _contract(
        case,
        group_keys=["merchant_name"],
        filters=[
            "上个月定义为锚点日前一个自然月",
            "region_name = 华东",
            "VIP3以上定义为 VIP3、VIP4、VIP5",
            "coupon_type = full_reduction",
            "category_name = 美妆",
            "商家为自营",
            "order_status = PAID",
            "优惠券必须适用于所购商品",
            "按商家回显订单数和实付金额",
        ],
        window=_SEP,
        dedup_key="order_id",
    )
    if view is None:
        return _Answer(contract, [])
    return _Answer(
        contract,
        _merchant_order_amounts(
            view, set(_VIP3), "华东", {"美妆"}, _SEP, None, True, None, None, None
        ),
    )


def _quantity_by_level(
    view: _View,
    levels: set[str],
    category: str,
    window: tuple[str, str],
) -> list[tuple[object, ...]]:
    totals: dict[str, int] = defaultdict(int)
    for order_id, (user_id, _total, status, created) in view.orders.items():
        if status != "PAID" or not _in_window(created, window):
            continue
        level = view.levels[view.users[user_id]][0]
        if level not in levels:
            continue
        for _detail, product_id, quantity, _price in view.details[order_id]:
            category_id = view.products[product_id][1]
            if view.categories[category_id][0] == category:
                totals[level] += quantity
    return [(level, total) for level, total in sorted(totals.items())]


def _quantity_rows(
    view: _View,
    levels: set[str],
    categories: set[str],
    window: tuple[str, str],
    *,
    self_operated: bool | None,
) -> list[tuple[object, ...]]:
    total = 0
    for lines in _lines(view, levels, categories, window, self_operated, None, False):
        for _detail, product_id, quantity, _price in lines:
            if view.categories[view.products[product_id][1]][0] in categories:
                total += quantity
    level = next(iter(levels))
    category = next(iter(categories))
    return [(level, category, total)] if total else []


def _amount_by_category(
    view: _View,
    categories: set[str] | None,
    window: tuple[str, str] | None,
    self_operated: bool,
) -> list[tuple[object, ...]]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for order_id, (_user, _total, status, created) in view.orders.items():
        if status != "PAID" or (window is not None and not _in_window(created, window)):
            continue
        for _detail, product_id, quantity, price in view.details[order_id]:
            product_name, category_id, merchant_id, _product_price = view.products[product_id]
            del product_name
            category = view.categories[category_id][0]
            if categories is not None and category not in categories:
                continue
            if view.merchants[merchant_id][1] is not self_operated:
                continue
            totals[category] += (price * Decimal(quantity)).quantize(Decimal("0.01"))
    return [(category, total) for category, total in sorted(totals.items())]


def _amount_or_quantity(view: _View, window: tuple[str, str]) -> list[tuple[str, int]]:
    totals: dict[str, int] = defaultdict(int)
    for order_id, (_user, _amount, status, created) in view.orders.items():
        if status != "PAID" or not _in_window(created, window):
            continue
        for _detail, product_id, quantity, _price in view.details[order_id]:
            _name, category_id, merchant_id, _product_price = view.products[product_id]
            if not view.merchants[merchant_id][1]:
                continue
            totals[view.categories[category_id][0]] += quantity
    return list(totals.items())


def _lines(
    view: _View,
    levels: set[str] | None,
    categories: set[str] | None,
    window: tuple[str, str] | None,
    self_operated: bool | None,
    merchant_name: str | None,
    promo: bool,
) -> list[list[tuple[int, int, int, Decimal]]]:
    selected: list[list[tuple[int, int, int, Decimal]]] = []
    for order_id, (user_id, _total, status, created) in view.orders.items():
        if status != "PAID":
            continue
        if window is not None and not _in_window(created, window):
            continue
        if levels is not None and view.levels[view.users[user_id]][0] not in levels:
            continue
        lines = []
        for line in view.details[order_id]:
            _detail, product_id, _quantity, _price = line
            _product_name, category_id, merchant_id, _product_price = view.products[product_id]
            if categories is not None and view.categories[category_id][0] not in categories:
                continue
            merchant, flag = view.merchants[merchant_id]
            if self_operated is not None and flag is not self_operated:
                continue
            if merchant_name is not None and merchant != merchant_name:
                continue
            if promo and not any(
                (product_id, coupon_id) in view.promo
                for coupon_id in view.order_coupons[order_id]
                if view.coupons[coupon_id][1] == "full_reduction"
            ):
                continue
            lines.append(line)
        if lines:
            selected.append(lines)
    return selected


def _detail_lines(
    view: _View,
    levels: set[str],
    region: str,
    categories: set[str],
    window: tuple[str, str],
    self_operated: bool,
) -> list[tuple[list[tuple[int, int, int, Decimal]], int]]:
    selected = []
    for order_id, (user_id, _total, status, created) in view.orders.items():
        if status != "PAID" or not _in_window(created, window):
            continue
        if view.levels[view.users[user_id]][0] not in levels or not view.user_in_region(
            user_id, region
        ):
            continue
        lines = []
        merchant_id = None
        for line in view.details[order_id]:
            _detail, product_id, _quantity, _price = line
            _name, category_id, product_merchant, _price_value = view.products[product_id]
            if view.categories[category_id][0] not in categories:
                continue
            if view.merchants[product_merchant][1] is not self_operated:
                continue
            merchant_id = product_merchant
            lines.append(line)
        if lines and merchant_id is not None:
            selected.append((lines, merchant_id))
    return selected


def _distinct_orders(
    view: _View,
    *,
    levels: set[str] | None,
    region: str | None,
    categories: set[str] | None,
    coupon_type: str | None,
    window: tuple[str, str] | None,
    self_operated: bool | None,
    merchant_name: str | None,
    promo: bool,
) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    for order_id, (user_id, _total, status, created) in view.orders.items():
        if status != "PAID":
            continue
        if window is not None and not _in_window(created, window):
            continue
        if levels is not None and view.levels[view.users[user_id]][0] not in levels:
            continue
        if region is not None and not view.user_in_region(user_id, region):
            continue
        coupons = [
            coupon_id
            for coupon_id in view.order_coupons[order_id]
            if coupon_type is None or view.coupons[coupon_id][1] == coupon_type
        ]
        if coupon_type is not None and not coupons:
            continue
        matched_merchant = None
        for _detail, product_id, _quantity, _price in view.details[order_id]:
            _name, category_id, merchant_id, _price_value = view.products[product_id]
            if categories is not None and view.categories[category_id][0] not in categories:
                continue
            merchant, flag = view.merchants[merchant_id]
            if self_operated is not None and flag is not self_operated:
                continue
            if merchant_name is not None and merchant != merchant_name:
                continue
            if promo and not any((product_id, coupon_id) in view.promo for coupon_id in coupons):
                continue
            matched_merchant = merchant_id
            break
        if categories is None and self_operated is None and merchant_name is None and not promo:
            matched_merchant = matched_merchant if matched_merchant is not None else -1
            if coupon_type is None or coupons:
                found.append((order_id, matched_merchant))
            continue
        if matched_merchant is not None and matched_merchant >= 0:
            found.append((order_id, matched_merchant))
    return found


def _merchant_order_amounts(
    view: _View,
    levels: set[str],
    region: str,
    categories: set[str],
    window: tuple[str, str],
    merchant_name: str | None,
    promo: bool,
    region_label: str | None,
    group_label: str | None,
    level_label: str | None,
) -> list[tuple[object, ...]]:
    grouped: dict[int, list[Decimal]] = defaultdict(list)
    for order_id, merchant_id in _distinct_orders(
        view,
        levels=levels,
        region=region,
        categories=categories,
        coupon_type="full_reduction",
        window=window,
        self_operated=True,
        merchant_name=merchant_name,
        promo=promo,
    ):
        grouped[merchant_id].append(view.orders[order_id][1])
    rows: list[tuple[object, ...]] = []
    for merchant_id, amounts in sorted(grouped.items()):
        total = sum(amounts, Decimal("0.00"))
        name = view.merchants[merchant_id][0]
        prefix: list[object] = []
        if level_label is not None:
            prefix.append(level_label)
        if region_label is not None:
            prefix.append(region_label)
        if group_label is not None:
            prefix.append(group_label)
        rows.append((*prefix, name, len(amounts), total))
    return rows


_ROUTES: list[tuple[re.Pattern[str], _Route]] = [
    (re.compile(r"^按等级编号升序查询全部会员等级的名称和折扣率$"), _levels),
    (re.compile(r"^按等级编号升序查询(VIP\d)会员等级的名称和折扣率$"), _one_level),
    (re.compile(r"^统计每个会员等级的用户数量$"), _users_per_level),
    (re.compile(r"^统计(VIP\d)会员等级下的用户数量$"), _users_of_level),
    (re.compile(r"^查询自营商家在售的美妆商品$"), _beauty_products),
    (re.compile(r"^按省份名称升序查询(.+)大区包含的省份$"), _provinces),
    (re.compile(r"^统计2026年(\d+)月状态为(已支付|已取消)的订单数量$"), _month_orders),
    (re.compile(r"^统计(.+)品类的在售商品数量$"), _product_count),
    (re.compile(r"^统计(满减|折扣)类型优惠券的数量$"), _coupon_count),
    (re.compile(r"^按优惠券编号升序查询全部满减优惠券的编号和名称$"), _full_coupons),
    (re.compile(r"^统计(自营|非自营)商家的数量$"), _merchant_count),
    (re.compile(r"^按商家名称升序查询全部自营商家的名称$"), _self_merchants),
    (re.compile(r"^按品类编号升序查询全部一级品类的名称$"), _root_categories),
    (re.compile(r"^统计全部末级品类的数量$"), _leaf_count),
    (re.compile(r"^统计用户编号为(\d+)的订单数量$"), _user_orders),
    (re.compile(r"^统计(.+)商品对应的订单明细行数$"), _detail_rows),
    (
        re.compile(r"^统计2026年9月已支付美妆订单中，VIP3、VIP4、VIP5用户的购买数量$"),
        _vip_group_quantity,
    ),
    (re.compile(r"^统计2026年9月已支付订单中，(VIP\d)用户购买(.+)商品的数量$"), _one_vip_quantity),
    (re.compile(r"^统计自营商家使用满减优惠券的已支付订单数$"), _self_coupon_orders),
    (re.compile(r"^统计自营商家各品类的已支付销售金额$"), _category_amount),
    (re.compile(r"^统计2026年9月自营商家(.+)品类的已支付销售金额$"), _one_category_amount),
    (re.compile(r"^统计2026年9月(.+)大区使用(满减|折扣)优惠券的已支付订单数$"), _region_coupon),
    (
        re.compile(r"^统计2026年9月(VIP\d)用户在(自营|非自营)商家的已支付销售金额$"),
        _level_self_amount,
    ),
    (re.compile(r"^统计2026年(\d+)月自营商家已支付销量不少于1件的品类和销量$"), _having_sales),
    (
        re.compile(
            r"^统计2026年1月至9月(.+)大区VIP3、VIP4和VIP5用户使用满减优惠券购买自营(.+)的已支付订单数和实付金额$"
        ),
        _group_orders,
    ),
    (
        re.compile(
            r"^统计2026年9月华东大区(.+?)用户(?:在(.+?))?使用满减优惠券购买自营美妆、且该优惠券适用于所购商品的已支付订单数和实付金额$"
        ),
        _promo_orders,
    ),
    (
        re.compile(r"^统计2026年1月至9月(.+)大区VIP3以上用户购买自营美妆的已支付商品数量$"),
        _beauty_quantity,
    ),
    (
        re.compile(
            r"^统计2026年1月至9月华东大区(VIP\d)用户使用满减优惠券购买自营美妆的已支付订单数和实付金额$"
        ),
        _east_level_orders,
    ),
    (
        re.compile(
            r"^统计上个月华东大区VIP3、VIP4、VIP5用户使用满减优惠券购买自营美妆的已支付订单数和实付金额$"
        ),
        _last_month_orders,
    ),
    (
        re.compile(
            r"^查询上个月已支付订单中，VIP3以上用户在自营美妆商品上实际使用了促销满减券的商家、商品和优惠券$"
        ),
        _promo_names,
    ),
    (
        re.compile(r"^统计上个月华东大区VIP3以上用户购买自营美妆的已支付商品数量$"),
        _last_month_quantity,
    ),
    (
        re.compile(
            r"^统计上个月华东大区VIP3以上用户使用满减优惠券购买自营美妆、且该优惠券适用于所购商品的已支付订单数和实付金额$"
        ),
        _last_month_promo,
    ),
]
