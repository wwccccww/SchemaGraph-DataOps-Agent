"""确定性造数不访问数据库。"""

from __future__ import annotations

from app.db.seed_data import (
    DETAIL_COUNT,
    ORDER_COUNT,
    PRODUCT_COUNT,
    USER_COUNT,
    build_dataset,
)


def test_same_seed_has_the_same_digest_and_scale() -> None:
    first = build_dataset()
    second = build_dataset()

    assert first.digest == second.digest
    assert len(first.digest) == 64
    assert first.count("t_user") == USER_COUNT
    assert first.count("t_product") == PRODUCT_COUNT
    assert first.count("t_order") == ORDER_COUNT
    assert first.count("t_order_detail") == DETAIL_COUNT
    assert first.rows["t_merchant"][0][1] == "自营美妆一店"
    assert first.rows["t_merchant"][1][1] == "自营美妆二店"
