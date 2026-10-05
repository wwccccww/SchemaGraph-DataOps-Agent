"""预测 SQL 的结构摘要不依赖 Gold，解析失败时也不中断评测。"""

from __future__ import annotations

from app.evaluation.sql_shape import describe_sql


def test_select_shape_keeps_join_filter_and_aggregation() -> None:
    shape = describe_sql(
        """
        SELECT ul.level_name, COUNT(*) AS user_count
        FROM t_user AS u
        JOIN t_user_level AS ul ON u.user_level_id = ul.level_id
        WHERE u.user_id > 0
        GROUP BY ul.level_name
        ORDER BY user_count DESC
        """
    )

    assert shape.parse_error is None
    assert shape.referenced_tables == ("t_user", "t_user_level")
    assert shape.projections == ("level_name", "user_count")
    assert shape.joins == ("JOIN t_user_level ON u.user_level_id = ul.level_id",)
    assert shape.predicates == ("WHERE u.user_id > 0",)
    assert shape.group_by == ("ul.level_name",)
    assert shape.aggregations == ("count",)
    assert shape.order_by == ("user_count DESC",)
    assert shape.sql_hash.startswith("sha256:")
    assert "SELECT" not in shape.sql_hash


def test_cte_name_is_not_a_referenced_table() -> None:
    shape = describe_sql(
        """
        WITH recent AS (SELECT order_id FROM t_order)
        SELECT order_id FROM recent
        """
    )

    assert shape.parse_error is None
    assert shape.referenced_tables == ("t_order",)


def test_unparsed_and_write_sql_keep_the_text_without_raising() -> None:
    broken = describe_sql("NOT SQL AT ALL")
    write = describe_sql("INSERT INTO t_user VALUES (1)")

    assert broken.parse_error == "SQL 无法解析"
    assert broken.sql == "NOT SQL AT ALL"
    assert broken.referenced_tables == ()
    assert write.parse_error == "不是只读查询"
    assert write.referenced_tables == ("t_user",)
    assert describe_sql(None).parse_error == "SQL 为空"
    assert describe_sql("").sql is None
