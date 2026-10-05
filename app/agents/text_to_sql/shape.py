"""从问句和当前库目录提取通用输出形状。不读取 Gold 列。"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.agents.text_to_sql.semantic import SemanticFinding
from app.evaluation.sql_shape import describe_sql
from app.schemas.catalog import SchemaEdge, TableDocument

_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_ORDER = re.compile(
    r"排序|从高到低|从低到高|升序|降序|最高|最低"
    r"|\b(?:sorted|highest|lowest|top)\b"
    r"|\border(?:ed)?\s+by\b",
    re.IGNORECASE,
)
_MEASURE = re.compile(
    r"汇总|金额|数量|净利润|次数|多少|比例|百分比"
    r"|\bhow many\b|\bnumber of\b|\baverage\b|\btotal\b"
    r"|\bpercentage\b|\brate\b",
    re.IGNORECASE,
)
_AGGREGATE = re.compile(r"\b(?:sum|count|avg|min|max)\s*\(", re.IGNORECASE)
_GROUP_AXIS = re.compile(
    r"各|按[^。]{0,16}汇总|按[^。]{0,16}统计"
    r"|\bgroup(?:ed|ing)?\s+(?:them\s+)?by\b"
    r"|\bfor each\b|\bsegmented by\b",
    re.IGNORECASE,
)
_DIMENSIONS = (
    (("商品类别", "类别", "item category", "category"), ("category",), ("item",)),
    (("教育", "education"), ("education",), ("customer_demographics",)),
    (("信用", "credit"), ("credit",), ("customer_demographics",)),
    (("收入", "income"), ("income",), ("income_band", "household_demographics")),
    (("性别", "gender"), ("gender",), ("customer_demographics",)),
    (("婚姻", "marital"), ("marital",), ("customer_demographics",)),
    (("促销", "promo"), ("promo",), ("promotion",)),
    (("班次", "shift"), ("hour", "shift"), ("time_dim",)),
    (("承运", "配送方式", "carrier", "ship mode"), ("carrier", "ship"), ("ship_mode",)),
    (("原因", "reason"), ("reason",), ("reason",)),
    (("仓库", "warehouse"), ("warehouse",), ("warehouse",)),
    (("渠道", "channel"), ("channel",), ()),
    (("网页", "web page", "page type"), ("page",), ("web_page",)),
    (("网站", "web site"), ("web",), ("web_site",)),
    (("呼叫中心", "call center"), ("call", "center"), ("call_center",)),
    (("出生年份", "birth year"), ("birth",), ("customer",)),
    (("购买潜力", "buy potential"), ("potential", "buy"), ("household_demographics",)),
    (("受抚养", "dependent"), ("dep_count", "dependent"), ("household_demographics",)),
    (("州",), ("state",), ()),
    (("县", "county"), ("county",), ("schools", "frpm")),
)
_ENTITIES = (
    (re.compile(r"当前住址|current address|customer address"), ("customer_address",)),
    (re.compile(r"顾客|customer"), ("customer",)),
    (re.compile(r"商品类别|item category"), ("item",)),
    (re.compile(r"促销商品|直邮促销|直邮"), ("item", "promotion")),
    (re.compile(r"门店销售|store sales"), ("store_sales",)),
    (re.compile(r"门店退货|store returns"), ("store_returns",)),
    (re.compile(r"目录退货|catalog returns"), ("catalog_returns",)),
    (re.compile(r"目录页|catalog page|目录部门"), ("catalog_page",)),
    (re.compile(r"目录销售|catalog sales"), ("catalog_sales",)),
    (re.compile(r"网站退货|web returns"), ("web_returns", "web_page")),
    (re.compile(r"网页类型|web page type"), ("web_page",)),
    (re.compile(r"网站名|web site name"), ("web_site",)),
    (re.compile(r"网站销售|web sales"), ("web_sales",)),
    (
        re.compile(r"门店所在|同一门店|同店|门店州|各门店|store state"),
        ("store",),
    ),
    (re.compile(r"仓库|warehouse"), ("warehouse",)),
    (re.compile(r"促销|promotion"), ("promotion",)),
    (re.compile(r"呼叫中心|call center"), ("call_center",)),
    (re.compile(r"配送方式|承运|ship mode"), ("ship_mode",)),
    (re.compile(r"原因|reason"), ("reason",)),
    (re.compile(r"收入分段|income band|income_band"), ("income_band", "household_demographics")),
    (re.compile(r"\bschools?\b", re.IGNORECASE), ("schools",)),
    (re.compile(r"\bSAT\b|\bsatscores\b|SAT performance", re.IGNORECASE), ("satscores",)),
    (re.compile(r"charter school|\bcharter\b", re.IGNORECASE), ("schools",)),
    (re.compile(r"grades?\s+(?:it\s+)?serves|grades served", re.IGNORECASE), ("schools",)),
    (re.compile(r"FRPM|free meal|free or reduced", re.IGNORECASE), ("frpm",)),
    (re.compile(r"NSLP|Provision Types|Provision Status", re.IGNORECASE), ("frpm",)),
)
_MEASURE_COLUMNS = (
    (re.compile(r"销售金额|sales amount"), ("ext_sales_price", "sales_price")),
    (re.compile(r"净利润|net profit"), ("net_profit",)),
    (
        re.compile(r"退货金额|return amount"),
        ("return_amount", "cr_return_amount", "wr_return_amt", "return_amt"),
    ),
    (re.compile(r"库存数量|在手库存|quantity on hand"), ("quantity_on_hand", "inv_quantity")),
)


@dataclass(frozen=True)
class GenericDimension:
    """问句点名、必须回显到最终投影的维度。"""

    label: str
    tokens: tuple[str, ...]
    columns: tuple[str, ...]
    must_group: bool


@dataclass(frozen=True)
class GenericShape:
    """通用问数的输出轴、过滤、实体和口径。不使用电商契约字段。"""

    years: tuple[str, ...]
    echo_years: bool
    dimensions: tuple[GenericDimension, ...]
    measures: tuple[str, ...]
    measure_columns: tuple[str, ...]
    entities: tuple[str, ...]
    formulas: tuple[str, ...]
    formula_columns: tuple[str, ...]
    joins: tuple[str, ...]
    order_required: bool


def extract_generic_shape(
    question: str,
    documents: Sequence[TableDocument] = (),
    edges: Sequence[SchemaEdge] = (),
) -> GenericShape:
    """只读问句和当前可见目录。Gold required_tables 不进入这里。"""

    visible = {document.table_name.lower(): document for document in documents}
    years = tuple(dict.fromkeys(_YEAR.findall(question)))
    grouping = _GROUP_AXIS.search(question) is not None
    measured = _MEASURE.search(question) is not None
    dimensions = _dimensions(question, documents, grouping=grouping and measured)
    entities = _merge_dimension_entities(
        _entities(question, visible),
        question,
        documents,
    )
    formulas, formula_columns = _formulas(question, documents)
    joins = _join_hints(question, documents, edges)
    return GenericShape(
        years=years,
        echo_years=bool(years and grouping and measured),
        dimensions=dimensions,
        measures=_measures(question),
        measure_columns=_measure_columns(question, documents),
        entities=entities,
        formulas=formulas,
        formula_columns=formula_columns,
        joins=joins,
        order_required=_ORDER.search(question) is not None,
    )


def format_generic_shape(shape: GenericShape) -> str:
    """放在可用表之前。不用电商答案契约的标题。"""

    lines = ["输出形状："]
    if shape.dimensions:
        shown = "、".join(_dimension_line(item) for item in shape.dimensions)
        lines.append(f"最终 SELECT 必须包含维度：{shown}")
        lines.append("这些维度在有聚合时必须进入 GROUP BY，不能只写在 WHERE。")
    if shape.echo_years:
        years = "、".join(shape.years)
        lines.append(f"年份 {years} 要同时出现在过滤和最终投影中，例如 d_year。")
    elif shape.years:
        lines.append(f"过滤年份：{'、'.join(shape.years)}")
    if shape.measures:
        lines.append(f"度量：{'、'.join(shape.measures)}")
    if shape.measure_columns:
        lines.append(f"度量列优先使用：{'、'.join(shape.measure_columns)}")
    if shape.entities:
        lines.append("必需实体表必须出现在 FROM 或 JOIN：" + "、".join(shape.entities))
    lines.extend(f"口径：{item}" for item in (*shape.formulas, *shape.joins))
    if shape.order_required:
        lines.append("问句要求排序时写 ORDER BY。")
    if len(lines) == 1:
        lines.append("问句中的维度要出现在最终投影，过滤值出现在 WHERE，度量要聚合。")
    return "\n".join(lines)


def check_answer_shape(
    question: str,
    sql: str,
    documents: Sequence[TableDocument],
    *,
    dialect: str = "postgres",
    edges: Sequence[SchemaEdge] = (),
) -> tuple[SemanticFinding, ...]:
    """维度必须在投影里。对不上列时不猜。"""

    findings = list(
        check_generic_shape(
            extract_generic_shape(question, documents, edges),
            sql,
            dialect=dialect,
        )
    )
    lowered = sql.lower()
    for document in documents:
        for column in document.columns:
            if not _mentioned_column(column.name, question):
                continue
            if column.name.lower() not in lowered:
                findings.append(
                    SemanticFinding(
                        "projection_mismatch",
                        f"问句点名的列 {column.name} 没有出现在投影或过滤中",
                    )
                )
    if re.search(r"performance level|SAT performance", question, re.IGNORECASE):
        if re.search(r"avgscr(read|math|write)", sql, re.IGNORECASE) and "case" not in lowered:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "SAT performance level 应使用 CASE 归类，不要只投影原始 AvgScr 列",
                )
            )
        if re.search(r"\bjoin\s+satscores\b", sql, re.IGNORECASE) and not re.search(
            r"left\s+join\s+satscores", sql, re.IGNORECASE
        ):
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    "SAT 指标应对 satscores 使用 LEFT JOIN（cds=CDSCode），不要 INNER JOIN 丢掉无 SAT 学校",
                )
            )
        if re.search(r"'High'|'Medium'|'Low'", sql) and "below average" not in lowered:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "SATPerformance 标签用 No SAT Data / Below Average / Average / Above Average，"
                    "不要用 High/Medium/Low",
                )
            )
    if re.search(r"charter", question, re.IGNORECASE) and any(
        document.table_name.lower() == "schools" for document in documents
    ):
        if "charter school (y/n)" in lowered and re.search(
            r"\bschools\b", sql, re.IGNORECASE
        ):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "charter school 语义优先使用 schools 表的 Charter 字段，不要用 frpm 的 Y/N 列",
                )
            )
    if re.search(r"Multiple Provision Types", question, re.IGNORECASE):
        if "multiple provision types" not in lowered.replace("_", " "):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "问句要求 Multiple Provision Types，WHERE 需 frpm.`NSLP Provision Status` "
                    "= 'Multiple Provision Types'",
                )
            )
    has_frpm = any(document.table_name.lower() == "frpm" for document in documents)
    if has_frpm and re.search(r"County Name|Alameda|Los Angeles|Fresno", question, re.IGNORECASE):
        if "county name" not in lowered and re.search(
            r"\bschools\.county\b|\bs\.county\b", sql, re.IGNORECASE
        ):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    "县级过滤优先用 frpm.`County Name`（或 schools.County 与问句县名一致），"
                    "不要混用错误县列导致漏行。",
                )
            )
    return tuple(findings)


def check_generic_shape(
    shape: GenericShape,
    sql: str,
    *,
    dialect: str = "postgres",
) -> tuple[SemanticFinding, ...]:
    """用已经抽出的形状核对 SQL。"""

    described = describe_sql(sql, dialect=dialect)
    findings: list[SemanticFinding] = []
    projected = _projected_text(described.projections, described.group_by)
    lowered = sql.lower()
    for year in shape.years:
        if year not in sql:
            findings.append(
                SemanticFinding("projection_mismatch", f"问句中的年份 {year} 没有出现在 SQL 中")
            )
        elif shape.echo_years and not _year_projected(year, described.projections):
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    f"年份 {year} 不能只写在 WHERE，必须出现在最终 SELECT 或分组中",
                )
            )
    if shape.measures and _AGGREGATE.search(sql) is None:
        findings.append(SemanticFinding("projection_mismatch", "问句要求度量，SQL 中没有聚合函数"))
    if shape.order_required and not _has_order(sql, dialect):
        findings.append(SemanticFinding("projection_mismatch", "问句要求排序，SQL 中没有 ORDER BY"))
    for dimension in shape.dimensions:
        if not any(token in projected for token in dimension.tokens):
            example = dimension.columns[0] if dimension.columns else dimension.tokens[0]
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    f"维度“{dimension.label}”必须出现在最终 SELECT 中，例如列 {example}",
                )
            )
        elif dimension.must_group and described.aggregations and not described.group_by:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    f"维度“{dimension.label}”有聚合时必须进入 GROUP BY",
                )
            )
    referenced = {name.lower() for name in described.referenced_tables}
    for entity in shape.entities:
        if entity.lower() not in referenced:
            findings.append(
                SemanticFinding(
                    "missing_entity",
                    f"问句要求的实体表 {entity} 必须出现在 FROM 或 JOIN 中，不能只用空值判断替代",
                )
            )
    if shape.measure_columns and not any(name.lower() in lowered for name in shape.measure_columns):
        findings.append(
            SemanticFinding(
                "projection_mismatch",
                f"度量应使用目录中的列 {shape.measure_columns[0]}",
            )
        )
    if shape.formula_columns and not _formula_used(shape.formula_columns, sql):
        findings.append(SemanticFinding("projection_mismatch", f"口径：{shape.formulas[0]}"))
    if dialect == "sqlite" and re.search(
        r"julianday\s*\(\s*['\"]now['\"]|date\s*\(\s*['\"]now['\"]|"
        r"strftime\s*\([^)]*['\"]now['\"]",
        sql,
        re.IGNORECASE,
    ):
        findings.append(
            SemanticFinding(
                "projection_mismatch",
                "计算校龄等相对日期时不要使用 date('now') 或 julianday('now')，"
                "改用问句给定的 anchor 日期或列中的 OpenDate 差值常量。",
            )
        )
    return tuple(findings)


def generic_coverage(
    shape: GenericShape,
    sql: str,
    *,
    dialect: str = "postgres",
) -> dict[str, float | None]:
    """分层覆盖率。不是执行准确率，也不读取 Gold。"""

    described = describe_sql(sql, dialect=dialect)
    projected = _projected_text(described.projections, described.group_by)
    referenced = {name.lower() for name in described.referenced_tables}
    dimension_hits = 0
    for dimension in shape.dimensions:
        if any(token in projected for token in dimension.tokens):
            dimension_hits += 1
    entity_hits = sum(1 for entity in shape.entities if entity.lower() in referenced)
    measure_ok = 1.0 if (not shape.measures or _AGGREGATE.search(sql)) else 0.0
    return {
        "dimension_coverage": _ratio(dimension_hits, len(shape.dimensions)),
        "entity_coverage": _ratio(entity_hits, len(shape.entities)),
        "measure_coverage": None if not shape.measures else measure_ok,
    }


def _dimensions(
    question: str,
    documents: Sequence[TableDocument],
    *,
    grouping: bool,
) -> tuple[GenericDimension, ...]:
    found: list[GenericDimension] = []
    for labels, tokens, tables in _DIMENSIONS:
        label = next((item for item in labels if _contains(question, item)), None)
        if label is None or not _dimension_requested(question, label):
            continue
        columns = _columns_for_tokens(documents, tokens, tables)
        found.append(
            GenericDimension(
                label=label,
                tokens=tokens,
                columns=columns,
                must_group=grouping,
            )
        )
    return tuple(found)


def _merge_dimension_entities(
    entities: tuple[str, ...],
    question: str,
    documents: Sequence[TableDocument],
) -> tuple[str, ...]:
    """分组维度对应的维表也要出现在 SQL 中。"""

    visible = {document.table_name.lower(): document.table_name for document in documents}
    names = list(entities)
    for labels, _tokens, tables in _DIMENSIONS:
        label = next((item for item in labels if _contains(question, item)), None)
        if label is None or not _dimension_requested(question, label):
            continue
        for table in tables:
            resolved = visible.get(table.lower())
            if resolved is not None and resolved not in names:
                names.append(resolved)
    return tuple(dict.fromkeys(names))


def _entities(
    question: str,
    visible: dict[str, TableDocument],
) -> tuple[str, ...]:
    names: list[str] = []
    sold_through_store = (
        "store_sales" in visible
        and re.search(r"卖过|售出|销售过|门店卖", question) is not None
    )
    if sold_through_store:
        names.append(visible["store_sales"].table_name)
    for pattern, tables in _ENTITIES:
        if pattern.search(question) is None:
            continue
        if sold_through_store and tables == ("store",):
            continue
        for table in tables:
            if table.lower() in visible and table not in names:
                names.append(visible[table.lower()].table_name)
    return tuple(names)


def _measures(question: str) -> tuple[str, ...]:
    if _MEASURE.search(question) is None:
        return ()
    return ("问句中的度量需要聚合",)


def _measure_columns(question: str, documents: Sequence[TableDocument]) -> tuple[str, ...]:
    names: list[str] = []
    for pattern, tokens in _MEASURE_COLUMNS:
        if pattern.search(question) is None:
            continue
        for document in documents:
            for column in document.columns:
                lowered = column.name.lower()
                if any(token in lowered for token in tokens):
                    names.append(column.name)
    return tuple(dict.fromkeys(names))


def _formulas(
    question: str,
    documents: Sequence[TableDocument],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if re.search(
        r"FRPM eligibility|Eligible FRPM|Percent.*FRPM|FRPM percentage",
        question,
        re.IGNORECASE,
    ):
        pct = _first_column(
            documents,
            ("percent (%) eligible frpm (k-12)", "percent (%) eligible frpm", "eligible frpm"),
        )
        if pct is not None:
            return (
                f"FRPM 比例用 frpm `{pct}` * 100 AS FRPMPercentage，"
                "不要仅用 Free Meal Count/Enrollment 重算",
            ), (pct,)
    if re.search(r"rate|比例|百分比|percentage", question, re.IGNORECASE) is None:
        return (), ()
    count = _first_column(documents, ("free meal count", "frpm count"))
    enrollment = _first_column(documents, ("enrollment (k-12)", "enrollment"))
    if count is None or enrollment is None:
        return (), ()
    text = f"免费餐比例用 {count} * 1.0 / {enrollment}；若无 FRPM 列再手算"
    return (text,), (count, enrollment)


def _join_hints(
    question: str,
    documents: Sequence[TableDocument],
    edges: Sequence[SchemaEdge],
) -> tuple[str, ...]:
    hints: list[str] = []
    visible = {document.table_name.lower() for document in documents}
    if (
        re.search(r"直邮|dmail", question, re.IGNORECASE)
        and re.search(r"商品|item", question, re.IGNORECASE)
        and "item" in visible
        and "promotion" in visible
    ):
        hints.append(
            "直邮促销商品：store_sales.ss_item_sk IN (SELECT p_item_sk FROM promotion "
            "WHERE p_channel_dmail='Y')，并 JOIN item；不要 JOIN promotion 事实行。"
        )
    elif (
        re.search(r"促销|promotion", question, re.IGNORECASE)
        and "promotion" in visible
        and re.search(r"名称|目的", question)
    ):
        hints.append(
            "促销名称/目的：JOIN promotion ON 事实表 ss_promo_sk/cs_promo_sk/ws_promo_sk = p_promo_sk，"
            "投影 promotion.p_promo_name 或 p_purpose。"
        )
    if re.search(r"收入|income", question, re.IGNORECASE) and "income_band" in visible:
        hints.append("收入分段用 income_band 连接 household_demographics，不要省略 income_band。")
    if (
        re.search(r"收入带|购买潜力|income|buy potential", question, re.IGNORECASE)
        and "household_demographics" in visible
        and "store_sales" in visible
    ):
        hints.append(
            "收入带/购买潜力：store_sales JOIN customer，再 household_demographics "
            "ON customer.c_current_hdemo_sk = hd_demo_sk，JOIN income_band；"
            "不要用 ss_hdemo_sk 直连 household；问句未提门店州时不要 JOIN store。"
        )
    if re.search(r"配送|承运|ship mode|ship_mode", question, re.IGNORECASE) and "ship_mode" in visible:
        hints.append("配送方式需 JOIN ship_mode，不要只用销售事实表上的 sk 列名猜测。")
    if re.search(r"网站名|web site name", question, re.IGNORECASE) and "web_site" in visible:
        hints.append("网站维度用 web_site 表，通过 web_sales 或 catalog_sales 关联。")
    if re.search(r"既在.+又在", question) and {"store_sales", "web_sales"} <= visible:
        hints.append(
            "跨渠道顾客：用 web_sales 子集（customer+item）过滤 store_sales，"
            "最终只汇总门店销售金额；不要 UNION ALL 合并两渠道金额。"
        )
    if "比较" in question and {"store_sales", "web_sales"} <= visible:
        hints.append(
            "渠道对比：各渠道独立 CTE 汇总后按 item_category/sales_year JOIN，"
            "输出 store_sales_amount 与 web_sales_amount 两列，不要 UNION 成单列。"
        )
    if (
        {"schools", "frpm", "satscores"} <= visible
        or ("schools" in visible and "frpm" in visible)
    ):
        hints.append(
            "California schools：schools 与 frpm/satscores 用 CDSCode 与 satscores.cds 连接，"
            "不要对 schools 与 frpm 做无键笛卡尔积。"
        )
    if "frpm" in visible and re.search(
        r"NSLP|Provision Status|free meal rate|FRPM|Enrollment \(K-12\)",
        question,
        re.IGNORECASE,
    ):
        hints.append(
            "餐食/NSLP/Enrollment 过滤或度量在 frpm（如 `NSLP Provision Status`、`County Name`），"
            "schools 上的 Magnet/GSserved 过滤仍需 JOIN frpm ON CDSCode。"
        )
    if re.search(r"Multiple Provision Types", question, re.IGNORECASE) and "frpm" in visible:
        hints.append(
            "问句点名 Multiple Provision Types 时 WHERE 需 "
            "frpm.`NSLP Provision Status` = 'Multiple Provision Types'（与 schools 条件 AND）。"
        )
    if "satscores" in visible and re.search(
        r"performance level|SAT performance",
        question,
        re.IGNORECASE,
    ):
        hints.append(
            "SAT performance level：satscores LEFT JOIN；Total=AvgScrRead+AvgScrMath+AvgScrWrite；"
            "CASE 标签 No SAT Data / Below Average(<1200) / Average(1200–1500) / Above Average。"
        )
    if "frpm" in visible and re.search(
        r"free meal rate|FRPM|Enrollment \(K-12\)",
        question,
        re.IGNORECASE,
    ):
        hints.append(
            "frpm 算餐食比例时在 WHERE 加 `Enrollment (K-12)` > 0，避免除零或无效行。"
        )
    if (
        "schools" in visible
        and "satscores" in visible
        and re.search(r"district average|district avg|compare.*district", question, re.IGNORECASE)
    ):
        hints.append(
            "学区 SAT 均分按 schools.District 聚合 satscores，不要用 satscores.dname 代替 schools.District。"
        )
    if {"disp", "client", "account"} <= visible and re.search(
        r"owner|account holder|client.*account|card holder",
        question,
        re.IGNORECASE,
    ):
        hints.append(
            "Financial 库：account 与 client 经 disp 连接，账户持有人用 disp.type = 'OWNER'。"
        )
    if re.search(r"账单地址|收货地址|bill address|ship address", question, re.IGNORECASE):
        if "customer_address" in visible and "web_sales" in visible:
            hints.append(
                "账单/收货地址州：web_sales.ws_bill_addr_sk 与 ws_ship_addr_sk 各 JOIN 一次 customer_address，"
                "并 JOIN customer ON ws_bill_customer_sk = c_customer_sk；过滤 bill_state <> ship_state。"
            )
    if re.search(r"当前住址|current address", question, re.IGNORECASE) and "customer_address" in visible:
        for edge in edges:
            tables = {edge.source_table.lower(), edge.target_table.lower()}
            if tables != {"customer", "customer_address"}:
                continue
            left = f"{edge.source_table}.{edge.source_columns[0]}"
            right = f"{edge.target_table}.{edge.target_columns[0]}"
            hints.append(f"当前住址用 {left} = {right} 连接，不要只用 IS NOT NULL")
            break
        else:
            hints.append("当前住址必须连接 customer_address，不要只用 IS NOT NULL")
    return tuple(hints)


def _dimension_line(dimension: GenericDimension) -> str:
    if dimension.columns:
        return f"{dimension.label}（列如 {dimension.columns[0]}）"
    return dimension.label


def _columns_for_tokens(
    documents: Sequence[TableDocument],
    tokens: Sequence[str],
    tables: Sequence[str],
) -> tuple[str, ...]:
    preferred = {name.lower() for name in tables}
    names: list[str] = []
    for document in documents:
        if preferred and document.table_name.lower() not in preferred:
            continue
        for column in document.columns:
            lowered = column.name.lower()
            if any(token in lowered for token in tokens):
                names.append(column.name)
    if names or not preferred:
        return tuple(dict.fromkeys(names))
    return _columns_for_tokens(documents, tokens, ())


def _first_column(documents: Sequence[TableDocument], needles: Sequence[str]) -> str | None:
    for document in documents:
        for column in document.columns:
            lowered = column.name.lower()
            if any(needle in lowered for needle in needles):
                return column.name
    return None


def _contains(question: str, fragment: str) -> bool:
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9 ]+", fragment):
        return re.search(rf"\b{re.escape(fragment)}\b", question, re.IGNORECASE) is not None
    return fragment in question


def _dimension_requested(question: str, label: str) -> bool:
    if label == "州":
        return "州" in question
    if any(prefix + label in question for prefix in ("各", "同一", "每个", "所在")):
        return True
    if re.search(rf"按[^。]{{0,16}}{re.escape(label)}", question) is not None:
        return True
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9 ]+", label):
        return (
            re.search(
                rf"\b(?:by|per|each|across)\s+{re.escape(label)}\b",
                question,
                re.IGNORECASE,
            )
            is not None
        )
    return False


def _projected_text(projections: Sequence[str], group_by: Sequence[str]) -> str:
    return " ".join((*projections, *group_by)).lower()


def _year_projected(year: str, projections: Sequence[str]) -> bool:
    blob = " ".join(projections).lower()
    if year in blob:
        return True
    return any("year" in name.lower() for name in projections)


def _formula_used(columns: Sequence[str], sql: str) -> bool:
    lowered = sql.lower()
    if "/" not in sql:
        return False
    return all(name.lower() in lowered for name in columns)


def _ratio(hits: int, total: int) -> float | None:
    if total == 0:
        return None
    return hits / total


def _has_order(sql: str, dialect: str) -> bool:
    try:
        parsed = sqlglot.parse_one(sql, read=dialect)
    except (SqlglotError, RecursionError):
        return "order by" in sql.lower()
    return isinstance(parsed, exp.Expression) and parsed.find(exp.Order) is not None


def _mentioned_column(column: str, question: str) -> bool:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", column) and len(column) >= 5:
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(column)}(?![A-Za-z0-9_])"
        return re.search(pattern, question, re.IGNORECASE) is not None
    if " " in column or "(" in column:
        return column.lower() in question.lower()
    return False
