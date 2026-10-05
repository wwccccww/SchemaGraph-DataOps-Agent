"""按当前库的表名和列名选择种子。不查询其他库的向量索引。"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.retrieval.dynamic import lexical_seed_tiers
from app.schemas.catalog import TableDocument
from app.schemas.retrieval import SchemaSeed

FALLBACK_SEED_CAP = 12
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
# 只在词汇种子为空时使用。电商问数仍走原有中文注释检索，不会读到这里。
_HINTS = (
    ("顾客", "customer"),
    ("客户", "customer"),
    ("住址", "address"),
    ("地址", "address"),
    ("商品", "item"),
    ("类别", "category"),
    ("门店", "store"),
    ("商店", "store"),
    ("销售", "sales"),
    ("金额", "sales"),
    ("日期", "date"),
    ("库存", "inventory"),
    ("仓库", "warehouse"),
    ("网页", "web"),
    ("目录", "catalog"),
    ("促销", "promotion"),
    ("退货", "return"),
    ("订单", "order"),
)


def lexical_schema_seeds(
    question: str,
    documents: Sequence[TableDocument],
) -> tuple[SchemaSeed, ...]:
    """先用词汇命中。没有命中时，按名称重合度保留最多 12 张非 Junction 表。"""

    if not documents:
        return ()
    database_id = documents[0].database_id
    if any(document.database_id != database_id for document in documents):
        raise ValueError("schema seeds refuse a mixed database catalog")
    by_name = {document.table_name: document for document in documents}
    tiers = lexical_seed_tiers(question, documents)
    if tiers:
        ordered = sorted(tiers, key=lambda name: (-tiers[name], name))
        return tuple(
            _seed(by_name[name], float(tiers[name])) for name in ordered if name in by_name
        )
    entities = [document for document in documents if not document.is_junction]
    ranked = sorted(
        entities,
        key=lambda document: (-_name_overlap(question, document), document.table_name),
    )
    return tuple(
        _seed(document, float(_name_overlap(question, document)))
        for document in ranked[:FALLBACK_SEED_CAP]
    )


def _seed(document: TableDocument, score: float) -> SchemaSeed:
    return SchemaSeed(
        database_id=document.database_id,
        schema_name=document.schema_name,
        table_name=document.table_name,
        content_hash=document.content_hash,
        embedding_model="lexical",
        embedding_version="none",
        score=score,
    )


def _name_overlap(question: str, document: TableDocument) -> int:
    tokens = _question_tokens(question)
    if not tokens:
        return 0
    names = [document.table_name, *[column.name for column in document.columns]]
    haystack: set[str] = set()
    for name in names:
        haystack.update(_tokens(name))
    return len(tokens & haystack)


def _question_tokens(question: str) -> set[str]:
    tokens = _tokens(question)
    for hint, fragment in _HINTS:
        if hint in question:
            tokens.add(fragment)
    return tokens


def _tokens(text: str) -> set[str]:
    found: set[str] = set()
    for token in _TOKEN.findall(text):
        lowered = token.lower()
        found.add(lowered)
        found.update(part for part in lowered.split("_") if len(part) >= 3)
    return found
