"""自建 132 条 Text-to-SQL 用例。

Gold SQL 只供评测进程读取。冻结文件由 build_custom_cases 生成，
测试要求两者一致。问题由评测作者编写，不由被测模型反写。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp

from app.evaluation.smoke import load_smoke_cases
from app.schemas.benchmark import BenchmarkCase, BenchmarkDifficulty

FULL_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "custom_ecommerce" / "full.yaml"
CUSTOM_CASE_COUNTS = {"basic": 50, "medium": 50, "complex": 32}
ANCHOR = date(2026, 10, 1)
_SEP_START = "2026-09-01 00:00:00"
_SEP_END = "2026-10-01 00:00:00"
_YEAR_START = "2026-01-01 00:00:00"
_YEAR_END = "2026-10-01 00:00:00"
_REGIONS = ("华北", "华东", "华中", "华南", "西南", "西北")
_LEVELS = ("VIP1", "VIP2", "VIP3", "VIP4", "VIP5")
_GROUP_A = ("美妆", "护肤", "彩妆", "香水", "手机", "电脑", "耳机", "相机", "男装", "女装")
_GROUP_B = ("零食", "饮料", "生鲜", "粮油", "家具", "灯具", "收纳", "厨具", "冰箱", "洗衣机")
_GROSS_CATEGORIES = (
    "美妆",
    "护肤",
    "彩妆",
    "香水",
    "手机",
    "电脑",
    "男装",
    "女装",
    "零食",
    "家具",
    "冰箱",
    "小说",
)
_PRODUCT_CATEGORIES = ("美妆", "护肤", "手机", "电脑", "男装", "零食", "家具")
_SMOKE_IDS = (
    ("smoke_basic_001", "custom_basic_001"),
    ("smoke_basic_002", "custom_basic_002"),
    ("smoke_basic_003", "custom_basic_003"),
    ("smoke_medium_001", "custom_medium_001"),
    ("smoke_medium_002", "custom_medium_002"),
    ("smoke_medium_003", "custom_medium_003"),
    ("smoke_complex_001", "custom_complex_001"),
    ("smoke_complex_002", "custom_complex_002"),
    ("smoke_complex_003", "custom_complex_003"),
    ("smoke_complex_004", "custom_complex_004"),
)


def load_custom_cases(path: Path | None = None) -> list[BenchmarkCase]:
    """读取冻结的自建用例。"""

    payload = yaml.safe_load((path or FULL_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("contract_version") != "1.0":
        raise ValueError("custom case file must declare contract_version 1.0")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("custom case file must contain a cases list")
    return [BenchmarkCase.model_validate(case) for case in cases]


def build_custom_cases() -> list[BenchmarkCase]:
    """按固定种子上已经核实非空的过滤条件生成 132 条用例。"""

    smoke = {case.id: case for case in load_smoke_cases()}
    copied = {new_id: _copy_smoke(smoke[old_id], new_id) for old_id, new_id in _SMOKE_IDS}
    basic = [copied[f"custom_basic_{index:03d}"] for index in range(1, 4)]
    basic.extend(_basic_cases())
    medium = [copied[f"custom_medium_{index:03d}"] for index in range(1, 4)]
    medium.extend(_medium_cases())
    complex_cases = [copied[f"custom_complex_{index:03d}"] for index in range(1, 5)]
    complex_cases.extend(_complex_cases())
    cases = [*basic, *medium, *complex_cases]
    if [len(basic), len(medium), len(complex_cases)] != [50, 50, 32]:
        raise RuntimeError("custom case builder drifted from 50/50/32")
    return cases


def dump_custom_cases(cases: list[BenchmarkCase]) -> str:
    """把用例写成可再次解析的 YAML。Gold SQL 使用去掉末尾换行的字面量。"""

    lines = ['contract_version: "1.0"', "cases:"]
    for case in cases:
        lines.extend(_emit_case(case))
    return "\n".join(lines) + "\n"


def referenced_tables(sql: str) -> set[str]:
    """用 SQLGlot 收集物理表。CTE 名称不算表。"""

    parsed = sqlglot.parse_one(sql, read="postgres")
    if not isinstance(parsed, exp.Expression):
        raise ValueError("gold SQL did not parse")
    cte_names = {cte.alias for cte in parsed.find_all(exp.CTE) if cte.alias}
    return {table.name for table in parsed.find_all(exp.Table) if table.name not in cte_names}


def normalize_sql(sql: str) -> str:
    """用于同文件去重的规范化 SQL。"""

    return " ".join(sql.split()).lower()


def _copy_smoke(case: BenchmarkCase, case_id: str) -> BenchmarkCase:
    return case.model_copy(update={"id": case_id, "gold_sql": case.gold_sql.strip()})


def _make(
    *,
    case_id: str,
    difficulty: BenchmarkDifficulty,
    question: str,
    gold_sql: str,
    required_tables: list[str],
    required_junctions: list[str],
    expected_columns: list[str],
    tags: list[str],
) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        source="custom",
        source_version="ecommerce-v1",
        database_id="ecommerce",
        difficulty=difficulty,
        dialect="postgres",
        question=question,
        gold_sql=gold_sql.strip(),
        required_tables=required_tables,
        required_junctions=required_junctions,
        order_sensitive="升序" in question,
        numeric_tolerance=None,
        expected_columns=expected_columns,
        anchor_date=ANCHOR,
        tags=tags,
    )


def _basic_cases() -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for offset, level in enumerate(_LEVELS, start=4):
        cases.append(
            _make(
                case_id=f"custom_basic_{offset:03d}",
                difficulty="basic",
                question=f"按等级编号升序查询{level}会员等级的名称和折扣率",
                gold_sql=(
                    "SELECT level_id, level_name, discount_rate\n"
                    "FROM t_user_level\n"
                    f"WHERE level_name = '{level}'\n"
                    "ORDER BY level_id"
                ),
                required_tables=["t_user_level"],
                required_junctions=[],
                expected_columns=["level_id", "level_name", "discount_rate"],
                tags=["dimension", "order"],
            )
        )
    for offset, level in enumerate(_LEVELS, start=9):
        cases.append(
            _make(
                case_id=f"custom_basic_{offset:03d}",
                difficulty="basic",
                question=f"统计{level}会员等级下的用户数量",
                gold_sql=(
                    "SELECT ul.level_name, COUNT(*)::bigint AS user_count\n"
                    "FROM t_user AS u\n"
                    "JOIN t_user_level AS ul ON u.user_level_id = ul.level_id\n"
                    f"WHERE ul.level_name = '{level}'\n"
                    "GROUP BY ul.level_id, ul.level_name"
                ),
                required_tables=["t_user", "t_user_level"],
                required_junctions=[],
                expected_columns=["level_name", "user_count"],
                tags=["aggregation"],
            )
        )
    for offset, region in enumerate(_REGIONS, start=14):
        cases.append(
            _make(
                case_id=f"custom_basic_{offset:03d}",
                difficulty="basic",
                question=f"按省份名称升序查询{region}大区包含的省份",
                gold_sql=(
                    "SELECT province_name\n"
                    "FROM t_region\n"
                    f"WHERE region_name = '{region}'\n"
                    "ORDER BY province_name"
                ),
                required_tables=["t_region"],
                required_junctions=[],
                expected_columns=["province_name"],
                tags=["dimension", "order"],
            )
        )
    for offset, month in enumerate(range(3, 10), start=20):
        cases.append(_month_count(offset, month, "PAID", "已支付"))
    for offset, month in enumerate(range(3, 10), start=27):
        cases.append(_month_count(offset, month, "CANCELLED", "已取消"))
    for offset, category in enumerate(_PRODUCT_CATEGORIES, start=34):
        cases.append(
            _make(
                case_id=f"custom_basic_{offset:03d}",
                difficulty="basic",
                question=f"统计{category}品类的在售商品数量",
                gold_sql=(
                    "SELECT c.category_name, COUNT(*)::bigint AS product_count\n"
                    "FROM t_product AS p\n"
                    "JOIN t_category AS c ON p.category_id = c.category_id\n"
                    f"WHERE c.category_name = '{category}'\n"
                    "GROUP BY c.category_id, c.category_name"
                ),
                required_tables=["t_product", "t_category"],
                required_junctions=[],
                expected_columns=["category_name", "product_count"],
                tags=["aggregation"],
            )
        )
    cases.append(_coupon_count(41, "full_reduction", "统计满减类型优惠券的数量"))
    cases.append(_coupon_count(42, "discount", "统计折扣类型优惠券的数量"))
    cases.append(
        _make(
            case_id="custom_basic_043",
            difficulty="basic",
            question="按优惠券编号升序查询全部满减优惠券的编号和名称",
            gold_sql=(
                "SELECT coupon_id, coupon_name\n"
                "FROM t_coupon\n"
                "WHERE coupon_type = 'full_reduction'\n"
                "ORDER BY coupon_id"
            ),
            required_tables=["t_coupon"],
            required_junctions=[],
            expected_columns=["coupon_id", "coupon_name"],
            tags=["dimension", "order"],
        )
    )
    cases.append(_merchant_count(44, "TRUE", "self_operated", "统计自营商家的数量"))
    cases.append(_merchant_count(45, "FALSE", "third_party", "统计非自营商家的数量"))
    cases.append(
        _make(
            case_id="custom_basic_046",
            difficulty="basic",
            question="按商家名称升序查询全部自营商家的名称",
            gold_sql=(
                "SELECT merchant_id, merchant_name\n"
                "FROM t_merchant\n"
                "WHERE is_self_operated IS TRUE\n"
                "ORDER BY merchant_name"
            ),
            required_tables=["t_merchant"],
            required_junctions=[],
            expected_columns=["merchant_id", "merchant_name"],
            tags=["dimension", "order"],
        )
    )
    cases.append(
        _make(
            case_id="custom_basic_047",
            difficulty="basic",
            question="按品类编号升序查询全部一级品类的名称",
            gold_sql=(
                "SELECT category_id, category_name\n"
                "FROM t_category\n"
                "WHERE parent_id = 0\n"
                "ORDER BY category_id"
            ),
            required_tables=["t_category"],
            required_junctions=[],
            expected_columns=["category_id", "category_name"],
            tags=["dimension", "order"],
        )
    )
    cases.append(
        _make(
            case_id="custom_basic_048",
            difficulty="basic",
            question="统计全部末级品类的数量",
            gold_sql=(
                "SELECT 'leaf' AS category_kind, COUNT(*)::bigint AS category_count\n"
                "FROM t_category\n"
                "WHERE parent_id <> 0"
            ),
            required_tables=["t_category"],
            required_junctions=[],
            expected_columns=["category_kind", "category_count"],
            tags=["aggregation"],
        )
    )
    cases.append(
        _make(
            case_id="custom_basic_049",
            difficulty="basic",
            question="统计用户编号为1的订单数量",
            gold_sql=(
                "SELECT u.user_id, COUNT(*)::bigint AS order_count\n"
                "FROM t_order AS o\n"
                "JOIN t_user AS u ON o.user_id = u.user_id\n"
                "WHERE u.user_id = 1\n"
                "GROUP BY u.user_id"
            ),
            required_tables=["t_order", "t_user"],
            required_junctions=[],
            expected_columns=["user_id", "order_count"],
            tags=["aggregation"],
        )
    )
    cases.append(
        _make(
            case_id="custom_basic_050",
            difficulty="basic",
            question="统计美妆商品对应的订单明细行数",
            gold_sql=(
                "SELECT c.category_name, COUNT(*)::bigint AS detail_count\n"
                "FROM t_order_detail AS od\n"
                "JOIN t_product AS p ON od.product_id = p.product_id\n"
                "JOIN t_category AS c ON p.category_id = c.category_id\n"
                "WHERE c.category_name = '美妆'\n"
                "GROUP BY c.category_id, c.category_name"
            ),
            required_tables=["t_order_detail", "t_product", "t_category"],
            required_junctions=[],
            expected_columns=["category_name", "detail_count"],
            tags=["aggregation"],
        )
    )
    return cases


def _month_count(index: int, month: int, status: str, status_label: str) -> BenchmarkCase:
    start, end = _month_bounds(2026, month)
    return _make(
        case_id=f"custom_basic_{index:03d}",
        difficulty="basic",
        question=f"统计2026年{month}月状态为{status_label}的订单数量",
        gold_sql=(
            "SELECT "
            f"'{start[:7]}' AS order_month, '{status}' AS order_status, "
            "COUNT(*)::bigint AS order_count\n"
            "FROM t_order\n"
            f"WHERE order_status = '{status}'\n"
            f"  AND created_at >= TIMESTAMP '{start}'\n"
            f"  AND created_at < TIMESTAMP '{end}'"
        ),
        required_tables=["t_order"],
        required_junctions=[],
        expected_columns=["order_month", "order_status", "order_count"],
        tags=["aggregation", "time-window"],
    )


def _coupon_count(index: int, coupon_type: str, question: str) -> BenchmarkCase:
    return _make(
        case_id=f"custom_basic_{index:03d}",
        difficulty="basic",
        question=question,
        gold_sql=(
            f"SELECT '{coupon_type}' AS coupon_type, COUNT(*)::bigint AS coupon_count\n"
            "FROM t_coupon\n"
            f"WHERE coupon_type = '{coupon_type}'"
        ),
        required_tables=["t_coupon"],
        required_junctions=[],
        expected_columns=["coupon_type", "coupon_count"],
        tags=["aggregation"],
    )


def _merchant_count(index: int, flag: str, kind: str, question: str) -> BenchmarkCase:
    return _make(
        case_id=f"custom_basic_{index:03d}",
        difficulty="basic",
        question=question,
        gold_sql=(
            f"SELECT '{kind}' AS merchant_kind, COUNT(*)::bigint AS merchant_count\n"
            "FROM t_merchant\n"
            f"WHERE is_self_operated IS {flag}"
        ),
        required_tables=["t_merchant"],
        required_junctions=[],
        expected_columns=["merchant_kind", "merchant_count"],
        tags=["aggregation"],
    )


def _medium_cases() -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    index = 4
    for level in _LEVELS:
        for category in ("美妆", "护肤", "手机"):
            cases.append(_level_category_quantity(index, level, category))
            index += 1
    for category in _GROSS_CATEGORIES:
        cases.append(_self_category_amount(index, category))
        index += 1
    for region in _REGIONS:
        cases.append(_region_coupon(index, region, "full_reduction", "满减"))
        index += 1
    for region in ("华东", "华北"):
        cases.append(_region_coupon(index, region, "discount", "折扣"))
        index += 1
    for level in ("VIP1", "VIP2", "VIP3", "VIP4"):
        cases.append(_level_self_amount(index, level, self_operated=True))
        index += 1
        cases.append(_level_self_amount(index, level, self_operated=False))
        index += 1
    for month in (6, 7, 8, 9):
        cases.append(_having_month(index, month))
        index += 1
    return cases


def _level_category_quantity(index: int, level: str, category: str) -> BenchmarkCase:
    return _make(
        case_id=f"custom_medium_{index:03d}",
        difficulty="medium",
        question=(f"统计2026年9月已支付订单中，{level}用户购买{category}商品的数量"),
        gold_sql=(
            "SELECT ul.level_name, c.category_name, "
            "SUM(od.quantity)::bigint AS total_quantity\n"
            "FROM t_order AS o\n"
            "JOIN t_user AS u ON o.user_id = u.user_id\n"
            "JOIN t_user_level AS ul ON u.user_level_id = ul.level_id\n"
            "JOIN t_order_detail AS od ON o.order_id = od.order_id\n"
            "JOIN t_product AS p ON od.product_id = p.product_id\n"
            "JOIN t_category AS c ON p.category_id = c.category_id\n"
            "WHERE o.order_status = 'PAID'\n"
            f"  AND o.created_at >= TIMESTAMP '{_SEP_START}'\n"
            f"  AND o.created_at < TIMESTAMP '{_SEP_END}'\n"
            f"  AND ul.level_name = '{level}'\n"
            f"  AND c.category_name = '{category}'\n"
            "GROUP BY ul.level_id, ul.level_name, c.category_id, c.category_name"
        ),
        required_tables=[
            "t_order",
            "t_user",
            "t_user_level",
            "t_order_detail",
            "t_product",
            "t_category",
        ],
        required_junctions=[],
        expected_columns=["level_name", "category_name", "total_quantity"],
        tags=["aggregation", "time-window"],
    )


def _self_category_amount(index: int, category: str) -> BenchmarkCase:
    return _make(
        case_id=f"custom_medium_{index:03d}",
        difficulty="medium",
        question=f"统计2026年9月自营商家{category}品类的已支付销售金额",
        gold_sql=(
            "SELECT c.category_name, SUM(od.quantity * od.price) AS gross_amount\n"
            "FROM t_order AS o\n"
            "JOIN t_order_detail AS od ON o.order_id = od.order_id\n"
            "JOIN t_product AS p ON od.product_id = p.product_id\n"
            "JOIN t_category AS c ON p.category_id = c.category_id\n"
            "JOIN t_merchant AS m ON p.merchant_id = m.merchant_id\n"
            "WHERE o.order_status = 'PAID'\n"
            "  AND m.is_self_operated IS TRUE\n"
            f"  AND c.category_name = '{category}'\n"
            f"  AND o.created_at >= TIMESTAMP '{_SEP_START}'\n"
            f"  AND o.created_at < TIMESTAMP '{_SEP_END}'\n"
            "GROUP BY c.category_id, c.category_name"
        ),
        required_tables=[
            "t_order",
            "t_order_detail",
            "t_product",
            "t_category",
            "t_merchant",
        ],
        required_junctions=[],
        expected_columns=["category_name", "gross_amount"],
        tags=["aggregation", "time-window"],
    )


def _region_coupon(index: int, region: str, coupon_type: str, label: str) -> BenchmarkCase:
    return _make(
        case_id=f"custom_medium_{index:03d}",
        difficulty="medium",
        question=f"统计2026年9月{region}大区使用{label}优惠券的已支付订单数",
        gold_sql=(
            "SELECT r.region_name, c.coupon_type, "
            "COUNT(DISTINCT o.order_id)::bigint AS order_count\n"
            "FROM t_order AS o\n"
            "JOIN t_user AS u ON o.user_id = u.user_id\n"
            "JOIN t_user_region_map AS urm ON u.user_id = urm.user_id\n"
            "JOIN t_region AS r ON urm.region_id = r.region_id\n"
            "JOIN t_order_coupon_rel AS ocr ON o.order_id = ocr.order_id\n"
            "JOIN t_coupon AS c ON ocr.coupon_id = c.coupon_id\n"
            "WHERE o.order_status = 'PAID'\n"
            f"  AND r.region_name = '{region}'\n"
            f"  AND c.coupon_type = '{coupon_type}'\n"
            f"  AND o.created_at >= TIMESTAMP '{_SEP_START}'\n"
            f"  AND o.created_at < TIMESTAMP '{_SEP_END}'\n"
            "GROUP BY r.region_name, c.coupon_type"
        ),
        required_tables=["t_order", "t_user", "t_region", "t_coupon"],
        required_junctions=["t_user_region_map", "t_order_coupon_rel"],
        expected_columns=["region_name", "coupon_type", "order_count"],
        tags=["aggregation", "junction", "time-window"],
    )


def _level_self_amount(index: int, level: str, *, self_operated: bool) -> BenchmarkCase:
    flag = "TRUE" if self_operated else "FALSE"
    kind = "自营" if self_operated else "非自营"
    return _make(
        case_id=f"custom_medium_{index:03d}",
        difficulty="medium",
        question=f"统计2026年9月{level}用户在{kind}商家的已支付销售金额",
        gold_sql=(
            "SELECT ul.level_name, m.is_self_operated, "
            "SUM(od.quantity * od.price) AS gross_amount\n"
            "FROM t_order AS o\n"
            "JOIN t_user AS u ON o.user_id = u.user_id\n"
            "JOIN t_user_level AS ul ON u.user_level_id = ul.level_id\n"
            "JOIN t_order_detail AS od ON o.order_id = od.order_id\n"
            "JOIN t_product AS p ON od.product_id = p.product_id\n"
            "JOIN t_merchant AS m ON p.merchant_id = m.merchant_id\n"
            "WHERE o.order_status = 'PAID'\n"
            f"  AND ul.level_name = '{level}'\n"
            f"  AND m.is_self_operated IS {flag}\n"
            f"  AND o.created_at >= TIMESTAMP '{_SEP_START}'\n"
            f"  AND o.created_at < TIMESTAMP '{_SEP_END}'\n"
            "GROUP BY ul.level_id, ul.level_name, m.is_self_operated"
        ),
        required_tables=[
            "t_order",
            "t_user",
            "t_user_level",
            "t_order_detail",
            "t_product",
            "t_merchant",
        ],
        required_junctions=[],
        expected_columns=["level_name", "is_self_operated", "gross_amount"],
        tags=["aggregation", "time-window"],
    )


def _having_month(index: int, month: int) -> BenchmarkCase:
    start, end = _month_bounds(2026, month)
    return _make(
        case_id=f"custom_medium_{index:03d}",
        difficulty="medium",
        question=f"统计2026年{month}月自营商家已支付销量不少于1件的品类和销量",
        gold_sql=(
            f"SELECT '{start[:7]}' AS order_month, c.category_name, "
            "SUM(od.quantity)::bigint AS total_quantity\n"
            "FROM t_order AS o\n"
            "JOIN t_order_detail AS od ON o.order_id = od.order_id\n"
            "JOIN t_product AS p ON od.product_id = p.product_id\n"
            "JOIN t_category AS c ON p.category_id = c.category_id\n"
            "JOIN t_merchant AS m ON p.merchant_id = m.merchant_id\n"
            "WHERE o.order_status = 'PAID'\n"
            "  AND m.is_self_operated IS TRUE\n"
            f"  AND o.created_at >= TIMESTAMP '{start}'\n"
            f"  AND o.created_at < TIMESTAMP '{end}'\n"
            "GROUP BY c.category_id, c.category_name\n"
            "HAVING SUM(od.quantity) >= 1"
        ),
        required_tables=[
            "t_order",
            "t_order_detail",
            "t_product",
            "t_category",
            "t_merchant",
        ],
        required_junctions=[],
        expected_columns=["order_month", "category_name", "total_quantity"],
        tags=["aggregation", "having", "time-window"],
    )


def _complex_cases() -> list[BenchmarkCase]:
    """28 条复杂用例。

    种子 20261001 上，单月加单一品类再叠加促销适用关系几乎只有华东美妆队列有行。
    因此券+地区用例使用 2026 年 1 月至 9 月和品类组；促销适用关系只切分该非空队列。
    """

    cases: list[BenchmarkCase] = []
    index = 5
    for region in _REGIONS:
        for names, label in ((_GROUP_A, "个护数码"), (_GROUP_B, "食品家居")):
            cases.append(_region_group_orders(index, region, names, label))
            index += 1
    for level in ("VIP3", "VIP4", "VIP5"):
        cases.append(_promo_slice(index, level=level, merchant_name=None))
        index += 1
    for merchant_name in ("自营美妆一店", "自营美妆二店"):
        cases.append(_promo_slice(index, level=None, merchant_name=merchant_name))
        index += 1
    cases.append(_promo_slice(index, level="VIP4", merchant_name="自营美妆一店"))
    index += 1
    for region in _REGIONS:
        cases.append(_region_beauty_quantity(index, region))
        index += 1
    for level in ("VIP2", "VIP3", "VIP4", "VIP5"):
        cases.append(_east_beauty_level(index, level))
        index += 1
    return cases


def _region_group_orders(
    index: int,
    region: str,
    categories: tuple[str, ...],
    label: str,
) -> BenchmarkCase:
    listed = "、".join(categories[:-1]) + "或" + categories[-1]
    in_list = ", ".join(f"'{name}'" for name in categories)
    question = (
        f"统计2026年1月至9月{region}大区VIP3、VIP4和VIP5用户使用满减优惠券"
        f"购买自营{listed}的已支付订单数和实付金额"
    )
    return _make(
        case_id=f"custom_complex_{index:03d}",
        difficulty="complex",
        question=question,
        gold_sql=_order_shape(
            region=region,
            level_sql="ul.level_name IN ('VIP3', 'VIP4', 'VIP5')",
            category_sql=f"cat.category_name IN ({in_list})",
            start=_YEAR_START,
            end=_YEAR_END,
            merchant_sql="",
            promo=False,
            select_list=(
                f"'{region}' AS region_name, '{label}' AS category_group, "
                "merchant_name, COUNT(*)::bigint AS total_orders, "
                "SUM(total_amount) AS net_pay_amount"
            ),
        ),
        required_tables=_ORDER_TABLES,
        required_junctions=["t_user_region_map", "t_order_coupon_rel"],
        expected_columns=[
            "region_name",
            "category_group",
            "merchant_name",
            "total_orders",
            "net_pay_amount",
        ],
        tags=["long-join", "aggregation", "junction-recall"],
    )


def _promo_slice(index: int, *, level: str | None, merchant_name: str | None) -> BenchmarkCase:
    if level is None:
        level_sql = "ul.level_name IN ('VIP3', 'VIP4', 'VIP5')"
        level_text = "VIP3、VIP4和VIP5"
    else:
        level_sql = f"ul.level_name = '{level}'"
        level_text = level
    merchant_sql = ""
    merchant_text = ""
    if merchant_name is not None:
        merchant_sql = f"AND m.merchant_name = '{merchant_name}'"
        merchant_text = f"在{merchant_name}"
    question = (
        f"统计2026年9月华东大区{level_text}用户{merchant_text}使用满减优惠券购买自营美妆、"
        "且该优惠券适用于所购商品的已支付订单数和实付金额"
    )
    return _make(
        case_id=f"custom_complex_{index:03d}",
        difficulty="complex",
        question=question,
        gold_sql=_order_shape(
            region="华东",
            level_sql=level_sql,
            category_sql="cat.category_name = '美妆'",
            start=_SEP_START,
            end=_SEP_END,
            merchant_sql=merchant_sql,
            promo=True,
            select_list=(
                "merchant_name, COUNT(*)::bigint AS total_orders, "
                "SUM(total_amount) AS net_pay_amount"
            ),
        ),
        required_tables=_ORDER_TABLES,
        required_junctions=["t_user_region_map", "t_order_coupon_rel", "t_promo_sku_rel"],
        expected_columns=["merchant_name", "total_orders", "net_pay_amount"],
        tags=["long-join", "junction-recall", "dedup"],
    )


def _region_beauty_quantity(index: int, region: str) -> BenchmarkCase:
    return _make(
        case_id=f"custom_complex_{index:03d}",
        difficulty="complex",
        question=f"统计2026年1月至9月{region}大区VIP3以上用户购买自营美妆的已支付商品数量",
        gold_sql=(
            "WITH qualified_details AS (\n"
            "    SELECT DISTINCT od.detail_id, od.quantity, m.merchant_id, m.merchant_name\n"
            "    FROM t_order AS o\n"
            "    JOIN t_user AS u ON o.user_id = u.user_id\n"
            "    JOIN t_user_level AS ul ON u.user_level_id = ul.level_id\n"
            "    JOIN t_user_region_map AS urm ON u.user_id = urm.user_id\n"
            "    JOIN t_region AS r ON urm.region_id = r.region_id\n"
            "    JOIN t_order_detail AS od ON o.order_id = od.order_id\n"
            "    JOIN t_product AS p ON od.product_id = p.product_id\n"
            "    JOIN t_category AS cat ON p.category_id = cat.category_id\n"
            "    JOIN t_merchant AS m ON p.merchant_id = m.merchant_id\n"
            "    WHERE ul.level_name IN ('VIP3', 'VIP4', 'VIP5')\n"
            f"      AND r.region_name = '{region}'\n"
            "      AND cat.category_name = '美妆'\n"
            "      AND m.is_self_operated IS TRUE\n"
            "      AND o.order_status = 'PAID'\n"
            f"      AND o.created_at >= TIMESTAMP '{_YEAR_START}'\n"
            f"      AND o.created_at < TIMESTAMP '{_YEAR_END}'\n"
            ")\n"
            "SELECT "
            f"'{region}' AS region_name, '美妆' AS category_name, "
            "merchant_name, SUM(quantity)::bigint AS total_quantity\n"
            "FROM qualified_details\n"
            "GROUP BY merchant_id, merchant_name"
        ),
        required_tables=[
            "t_order",
            "t_user",
            "t_user_level",
            "t_region",
            "t_order_detail",
            "t_product",
            "t_category",
            "t_merchant",
        ],
        required_junctions=["t_user_region_map"],
        expected_columns=["region_name", "category_name", "merchant_name", "total_quantity"],
        tags=["junction", "aggregation"],
    )


def _east_beauty_level(index: int, level: str) -> BenchmarkCase:
    return _make(
        case_id=f"custom_complex_{index:03d}",
        difficulty="complex",
        question=(
            f"统计2026年1月至9月华东大区{level}用户使用满减优惠券"
            "购买自营美妆的已支付订单数和实付金额"
        ),
        gold_sql=_order_shape(
            region="华东",
            level_sql=f"ul.level_name = '{level}'",
            category_sql="cat.category_name = '美妆'",
            start=_YEAR_START,
            end=_YEAR_END,
            merchant_sql="",
            promo=False,
            select_list=(
                f"'{level}' AS level_name, merchant_name, "
                "COUNT(*)::bigint AS total_orders, SUM(total_amount) AS net_pay_amount"
            ),
        ),
        required_tables=_ORDER_TABLES,
        required_junctions=["t_user_region_map", "t_order_coupon_rel"],
        expected_columns=["level_name", "merchant_name", "total_orders", "net_pay_amount"],
        tags=["long-join", "aggregation", "junction-recall"],
    )


_ORDER_TABLES = [
    "t_order",
    "t_user",
    "t_user_level",
    "t_region",
    "t_coupon",
    "t_order_detail",
    "t_product",
    "t_category",
    "t_merchant",
]


def _order_shape(
    *,
    region: str,
    level_sql: str,
    category_sql: str,
    start: str,
    end: str,
    merchant_sql: str,
    promo: bool,
    select_list: str,
) -> str:
    promo_sql = ""
    if promo:
        promo_sql = (
            "      AND EXISTS (\n"
            "          SELECT 1\n"
            "          FROM t_promo_sku_rel AS psr\n"
            "          WHERE psr.product_id = p.product_id\n"
            "            AND psr.coupon_id = c.coupon_id\n"
            "      )\n"
        )
    merchant_line = f"      {merchant_sql}\n" if merchant_sql else ""
    return (
        "WITH qualified_orders AS (\n"
        "    SELECT DISTINCT o.order_id, o.total_amount, m.merchant_id, m.merchant_name\n"
        "    FROM t_order AS o\n"
        "    JOIN t_user AS u ON o.user_id = u.user_id\n"
        "    JOIN t_user_level AS ul ON u.user_level_id = ul.level_id\n"
        "    JOIN t_user_region_map AS urm ON u.user_id = urm.user_id\n"
        "    JOIN t_region AS r ON urm.region_id = r.region_id\n"
        "    JOIN t_order_coupon_rel AS ocr ON o.order_id = ocr.order_id\n"
        "    JOIN t_coupon AS c ON ocr.coupon_id = c.coupon_id\n"
        "    JOIN t_order_detail AS od ON o.order_id = od.order_id\n"
        "    JOIN t_product AS p ON od.product_id = p.product_id\n"
        "    JOIN t_category AS cat ON p.category_id = cat.category_id\n"
        "    JOIN t_merchant AS m ON p.merchant_id = m.merchant_id\n"
        f"    WHERE {level_sql}\n"
        f"      AND r.region_name = '{region}'\n"
        "      AND c.coupon_type = 'full_reduction'\n"
        f"      AND {category_sql}\n"
        "      AND m.is_self_operated IS TRUE\n"
        "      AND o.order_status = 'PAID'\n"
        f"      AND o.created_at >= TIMESTAMP '{start}'\n"
        f"      AND o.created_at < TIMESTAMP '{end}'\n"
        f"{merchant_line}"
        f"{promo_sql}"
        ")\n"
        f"SELECT {select_list}\n"
        "FROM qualified_orders\n"
        "GROUP BY merchant_id, merchant_name"
    )


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    start = f"{year:04d}-{month:02d}-01 00:00:00"
    if month == 12:
        end = f"{year + 1:04d}-01-01 00:00:00"
    else:
        end = f"{year:04d}-{month + 1:02d}-01 00:00:00"
    return start, end


def _emit_case(case: BenchmarkCase) -> list[str]:
    payload = case.model_dump(mode="json")
    lines = [f"  - id: {payload['id']}"]
    for key in (
        "source",
        "source_version",
        "database_id",
        "difficulty",
        "dialect",
    ):
        lines.append(f"    {key}: {payload[key]}")
    lines.append(f"    question: {json.dumps(payload['question'], ensure_ascii=False)}")
    lines.append("    gold_sql: |-")
    lines.extend(f"      {line}" for line in str(payload["gold_sql"]).split("\n"))
    lines.extend(_emit_list("required_tables", payload["required_tables"]))
    lines.extend(_emit_list("required_junctions", payload["required_junctions"]))
    lines.append(f"    order_sensitive: {str(payload['order_sensitive']).lower()}")
    lines.append("    numeric_tolerance: null")
    lines.extend(_emit_list("expected_columns", payload["expected_columns"]))
    lines.append(f"    anchor_date: {json.dumps(payload['anchor_date'])}")
    lines.extend(_emit_list("tags", payload["tags"]))
    return lines


def _emit_list(key: str, values: object) -> list[str]:
    if not isinstance(values, list):
        raise TypeError(key)
    if not values:
        return [f"    {key}: []"]
    lines = [f"    {key}:"]
    lines.extend(f"      - {json.dumps(item, ensure_ascii=False)}" for item in values)
    return lines
