"""外部 badcase 的 join 语义分类。"""

from __future__ import annotations

from app.evaluation.badcase import classify_badcase


def test_group_by_alias_differences_are_not_join_semantics() -> None:
    gold = (
        "SELECT store.s_state, item.i_category, date_dim.d_year, SUM(ss_ext_sales_price) "
        "FROM store_sales JOIN store ON store.s_store_sk = store_sales.ss_store_sk "
        "JOIN item ON item.i_item_sk = store_sales.ss_item_sk "
        "JOIN date_dim ON date_dim.d_date_sk = store_sales.ss_sold_date_sk "
        "GROUP BY store.s_state, item.i_category, date_dim.d_year"
    )
    predicted = (
        "SELECT s.s_state, i.i_category, d.d_year, SUM(ss.ss_ext_sales_price) "
        "FROM store_sales AS ss "
        "JOIN store AS s ON ss.ss_store_sk = s.s_store_sk "
        "JOIN item AS i ON ss.ss_item_sk = i.i_item_sk "
        "JOIN date_dim AS d ON ss.ss_sold_date_sk = d.d_date_sk "
        "GROUP BY s.s_state, i.i_category, d.d_year"
    )
    detail, _symptoms = classify_badcase(
        question="统计 2001 年各州门店销售",
        gold_sql=gold,
        predicted_sql=predicted,
        required_tables=("store_sales", "store", "item", "date_dim"),
        error_category=None,
        ex=0,
    )
    assert detail != "join_semantics"
