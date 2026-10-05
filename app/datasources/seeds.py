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
    ("年份", "date"),
    ("年", "date"),
    ("库存", "inventory"),
    ("仓库", "warehouse"),
    ("网页", "web"),
    ("网站", "web"),
    ("目录", "catalog"),
    ("促销", "promotion"),
    ("退货", "return"),
    ("订单", "order"),
    ("原因", "reason"),
    ("收入", "income"),
    ("配送", "ship"),
    ("呼叫", "call"),
)
# 关键词命中后，表名里带这些片段的表必须进入种子，再由预算截断。
_CONCEPTS = (
    (("sat",), ("satscores",)),
    (("frpm", "meal"), ("frpm",)),
    (("loan",), ("loan",)),
    (("client",), ("client",)),
    (("card",), ("card",)),
    (("district",), ("district",)),
    (("transaction", "balance"), ("trans",)),
    (("account",), ("account",)),
    (("school",), ("school",)),
    (("日期", "年份", "year", "month", "年"), ("date",)),
    (("小时", "班次", "time"), ("time",)),
    (("顾客", "客户", "customer"), ("customer",)),
    (("住址", "地址", "address"), ("address",)),
    (("商品", "类别", "category", "item"), ("item",)),
    (("门店", "store"), ("store",)),
    (("目录", "catalog"), ("catalog",)),
    (("网站", "网页", "web"), ("web",)),
    (("销售", "金额", "购买", "净利润", "sales"), ("sales",)),
    (("退货", "return"), ("return", "reason")),
    (("库存", "inventory"), ("inventory",)),
    (("仓库", "warehouse"), ("warehouse",)),
    (("原因", "reason"), ("reason",)),
    (("促销", "promotion", "promo"), ("promo",)),
    (("收入", "income"), ("income", "household")),
    (("呼叫", "call"), ("call",)),
    (("配送", "承运", "ship"), ("ship",)),
    (("教育", "婚姻", "性别", "demographic"), ("demographic",)),
)


def lexical_schema_seeds(
    question: str,
    documents: Sequence[TableDocument],
) -> tuple[SchemaSeed, ...]:
    """词汇命中和概念表优先。整库不超过 12 张时保留全部非 Junction 表。"""

    if not documents:
        return ()
    database_id = documents[0].database_id
    if any(document.database_id != database_id for document in documents):
        raise ValueError("schema seeds refuse a mixed database catalog")
    entities = [document for document in documents if not document.is_junction]
    tiers = lexical_seed_tiers(question, documents)
    concepts = _concept_tables(question, entities)
    relevant = [
        document
        for document in entities
        if document.table_name in tiers
        or document.table_name in concepts
        or _table_name_overlap(question, document) > 0
    ]
    pool = entities if len(entities) <= FALLBACK_SEED_CAP or not relevant else relevant
    ranked = sorted(
        pool,
        key=lambda document: (
            -_seed_score(question, document, tiers, concepts),
            document.table_name,
        ),
    )
    return tuple(
        _seed(document, float(_seed_score(question, document, tiers, concepts)))
        for document in ranked[:FALLBACK_SEED_CAP]
    )


def _seed_score(
    question: str,
    document: TableDocument,
    tiers: dict[str, int],
    concepts: set[str],
) -> int:
    score = _name_overlap(question, document)
    if document.table_name in concepts:
        score += 10
    if document.table_name in tiers:
        score += 20
    return score


def _concept_tables(question: str, documents: Sequence[TableDocument]) -> set[str]:
    fired = [
        fragments
        for keywords, fragments in _CONCEPTS
        if any(_keyword_in_question(keyword, question) for keyword in keywords)
    ]
    if not fired:
        return set()
    names = [document.table_name for document in documents]
    selected: set[str] = set()
    for fragments in fired:
        matches = [name for name in names if _name_has_fragment(name, fragments)]
        if len(matches) <= 2:
            selected.update(matches)
            continue
        facts = [name for name in matches if name.lower().split("_")[-1] in {"sales", "returns"}]
        selected.update(name for name in matches if name not in set(facts))
        kept_facts = [name for name in facts if _keep_concept_match(name, fired, fragments)]
        selected.update(kept_facts or facts)
    return selected


def _keep_concept_match(
    table_name: str,
    fired: Sequence[tuple[str, ...]],
    fragments: tuple[str, ...],
) -> bool:
    tokens = table_name.lower().split("_")
    if tokens[-1] in {"sales", "returns"}:
        return any(
            _name_has_fragment(table_name, other) for other in fired if other is not fragments
        )
    return True


def _keyword_in_question(keyword: str, question: str) -> bool:
    if any("\u4e00" <= char <= "\u9fff" for char in keyword):
        return keyword in question
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(keyword)}(?![A-Za-z0-9_])"
    return re.search(pattern, question, re.IGNORECASE) is not None


def _name_has_fragment(table_name: str, fragments: Sequence[str]) -> bool:
    tokens = table_name.lower().split("_")
    for fragment in fragments:
        lowered = fragment.lower()
        if lowered in tokens:
            return True
        if any(token.startswith(lowered) and len(lowered) >= 4 for token in tokens):
            return True
    return False


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


def _table_name_overlap(question: str, document: TableDocument) -> int:
    tokens = _tokens(question)
    if not tokens:
        return 0
    return len(tokens & _tokens(document.table_name))


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
