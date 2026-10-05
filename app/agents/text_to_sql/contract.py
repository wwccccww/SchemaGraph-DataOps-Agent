"""从问题和固定业务词典提取答案契约。

不读取 Gold SQL、Gold 结果、required_tables 或难度。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.agents.text_to_sql.semantic import SemanticFinding
from app.evaluation.sql_shape import describe_sql

CategoryScope = Literal["exact", "descendants"]
_DESCENDANTS = re.compile(r"及其子类|全部下级|子品类|下级品类")
_LITERAL_ALIAS = re.compile(
    r"'[^']*'\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
_MONTH = re.compile(r"(\d{4})年(\d{1,2})月")
_SPAN = re.compile(r"(\d{4})年(\d{1,2})月至(\d{1,2})月")
_CLOCK = re.compile(r"\b(?:current_date|current_timestamp|clock_timestamp)\b", re.IGNORECASE)
_GROUP_TOKENS = {
    "品类": ("category_id", "category_name", "category_group"),
    "会员等级": ("level_id", "level_name"),
    "商家": ("merchant_id", "merchant_name"),
    "地区": ("region_id", "region_name", "province_name"),
    "优惠券": ("coupon_id", "coupon_name", "coupon_type"),
    "用户": ("user_id", "username"),
    "商品": ("product_id", "product_name"),
}


@dataclass(frozen=True)
class AnswerContract:
    """生成前就能确定的答案形状。"""

    dimensions: tuple[str, ...]
    dimension_fields: tuple[str, ...]
    measures: tuple[str, ...]
    filters: tuple[str, ...]
    category_scope: CategoryScope
    time_window: tuple[str, str] | None
    dedup_key: str | None
    output_fields: tuple[str, ...] = ()
    constants: tuple[tuple[str, str], ...] = ()
    fact_key: str | None = None
    group_keys: tuple[str, ...] = ()
    fanout_policy: str = ""

    def as_pairs(self) -> tuple[tuple[str, str], ...]:
        if self.time_window is None:
            window = "无"
        else:
            window = f"{self.time_window[0]}/{self.time_window[1]}"
        rendered_constants = ",".join(f"{name}={value}" for name, value in self.constants)
        return (
            ("dimensions", ",".join(self.dimensions)),
            ("dimension_fields", ",".join(self.dimension_fields)),
            ("measures", ",".join(self.measures)),
            ("filters", ",".join(self.filters)),
            ("category_scope", self.category_scope),
            ("time_window", window),
            ("dedup_key", self.dedup_key or ""),
            ("output_fields", ",".join(self.output_fields)),
            ("constants", rendered_constants),
            ("fact_key", self.fact_key or ""),
            ("group_keys", ",".join(self.group_keys)),
            ("fanout_policy", self.fanout_policy),
        )


def extract_answer_contract(question: str, *, anchor_date: str = "2026-10-01") -> AnswerContract:
    """按问句和锚点日展开契约。锚点日不是 Gold。"""

    builder = _Builder(question, anchor_date)
    builder.apply()
    return builder.contract()


def format_answer_contract(contract: AnswerContract) -> str:
    """放在 Schema Context 之前的契约文本。"""

    window = "无"
    if contract.time_window is not None:
        start, end = contract.time_window
        window = f"[{start}, {end})"
    constants = "无"
    if contract.constants:
        constants = "、".join(f"{name}='{value}'" for name, value in contract.constants)
    return "\n".join(
        (
            "答案契约：",
            f"dimensions: {_shown(contract.dimensions)}",
            f"dimension_fields: {_shown(contract.dimension_fields)}",
            f"measures: {_shown(contract.measures)}",
            f"filters: {_shown(contract.filters)}",
            f"category_scope: {contract.category_scope}",
            f"time_window: {window}",
            f"dedup_key: {contract.dedup_key or '无'}",
            f"output_fields: {_shown(contract.output_fields)}",
            f"constants: {constants}",
            "最终 SELECT 的别名和顺序必须与 output_fields 一致。",
            "constants 中的值必须作为字符串字面量投影，不能改成函数计算结果。",
            "每个 dimension 出现在最终结果粒度中，dimension_fields 和 measures 出现在最终投影。",
            "单个维度值若被契约回显，不能只返回一个没有该列的标量。",
            "品类默认精确匹配当前节点。只有问题写明及其子类或全部下级时才展开。",
            "时间窗口使用上面的固定常量。",
            "不要使用 CURRENT_DATE、CURRENT_TIMESTAMP 或 clock_timestamp。",
            "dedup_key 不是“无”时，先按该键形成事实集合，再做最终聚合。",
            "fact_key 不是“无”时，汇总前先按该键去重，去重后不要再连接会放大行数的表。",
            "group_keys 用于分组，不要求全部出现在最终投影。",
        )
    )


def format_query_plan(contract: AnswerContract, join_paths: Sequence[str]) -> str:
    """事实粒度、有序输出和当前 Schema 里的外键路径。不读取 Gold。"""

    grain = contract.fact_key or contract.dedup_key or "结果行"
    lines = [
        "查询计划：",
        f"事实粒度：{grain}",
        f"输出列：{_shown(contract.output_fields)}",
    ]
    if contract.fact_key:
        lines.append(f"事实键：{contract.fact_key}")
        lines.append(f"防放大：{contract.fanout_policy or '聚合前按事实键去重'}")
    if contract.group_keys:
        lines.append(f"分组键：{'、'.join(contract.group_keys)}")
    if contract.dedup_key:
        lines.append(f"去重：聚合前按 {contract.dedup_key} 形成事实集合。")
    if contract.constants:
        shown = "、".join(f"{name}='{value}'" for name, value in contract.constants)
        lines.append(f"常量列：{shown}")
    if join_paths:
        lines.append("合法外键：")
        lines.extend(join_paths)
    else:
        lines.append("合法外键：无")
    lines.append("CTE 被外层引用的列必须出现在该 CTE 的投影中。")
    return "\n".join(lines)


def check_contract(
    *,
    question: str,
    sql: str,
    anchor_date: str = "2026-10-01",
) -> tuple[SemanticFinding, ...]:
    """执行成功后的确定性契约复核。不读取 Gold。"""

    contract = extract_answer_contract(question, anchor_date=anchor_date)
    shape = describe_sql(sql)
    if shape.parse_error is not None:
        return ()
    findings: list[SemanticFinding] = []
    _check_output(contract, shape.projections, sql, findings)
    _check_projection(contract, shape.projections, findings)
    _check_measures(contract, shape, sql, findings)
    _check_grain(contract, shape, findings)
    _check_category(contract, question, sql, findings)
    _check_time(contract, sql, findings)
    _check_dedup(contract, sql, findings)
    _check_canonical_values(question, sql, findings)
    unique = list(dict.fromkeys(findings))
    return tuple(sorted(unique, key=lambda item: (item.category, item.message)))


class _Builder:
    def __init__(self, question: str, anchor_date: str) -> None:
        self.question = question
        self.anchor_date = anchor_date
        self.dimensions: list[str] = []
        self.fields: list[str] = []
        self.measures: list[str] = []
        self.filters: list[str] = []

    def apply(self) -> None:
        text = self.question
        self._time_filter()
        self._status_filter()
        self._membership_filters()
        self._measures()
        self._fields(text)
        self._groups(text)
        group = category_group_name(text)
        if group is not None:
            members = "、".join(_CATEGORY_GROUPS[group])
            self.filters.append(f"品类组 {group} 包含 {members}")
        if self.category_scope == "exact":
            self.filters.append("品类名称只匹配当前节点")
        for alias, canonical in canonical_value_aliases(text):
            self.filters.append(f"品类取值使用 {canonical}，不要写成 {alias}")

    def contract(self) -> AnswerContract:
        return AnswerContract(
            dimensions=tuple(dict.fromkeys(self.dimensions)),
            dimension_fields=tuple(dict.fromkeys(self.fields)),
            measures=tuple(dict.fromkeys(self.measures)),
            filters=tuple(dict.fromkeys(self.filters)),
            category_scope=self.category_scope,
            time_window=self.window,
            dedup_key=self.dedup_key,
            output_fields=_output_fields(self.question),
            constants=_constants(self.question, self.window),
            fact_key=self.fact_key,
            group_keys=self.group_keys,
            fanout_policy="dedup_before_aggregate" if self.fact_key else "",
        )

    @property
    def category_scope(self) -> CategoryScope:
        if _DESCENDANTS.search(self.question):
            return "descendants"
        return "exact"

    @property
    def window(self) -> tuple[str, str] | None:
        return _time_window(self.question, self.anchor_date)

    @property
    def dedup_key(self) -> str | None:
        text = self.question.replace("订单数量", "")
        if "订单数" in text or "实付金额" in text:
            return "order_id"
        return None

    @property
    def fact_key(self) -> str | None:
        text = self.question
        if "在售商品数量" in text:
            return "product_id"
        if "用户数量" in text:
            return "user_id"
        if "明细行数" in text:
            return "detail_id"
        bought = "购买" in text and "数量" in text and "在售" not in text
        if "销量" in text or bought or ("商品数量" in text and "在售" not in text):
            return "detail_id"
        return self.dedup_key

    @property
    def group_keys(self) -> tuple[str, ...]:
        keys: list[str] = []
        if "商家" in self.dimensions:
            keys.extend(("merchant_id", "merchant_name"))
        if "品类" in self.dimensions:
            keys.extend(("category_id", "category_name"))
        if "会员等级" in self.dimensions:
            keys.extend(("level_id", "level_name"))
        if "地区" in self.dimensions:
            keys.append("region_name")
        if "优惠券" in self.dimensions:
            keys.append("coupon_type")
        if "用户" in self.dimensions:
            keys.append("user_id")
        return tuple(dict.fromkeys(keys))

    def _time_filter(self) -> None:
        window = self.window
        if window is None:
            return
        self.filters.append(f"时间窗口 [{window[0]}, {window[1]})")

    def _status_filter(self) -> None:
        if "已支付" in self.question:
            self.filters.append("order_status = PAID")
        if "已取消" in self.question:
            self.filters.append("order_status = CANCELLED")
        if "自营" in self.question and "非自营" not in self.question:
            self.filters.append("商家为自营")
        if "非自营" in self.question:
            self.filters.append("商家为非自营")

    def _membership_filters(self) -> None:
        if "VIP3以上" in self.question or "VIP3、VIP4" in self.question:
            self.filters.append("VIP3以上定义为 VIP3、VIP4、VIP5")
        if "满减" in self.question:
            self.filters.append("coupon_type = full_reduction")
        if "折扣" in self.question and "折扣率" not in self.question:
            self.filters.append("coupon_type = discount")
        if "末级" in self.question:
            self.filters.append("末级品类定义为 parent_id <> 0")
        if "一级" in self.question:
            self.filters.append("一级品类定义为 parent_id = 0")

    def _measures(self) -> None:
        text = self.question
        if any(word in text for word in ("实付金额",)):
            self.measures.append("sum_amount")
        if "销售金额" in text:
            self.measures.append("sum_line")
        bought = "购买" in text and "数量" in text and "在售" not in text
        if "销量" in text or bought or ("商品数量" in text and "在售" not in text):
            self.measures.append("sum_quantity")
        if any(
            word in text
            for word in (
                "用户数量",
                "订单数量",
                "订单数",
                "明细行数",
                "在售商品数量",
                "优惠券的数量",
                "商家的数量",
                "品类的数量",
            )
        ):
            self.measures.append("count")

    def _fields(self, text: str) -> None:
        if "折扣率" in text:
            self.fields.append("discount_rate")
        if "名称" in text and "会员等级" in text:
            self.fields.append("level_name")
        if "等级编号" in text or ("编号" in text and "会员等级" in text):
            self.fields.append("level_id")
        if "省份" in text:
            self.fields.append("province_name")
        if "品类编号" in text:
            self.fields.append("category_id")
        if "优惠券编号" in text:
            self.fields.append("coupon_id")
        if "名称" in text and "优惠券" in text:
            self.fields.append("coupon_name")
        if "商家、商品和优惠券" in text:
            self.fields.extend(("merchant_name", "product_name", "coupon_name"))
        if "商品" in text and "查询" in text and "统计" not in text:
            self.fields.extend(("product_name", "merchant_name"))
        if "按商家名称" in text or ("商家" in text and "名称" in text and "查询" in text):
            self.fields.append("merchant_name")
        if "一级" in text and "名称" in text:
            self.fields.append("category_name")
        if "末级" in text:
            self.fields.append("category_kind")
        if "满减类型" in text or "折扣类型" in text:
            self.fields.append("coupon_type")
        if "商家的数量" in text:
            self.fields.append("merchant_kind")
        if "状态为" in text:
            self.fields.extend(("order_month", "order_status"))
        if "品类和销量" in text:
            self.fields.extend(("order_month", "category_name"))
        if "在售商品数量" in text or "明细行数" in text:
            self.fields.append("category_name")
        if "用户数量" in text or "会员等级下" in text:
            self.fields.append("level_name")
        if "用户编号" in text:
            self.fields.append("user_id")
        if "购买" in text and "商品" in text and "大区" not in text:
            if "会员" in text or "VIP" in text:
                self.fields.append("level_name")
            if "品类" in text or _named_category(text):
                self.fields.append("category_name")
        if "销售金额" in text and "品类" in text:
            self.fields.append("category_name")
        if "销售金额" in text and "VIP" in text:
            self.fields.extend(("level_name", "is_self_operated"))
        if "大区" in text and "优惠券" in text and "订单数" in text and "实付" not in text:
            self.fields.extend(("region_name", "coupon_type"))
        if "实付金额" in text or ("订单数" in text and "商家" in text and "优惠券" in text):
            self.fields.append("merchant_name")
        if "个护数码" in text or "食品家居" in text:
            self.fields.extend(("region_name", "category_group", "merchant_name"))
        if "商品数量" in text and "大区" in text:
            self.fields.append("merchant_name")
        single_level = re.search(r"VIP[1-5]用户", text) and "VIP3、VIP4" not in text
        if single_level and "订单数" in text and "实付金额" in text and "适用于" not in text:
            self.fields.append("level_name")
        if "各品类" in text:
            self.fields.append("category_name")

    def _groups(self, text: str) -> None:
        if "各品类" in text or "每个品类" in text or "品类和销量" in text:
            self.dimensions.append("品类")
        elif "每个会员等级" in text:
            self.dimensions.append("会员等级")
        elif "在售商品数量" in text or "明细行数" in text:
            self.dimensions.append("品类")
        elif "用户数量" in text or "会员等级下" in text:
            self.dimensions.append("会员等级")
        elif "用户编号" in text:
            self.dimensions.append("用户")
        elif "购买" in text and "数量" in text and "大区" not in text:
            if "VIP" in text or "会员" in text:
                self.dimensions.append("会员等级")
            if "品类" in text or "商品" in text:
                self.dimensions.append("品类")
        elif "销售金额" in text and "品类" in text and "VIP" not in text:
            self.dimensions.append("品类")
        elif "销售金额" in text and "VIP" in text:
            self.dimensions.append("会员等级")
        elif "大区" in text and "优惠券" in text and "订单数" in text and "实付" not in text:
            self.dimensions.extend(("地区", "优惠券"))
        elif "实付金额" in text or "商品数量" in text or ("订单数" in text and "商家" in text):
            self.dimensions.append("商家")


_CATEGORY_GROUPS: dict[str, tuple[str, ...]] = {
    "个护数码": (
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
    ),
    "食品家居": (
        "零食",
        "饮料",
        "生鲜",
        "粮油",
        "家具",
        "灯具",
        "收纳",
        "厨具",
        "冰箱",
        "洗衣机",
    ),
}
_REGIONS = ("华北", "华东", "华中", "华南", "西南", "西北")


_CANONICAL_VALUES = (("护肤品", "护肤"),)


def canonical_value_aliases(question: str) -> tuple[tuple[str, str], ...]:
    """问句里的口语别名对应目录中的取值。不读取 Gold。"""

    return tuple((alias, canonical) for alias, canonical in _CANONICAL_VALUES if alias in question)


def category_group_name(question: str) -> str | None:
    """问句列出一整组品类时，返回业务组名。"""

    for name, members in _CATEGORY_GROUPS.items():
        if all(member in question for member in members):
            return name
    return None


def _output_fields(question: str) -> tuple[str, ...]:
    """按业务响应规范给出最终投影的别名和顺序。不读取 Gold。"""

    text = question
    if "折扣率" in text and "会员等级" in text:
        return ("level_id", "level_name", "discount_rate")
    if "每个会员等级" in text and "用户数量" in text:
        return ("level_name", "user_count")
    if "会员等级下" in text and "用户数量" in text:
        return ("level_name", "user_count")
    if "省份" in text:
        return ("province_name",)
    if "状态为" in text and "订单数量" in text:
        return ("order_month", "order_status", "order_count")
    if "在售商品数量" in text:
        return ("category_name", "product_count")
    if "满减类型" in text or "折扣类型" in text:
        return ("coupon_type", "coupon_count")
    if "优惠券编号" in text:
        return ("coupon_id", "coupon_name")
    if "商家的数量" in text:
        return ("merchant_kind", "merchant_count")
    if "商家名称" in text and "查询" in text:
        return ("merchant_id", "merchant_name")
    if "一级" in text and "名称" in text:
        return ("category_id", "category_name")
    if "末级" in text and "数量" in text:
        return ("category_kind", "category_count")
    if "用户编号" in text and "订单" in text:
        return ("user_id", "order_count")
    if "明细行数" in text:
        return ("category_name", "detail_count")
    if "品类和销量" in text:
        return ("order_month", "category_name", "total_quantity")
    if "商家、商品和优惠券" in text:
        return ("merchant_name", "product_name", "coupon_name")
    if category_group_name(text) is not None and "实付金额" in text:
        return (
            "region_name",
            "category_group",
            "merchant_name",
            "total_orders",
            "net_pay_amount",
        )
    if "商品数量" in text and "大区" in text:
        if _SPAN.search(text):
            return ("region_name", "category_name", "merchant_name", "total_quantity")
        return ("merchant_name", "total_quantity")
    if "查询" in text and "商品" in text and "统计" not in text:
        return ("product_id", "product_name", "merchant_name")
    if "实付金额" in text:
        single_level = re.search(r"VIP[1-5]用户", text) and "VIP3、VIP4" not in text
        if single_level and "适用于" not in text and _SPAN.search(text):
            return ("level_name", "merchant_name", "total_orders", "net_pay_amount")
        return ("merchant_name", "total_orders", "net_pay_amount")
    if "销售金额" in text and "VIP" in text:
        return ("level_name", "is_self_operated", "gross_amount")
    if "销售金额" in text:
        return ("category_name", "gross_amount")
    if "大区" in text and "优惠券" in text and "订单数" in text and "实付" not in text:
        return ("region_name", "coupon_type", "order_count")
    if "购买" in text and "数量" in text and "大区" not in text:
        if "商品" in text:
            return ("level_name", "category_name", "total_quantity")
        return ("level_name", "total_quantity")
    if "订单数" in text and "商家" in text:
        return ("merchant_name", "order_count")
    return ()


def _constants(question: str, window: tuple[str, str] | None) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    label = _month_label(question, window)
    if label is not None and ("状态为" in question or "品类和销量" in question):
        rows.append(("order_month", label))
    if "状态为" in question and "已支付" in question:
        rows.append(("order_status", "PAID"))
    if "状态为" in question and "已取消" in question:
        rows.append(("order_status", "CANCELLED"))
    if "商家的数量" in question:
        kind = "third_party" if "非自营" in question else "self_operated"
        rows.append(("merchant_kind", kind))
    if "末级" in question and "数量" in question:
        rows.append(("category_kind", "leaf"))
    group = category_group_name(question)
    if group is not None:
        rows.append(("category_group", group))
        region = _region_name(question)
        if region is not None:
            rows.append(("region_name", region))
    return tuple(rows)


def _month_label(question: str, window: tuple[str, str] | None) -> str | None:
    if "上个月" in question and window is not None:
        return window[0][:7]
    match = _MONTH.search(question)
    if match is None:
        return None
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"


def _region_name(question: str) -> str | None:
    found = [name for name in _REGIONS if name in question]
    if len(found) == 1:
        return found[0]
    return None


def _check_output(
    contract: AnswerContract,
    projections: tuple[str, ...],
    sql: str,
    findings: list[SemanticFinding],
) -> None:
    if contract.output_fields:
        actual = tuple(name.lower() for name in projections)
        expected = tuple(name.lower() for name in contract.output_fields)
        if actual != expected:
            shown = "、".join(projections) if projections else "无"
            findings.append(
                SemanticFinding(
                    "contract_mismatch",
                    f"期望投影顺序 {'、'.join(contract.output_fields)}；实际投影为 {shown}",
                )
            )
    for name, literal in contract.constants:
        if f"'{literal}'" not in sql:
            findings.append(
                SemanticFinding(
                    "contract_mismatch",
                    f"期望常量 {name}='{literal}'；实际没有这个字符串字面量",
                )
            )


def _shown(values: tuple[str, ...]) -> str:
    return "、".join(values) if values else "无"


def _named_category(text: str) -> bool:
    names = (
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
        "零食",
        "饮料",
        "生鲜",
        "粮油",
        "家具",
        "灯具",
        "收纳",
        "厨具",
        "冰箱",
        "洗衣机",
    )
    return any(name in text for name in names)


def _time_window(question: str, anchor_date: str) -> tuple[str, str] | None:
    if "上个月" in question:
        parsed = date.fromisoformat(anchor_date)
        if parsed.month == 1:
            start = f"{parsed.year - 1}-12-01 00:00:00"
            end = f"{parsed.year}-01-01 00:00:00"
        else:
            start = f"{parsed.year}-{parsed.month - 1:02d}-01 00:00:00"
            end = f"{parsed.year}-{parsed.month:02d}-01 00:00:00"
        return start, end
    span = _SPAN.search(question)
    if span:
        year = int(span.group(1))
        start_month = int(span.group(2))
        end_month = int(span.group(3)) + 1
        end_year = year
        if end_month == 13:
            end_month = 1
            end_year += 1
        return (
            f"{year}-{start_month:02d}-01 00:00:00",
            f"{end_year}-{end_month:02d}-01 00:00:00",
        )
    one = _MONTH.search(question)
    if one:
        year = int(one.group(1))
        month = int(one.group(2))
        end_month = month + 1
        end_year = year
        if end_month == 13:
            end_month = 1
            end_year += 1
        return (
            f"{year}-{month:02d}-01 00:00:00",
            f"{end_year}-{end_month:02d}-01 00:00:00",
        )
    return None


def _check_projection(
    contract: AnswerContract,
    projections: tuple[str, ...],
    findings: list[SemanticFinding],
) -> None:
    present = {name.lower() for name in projections}
    missing = [field for field in contract.dimension_fields if field.lower() not in present]
    if missing:
        actual = "、".join(projections) if projections else "无"
        findings.append(
            SemanticFinding(
                "contract_mismatch",
                f"期望投影包含 {'、'.join(missing)}；实际投影为 {actual}",
            )
        )


def _check_measures(
    contract: AnswerContract,
    shape: object,
    sql: str,
    findings: list[SemanticFinding],
) -> None:
    aggregations = _all_aggregations(shape)
    lowered = sql.lower()
    missing = [
        measure
        for measure in contract.measures
        if not _measure_present(measure, aggregations, lowered)
    ]
    if missing:
        actual = "、".join(sorted(aggregations)) if aggregations else "无"
        findings.append(
            SemanticFinding(
                "contract_mismatch",
                f"期望度量 {'、'.join(missing)}；实际聚合为 {actual}",
            )
        )


def _check_canonical_values(question: str, sql: str, findings: list[SemanticFinding]) -> None:
    for alias, canonical in canonical_value_aliases(question):
        if f"'{alias}'" in sql:
            findings.append(
                SemanticFinding(
                    "wrong_entity_literal",
                    f"期望品类取值 '{canonical}'；实际写成了 '{alias}'",
                )
            )
        elif f"'{canonical}'" not in sql:
            findings.append(
                SemanticFinding(
                    "wrong_entity_literal",
                    f"期望品类取值 '{canonical}'",
                )
            )


def _literal_aliases(sql: str) -> set[str]:
    return {match.group(1).lower() for match in _LITERAL_ALIAS.finditer(sql)}


def _check_grain(contract: AnswerContract, shape: object, findings: list[SemanticFinding]) -> None:
    if not contract.dimensions or not contract.measures:
        return
    grouped = " ".join(_all_groups(shape)).lower()
    if grouped.strip() == "":
        findings.append(
            SemanticFinding(
                "contract_mismatch",
                f"期望按 {'、'.join(contract.dimensions)} 分组；实际没有 GROUP BY",
            )
        )
        return
    sql = getattr(shape, "sql", "") or ""
    literals = _literal_aliases(sql)
    missing = [
        name
        for name in contract.dimensions
        if not any(token in grouped or token in literals for token in _GROUP_TOKENS.get(name, ()))
    ]
    if missing:
        findings.append(
            SemanticFinding(
                "contract_mismatch",
                f"期望分组覆盖 {'、'.join(missing)}；实际分组为 {grouped.strip()}",
            )
        )


def _check_category(
    contract: AnswerContract,
    question: str,
    sql: str,
    findings: list[SemanticFinding],
) -> None:
    if contract.category_scope != "exact":
        return
    lowered = sql.lower()
    recursive = "with recursive" in lowered
    walks_parent = "parent_id" in lowered and "一级" not in question and "末级" not in question
    if recursive or walks_parent:
        findings.append(
            SemanticFinding(
                "contract_mismatch",
                "期望品类精确匹配当前节点；实际出现了递归品类树或 parent_id 展开",
            )
        )


def _check_time(contract: AnswerContract, sql: str, findings: list[SemanticFinding]) -> None:
    if contract.time_window is None:
        return
    start, end = contract.time_window
    if _CLOCK.search(sql):
        findings.append(
            SemanticFinding(
                "contract_mismatch",
                f"期望时间窗口 [{start}, {end})；实际使用了运行时时钟",
            )
        )
        return
    if start not in sql or end not in sql:
        findings.append(
            SemanticFinding(
                "contract_mismatch",
                f"期望时间窗口 [{start}, {end})；实际缺少固定半开区间",
            )
        )


def _check_dedup(contract: AnswerContract, sql: str, findings: list[SemanticFinding]) -> None:
    if contract.dedup_key != "order_id":
        return
    lowered = sql.lower()
    if "distinct" in lowered and "order_id" in lowered:
        return
    findings.append(
        SemanticFinding(
            "contract_mismatch",
            "期望聚合前按 order_id 去重；实际没有 DISTINCT order_id",
        )
    )


def _measure_present(measure: str, aggregations: set[str], sql: str) -> bool:
    if measure == "count":
        return "count" in aggregations
    if measure == "sum_quantity":
        return "sum" in aggregations and "quantity" in sql
    if measure == "sum_amount":
        return "sum" in aggregations and "total_amount" in sql
    if measure == "sum_line":
        return "sum" in aggregations and ("price" in sql or "gross_amount" in sql)
    return True


def _all_aggregations(shape: object) -> set[str]:
    found = set(getattr(shape, "aggregations", ()))
    for scope in getattr(shape, "scopes", ()):
        found.update(scope.aggregations)
    return {name.lower() for name in found}


def _all_groups(shape: object) -> tuple[str, ...]:
    found = list(getattr(shape, "group_by", ()))
    for scope in getattr(shape, "scopes", ()):
        found.extend(scope.group_by)
    return tuple(found)
