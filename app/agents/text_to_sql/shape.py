"""从问句本身提取通用答案形状。不读取 Gold 列。"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.agents.text_to_sql.semantic import SemanticFinding
from app.schemas.catalog import TableDocument

_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_ORDER = re.compile(
    r"排序|从高到低|从低到高|升序|降序|最高|最低"
    r"|\b(?:sorted|highest|lowest|top)\b"
    r"|\border(?:ed)?\s+by\b",
    re.IGNORECASE,
)
_MEASURE = re.compile(
    r"汇总|金额|数量|净利润|次数|多少|\bhow many\b|\bnumber of\b|\baverage\b|\btotal\b",
    re.IGNORECASE,
)
_AGGREGATE = re.compile(r"\b(?:sum|count|avg|min|max)\s*\(", re.IGNORECASE)
_DIMENSIONS = (
    ("类别", "category"),
    ("教育", "education"),
    ("收入", "income"),
    ("性别", "gender"),
    ("促销", "promo"),
    ("班次", "hour"),
    ("承运", "carrier"),
    ("婚姻", "marital"),
    ("原因", "reason"),
    ("州", "state"),
    ("仓库", "warehouse"),
)


def check_answer_shape(
    question: str,
    sql: str,
    documents: Sequence[TableDocument],
    *,
    dialect: str = "postgres",
) -> tuple[SemanticFinding, ...]:
    """维度、度量、年份和排序必须能在 SQL 里找到。对不上列时不猜。"""

    findings: list[SemanticFinding] = []
    for year in dict.fromkeys(_YEAR.findall(question)):
        if year not in sql:
            findings.append(
                SemanticFinding("projection_mismatch", f"问句中的年份 {year} 没有出现在 SQL 中")
            )
    if _MEASURE.search(question) and _AGGREGATE.search(sql) is None:
        findings.append(SemanticFinding("projection_mismatch", "问句要求度量，SQL 中没有聚合函数"))
    if _ORDER.search(question) and not _has_order(sql, dialect):
        findings.append(SemanticFinding("projection_mismatch", "问句要求排序，SQL 中没有 ORDER BY"))
    lowered = sql.lower()
    for fragment, token in _DIMENSIONS:
        if fragment not in question:
            continue
        columns = [
            column.name
            for document in documents
            for column in document.columns
            if token in column.name.lower()
        ]
        if columns and token not in lowered:
            findings.append(
                SemanticFinding(
                    "projection_mismatch",
                    f"问句中的维度“{fragment}”应出现在投影或过滤中，例如列 {columns[0]}",
                )
            )
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
    return tuple(findings)


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
