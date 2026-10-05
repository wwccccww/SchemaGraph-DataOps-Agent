"""动态种子只看问句、表注释和列注释，不读取评测标签。"""

from __future__ import annotations

import re

from app.db.ecommerce_schema import ecommerce_sql
from app.db.tables import JUNCTION_TABLES
from app.evaluation.custom_cases import load_custom_cases
from app.retrieval.dynamic import VECTOR_SEED_LIMIT, choose_schema_seeds
from app.schemas.catalog import ColumnDocument, TableDocument

_CREATE = re.compile(r"^CREATE TABLE (t_[a-z0-9_]+) \(")
_COLUMN = re.compile(r"^    ([a-z_]+) ")
_TABLE_COMMENT = re.compile(r"^COMMENT ON TABLE (t_[a-z0-9_]+) IS '([^']*)';$")
_COLUMN_COMMENT = re.compile(r"^COMMENT ON COLUMN (t_[a-z0-9_]+)\.([a-z_]+) IS '([^']*)';$")


def _documents() -> list[TableDocument]:
    columns: dict[str, list[ColumnDocument]] = {}
    table_comments: dict[str, str] = {}
    column_comments: dict[tuple[str, str], str] = {}
    current = ""
    for line in ecommerce_sql().splitlines():
        create = _CREATE.match(line)
        if create:
            current = create.group(1)
            columns[current] = []
            continue
        column = _COLUMN.match(line)
        if current and column:
            columns[current].append(
                ColumnDocument(
                    name=column.group(1),
                    data_type="text",
                    nullable=True,
                )
            )
        table_comment = _TABLE_COMMENT.match(line)
        if table_comment:
            table_comments[table_comment.group(1)] = table_comment.group(2)
        column_comment = _COLUMN_COMMENT.match(line)
        if column_comment:
            column_comments[(column_comment.group(1), column_comment.group(2))] = (
                column_comment.group(3)
            )
    documents: list[TableDocument] = []
    for name, specs in columns.items():
        comment = table_comments[name]
        filled = [
            spec.model_copy(update={"comment": column_comments.get((name, spec.name))})
            for spec in specs
        ]
        documents.append(
            TableDocument(
                database_id="ecommerce",
                schema_name="public",
                table_name=name,
                table_comment=comment,
                columns=filled,
                is_junction="[Junction Table]" in comment,
                content_hash="sha256:test",
            )
        )
    return documents


def _names(question: str, scores: dict[str, float] | None = None) -> tuple[str, ...]:
    choices = choose_schema_seeds(question, _documents(), scores)
    return tuple(choice.table_name for choice in choices)


def test_level_question_does_not_pad_unrelated_tables() -> None:
    question = "按等级编号升序查询全部会员等级的名称和折扣率"
    selected = _names(question, {name: 0.8 for name in _entity_names()})

    assert selected == ("t_user_level",)


def test_column_word_selects_its_table() -> None:
    assert _names("查询各等级的折扣率") == ("t_user_level",)
    assert _names("统计自营商家的数量") == ("t_merchant",)
    assert "t_region" in _names("查询华东大区的省份")


def test_product_question_keeps_category_and_skips_order_detail() -> None:
    selected = set(_names("统计美妆品类的在售商品数量"))

    assert selected == {"t_product", "t_category"}


def test_purchase_question_includes_order_detail_not_coupon() -> None:
    selected = set(_names("统计2026年9月已支付订单中，VIP1用户购买美妆商品的数量"))

    assert {
        "t_order",
        "t_user",
        "t_user_level",
        "t_order_detail",
        "t_product",
        "t_category",
    } <= selected
    assert "t_coupon" not in selected
    assert "t_merchant" not in selected


def test_junction_comment_cannot_become_a_seed() -> None:
    selected = _names("查询用户和区域的地址映射")

    assert set(selected).isdisjoint(JUNCTION_TABLES)
    assert "t_user" in selected
    assert "t_region" in selected


def test_table_name_match_does_not_treat_a_longer_name_as_two_tables() -> None:
    selected = _names("请查询 t_order_detail 的行")

    assert "t_order_detail" in selected
    assert "t_order" not in selected


def test_vector_gap_stops_before_five_tables() -> None:
    documents = [_bare(f"t_entity_{index}", f"无关实体{index}") for index in range(6)]
    scores = {
        "t_entity_0": 0.90,
        "t_entity_1": 0.89,
        "t_entity_2": 0.50,
        "t_entity_3": 0.49,
        "t_entity_4": 0.48,
        "t_entity_5": 0.40,
    }

    selected = tuple(
        choice.table_name for choice in choose_schema_seeds("没有任何注释词", documents, scores)
    )

    assert selected == ("t_entity_0", "t_entity_1")
    assert len(selected) < VECTOR_SEED_LIMIT


def test_flat_vector_scores_still_cap_at_five() -> None:
    documents = [_bare(f"t_entity_{index}", f"无关实体{index}") for index in range(6)]
    scores = {document.table_name: 0.8 for document in documents}

    selected = choose_schema_seeds("没有任何注释词", documents, scores)

    assert len(selected) == VECTOR_SEED_LIMIT
    assert [choice.table_name for choice in selected] == [
        "t_entity_0",
        "t_entity_1",
        "t_entity_2",
        "t_entity_3",
        "t_entity_4",
    ]


def test_sales_words_select_order_product_and_detail() -> None:
    selected = set(_names("统计2026年9月自营商家美妆品类的已支付销售金额"))

    assert {
        "t_merchant",
        "t_category",
        "t_order",
        "t_order_detail",
        "t_product",
    } <= selected
    assert "t_coupon" not in selected


def test_category_value_absent_from_the_comment_still_selects_category() -> None:
    assert "t_category" in _names("统计护肤商品的数量")


def test_custom_questions_cover_required_entities_without_junction_seeds() -> None:
    documents = _documents()
    scores = {document.table_name: 0.2 for document in documents if not document.is_junction}
    recalls: list[tuple[str, float]] = []
    for case in load_custom_cases():
        selected = {
            choice.table_name for choice in choose_schema_seeds(case.question, documents, scores)
        }
        assert selected.isdisjoint(JUNCTION_TABLES)
        assert "required_tables" not in case.question
        found = sum(1 for name in case.required_tables if name in selected)
        recalls.append((case.difficulty, found / len(case.required_tables)))

    basic = [score for difficulty, score in recalls if difficulty == "basic"]
    assert basic
    assert all(score == 1.0 for score in basic)
    assert sum(score for _difficulty, score in recalls) / len(recalls) >= 0.95


def _entity_names() -> set[str]:
    return {document.table_name for document in _documents() if not document.is_junction}


def _bare(name: str, comment: str) -> TableDocument:
    return TableDocument(
        database_id="ecommerce",
        schema_name="public",
        table_name=name,
        table_comment=comment,
        columns=[],
        is_junction=False,
        content_hash="sha256:test",
    )
