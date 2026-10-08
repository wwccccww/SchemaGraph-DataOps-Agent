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


def test_alias_group_by_with_matching_projections_is_not_join_semantics() -> None:
    gold = (
        "SELECT web_page.wp_type AS page_type, reason.r_reason_desc AS return_reason, "
        "item.i_category AS item_category, date_dim.d_year AS return_year, "
        "SUM(web_returns.wr_return_amt) AS return_amount "
        "FROM web_returns "
        "JOIN date_dim ON web_returns.wr_returned_date_sk = date_dim.d_date_sk "
        "JOIN item ON web_returns.wr_item_sk = item.i_item_sk "
        "JOIN web_page ON web_returns.wr_web_page_sk = web_page.wp_web_page_sk "
        "JOIN reason ON web_returns.wr_reason_sk = reason.r_reason_sk "
        "WHERE date_dim.d_year = 2001 "
        "GROUP BY web_page.wp_type, reason.r_reason_desc, item.i_category, date_dim.d_year"
    )
    predicted = (
        "SELECT page_type, return_reason, item_category, return_year, SUM(return_amount) "
        "FROM (SELECT wp.wp_type AS page_type, r.r_reason_desc AS return_reason, "
        "i.i_category AS item_category, d.d_year AS return_year, wr.wr_return_amt AS return_amount "
        "FROM web_returns wr JOIN date_dim d ON wr.wr_returned_date_sk = d.d_date_sk "
        "JOIN item i ON wr.wr_item_sk = i.i_item_sk "
        "JOIN web_page wp ON wr.wr_web_page_sk = wp.wp_web_page_sk "
        "JOIN reason r ON wr.wr_reason_sk = r.r_reason_sk WHERE d.d_year = 2001) t "
        "GROUP BY page_type, return_reason, item_category, return_year"
    )
    detail, _ = classify_badcase(
        question="returns by page type",
        gold_sql=gold,
        predicted_sql=predicted,
        required_tables=("web_returns", "date_dim", "item", "web_page", "reason"),
        error_category=None,
        ex=0,
    )
    assert detail != "join_semantics"


def test_group_by_quoted_label_matches_snake_case_alias() -> None:
    detail, _ = classify_badcase(
        question="count schools by county",
        gold_sql='SELECT ss."County Name" AS c FROM schools ss GROUP BY ss."County Name"',
        predicted_sql="SELECT county_name AS c FROM schools GROUP BY county_name",
        required_tables=("schools",),
        error_category=None,
        ex=0,
        dialect="sqlite",
    )
    assert detail != "join_semantics"
