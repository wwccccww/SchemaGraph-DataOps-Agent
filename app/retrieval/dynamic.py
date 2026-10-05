"""按问句里的表名和中文注释选择实体种子。

向量 Top-5 会把无关表补进只涉及一张表的问题。这里先收表名、表注释核心词、列注释和品类取值；
已支付、销售、销量会映射到列注释里的对应说法。没有任何命中时，才按向量分差保留，最多 5 张。
Junction Table 不能成为种子。required_tables 不能传进这个模块。
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.db.seed_data import LEAF_CATEGORIES, ROOT_CATEGORIES
from app.schemas.catalog import TableDocument

VECTOR_SEED_LIMIT = 5
VECTOR_SCORE_GAP = 0.02
_MAX_PHRASE = 8
_HAN_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")
_ASCII_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
_TABLE_AFFIXES = (
    "事实表",
    "维度表",
    "映射表",
    "维表",
    "主表",
    "基础",
    "行政",
    "入驻",
    "营销",
    "交易",
    "账户",
    "账号",
    "标准",
    "树",
    "表",
    "主",
)
# 问句里的业务词对应列注释用词。只补充注释里已经出现的说法，不读取评测标签。
_PHRASE_ALIASES: dict[str, tuple[str, ...]] = {
    "已支付": ("订单状态",),
    "已取消": ("订单状态",),
    "销售": ("实付", "售卖", "购买数量"),
    "销售额": ("实付", "售卖", "购买数量"),
    "销量": ("购买数量", "售卖"),
}
_GENERIC_PHRASES = frozenset(
    {
        "名称",
        "编号",
        "主键",
        "唯一",
        "关联",
        "注册",
        "状态",
        "类型",
        "金额",
        "单价",
        "价格",
        "时间",
        "时间戳",
        "流水",
        "快照",
        "活动",
        "门槛",
        "使用",
        "是否",
        "平台",
        "父级",
        "表示",
        "最终",
        "全部",
        "数量",
        "文本",
        "记录",
        "归属",
        "所属",
        "基础",
        "标准",
        "账号",
        "账户",
    }
)


@dataclass(frozen=True)
class SeedChoice:
    """一张被选中的实体表。score 把档位和向量分加在一起，只用于排序。"""

    table_name: str
    score: float
    tier: int


def choose_schema_seeds(
    question: str,
    documents: Sequence[TableDocument],
    vector_scores: Mapping[str, float] | None = None,
) -> tuple[SeedChoice, ...]:
    """返回种子表。调用方不要把 required_tables 或 Gold SQL 传进来。"""

    if question.strip() == "":
        raise ValueError("retrieval question must be non-empty")
    entities = _entity_documents(documents)
    scores = _finite_scores(vector_scores or {})
    cores = {name: core for name, document in entities.items() if (core := _table_core(document))}
    aliases = _alias_phrases(question)
    column_hits = {
        name: _maximal(_phrases_in_question(_column_text(document), question, aliases))
        for name, document in entities.items()
    }
    lexical = _lexical_tables(question, entities, cores, column_hits)
    if lexical:
        ordered = sorted(lexical, key=lambda name: (-lexical[name], -scores.get(name, 0.0), name))
        return tuple(_choice(name, lexical[name], scores.get(name, 0.0)) for name in ordered)
    return _vector_fallback(entities, scores)


def _entity_documents(documents: Sequence[TableDocument]) -> dict[str, TableDocument]:
    entities: dict[str, TableDocument] = {}
    for document in documents:
        if document.is_junction or document.table_name in entities:
            continue
        entities[document.table_name] = document
    return entities


def _finite_scores(vector_scores: Mapping[str, float]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for name, score in vector_scores.items():
        if math.isfinite(score):
            scores[name] = float(score)
    return scores


def _lexical_tables(
    question: str,
    entities: Mapping[str, TableDocument],
    cores: Mapping[str, str],
    column_hits: Mapping[str, set[str]],
) -> dict[str, int]:
    selected = {
        name: 2
        for name, document in entities.items()
        if _table_name_in_question(document.table_name, question)
        or (name in cores and cores[name] in question)
    }
    phrase_tables: dict[str, set[str]] = defaultdict(set)
    for name, phrases in column_hits.items():
        for phrase in phrases:
            phrase_tables[phrase].add(name)
    for phrase, tables in phrase_tables.items():
        owners = {name for name, core in cores.items() if phrase in core}
        if len(owners) == 1:
            chosen = owners
        elif owners:
            chosen = {name for name in owners if cores[name] == phrase or cores[name] in question}
        elif len(tables) <= 2:
            chosen = set(tables)
        else:
            chosen = set()
        for name in chosen:
            selected.setdefault(name, 1)
    return selected


def _vector_fallback(
    entities: Mapping[str, TableDocument],
    scores: Mapping[str, float],
) -> tuple[SeedChoice, ...]:
    ordered = sorted(
        (name for name in entities if name in scores),
        key=lambda name: (-scores[name], name),
    )
    if not ordered:
        return ()
    best = scores[ordered[0]]
    kept: list[str] = []
    for name in ordered:
        if len(kept) >= VECTOR_SEED_LIMIT:
            break
        if kept and best - scores[name] > VECTOR_SCORE_GAP:
            break
        kept.append(name)
    return tuple(_choice(name, 0, scores[name]) for name in kept)


def _choice(name: str, tier: int, vector: float) -> SeedChoice:
    return SeedChoice(table_name=name, score=float(tier) + vector, tier=tier)


def _table_core(document: TableDocument) -> str | None:
    if not document.table_comment:
        return None
    head = document.table_comment.split("[", 1)[0]
    han = "".join(re.findall(r"[\u4e00-\u9fff]", head))
    changed = True
    while changed and len(han) >= 2:
        changed = False
        for affix in _TABLE_AFFIXES:
            if len(han) - len(affix) < 2:
                continue
            if han.startswith(affix):
                han = han[len(affix) :]
                changed = True
                break
            if han.endswith(affix):
                han = han[: -len(affix)]
                changed = True
                break
    if len(han) < 2:
        return None
    return han


def _column_text(document: TableDocument) -> str:
    parts: list[str] = []
    for column in document.columns:
        parts.append(column.name)
        if column.comment:
            parts.append(column.comment)
        if column.name == "category_name":
            parts.extend(LEAF_CATEGORIES)
            parts.extend(ROOT_CATEGORIES)
    return " ".join(parts)


def _alias_phrases(question: str) -> set[str]:
    found: set[str] = set()
    for word, targets in _PHRASE_ALIASES.items():
        if word in question:
            found.update(targets)
    return found


def _phrases_in_question(text: str, question: str, aliases: set[str]) -> set[str]:
    found: set[str] = set()
    for run in _HAN_RUN.findall(text):
        longest = min(len(run), _MAX_PHRASE)
        for size in range(2, longest + 1):
            for start in range(0, len(run) - size + 1):
                piece = run[start : start + size]
                if piece in _GENERIC_PHRASES:
                    continue
                if piece in question or piece in aliases:
                    found.add(piece)
    for token in _ASCII_WORD.findall(text):
        letters = re.match(r"[A-Za-z]+", token)
        if letters is not None and _ascii_in_question(letters.group(0), question):
            found.add(letters.group(0))
        if token in _GENERIC_PHRASES or len(token) < 3:
            continue
        if _ascii_in_question(token, question):
            found.add(token)
    return found


def _ascii_in_question(phrase: str, question: str) -> bool:
    if len(phrase) < 3:
        return False
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(phrase)}(?![A-Za-z_])"
    return re.search(pattern, question) is not None


def _maximal(phrases: set[str]) -> set[str]:
    return {
        phrase
        for phrase in phrases
        if not any(phrase != other and phrase in other for other in phrases)
    }


def _table_name_in_question(table_name: str, question: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(table_name)}(?![A-Za-z0-9_])"
    return re.search(pattern, question) is not None
