"""答案契约只来自问题和锚点日。"""

from __future__ import annotations

from app.agents.text_to_sql.contract import check_contract, extract_answer_contract
from app.agents.text_to_sql.prompt import render_generation_prompt
from app.evaluation.custom_cases import load_custom_cases

_PROJECTION_IDS = (
    "custom_basic_001",
    "custom_basic_003",
    "custom_basic_005",
    "custom_basic_006",
    "custom_basic_007",
    "custom_basic_008",
    *(f"custom_basic_{index:03d}" for index in range(20, 34)),
    "custom_basic_041",
    "custom_basic_042",
    "custom_basic_044",
    "custom_basic_045",
    "custom_basic_046",
    "custom_basic_047",
    "custom_basic_048",
)
_GRAIN_IDS = (
    "custom_basic_002",
    *(f"custom_basic_{index:03d}" for index in range(9, 14)),
    *(f"custom_basic_{index:03d}" for index in range(34, 41)),
    "custom_basic_050",
    "custom_medium_001",
    "custom_medium_002",
    "custom_medium_003",
    "custom_medium_004",
    "custom_medium_005",
    *(f"custom_medium_{index:03d}" for index in range(8, 22)),
    *(f"custom_medium_{index:03d}" for index in range(23, 51)),
    *(f"custom_complex_{index:03d}" for index in range(5, 24)),
    "custom_complex_030",
    "custom_complex_031",
)


def test_projection_and_grain_cases_build_answer_contracts() -> None:
    cases = {case.id: case for case in load_custom_cases()}

    assert len(_PROJECTION_IDS) == 27
    assert len(set(_PROJECTION_IDS)) == 27
    assert len(_GRAIN_IDS) == 82
    assert len(set(_GRAIN_IDS)) == 82
    for case_id in _PROJECTION_IDS:
        contract = extract_answer_contract(cases[case_id].question)
        assert contract.dimension_fields or contract.measures, case_id
    for case_id in _GRAIN_IDS:
        case = cases[case_id]
        contract = extract_answer_contract(case.question, anchor_date=case.anchor_date.isoformat())
        assert contract.dimensions, case_id


def test_gold_sql_satisfies_the_question_contract() -> None:
    for case in load_custom_cases():
        findings = check_contract(
            question=case.question,
            sql=case.gold_sql,
            anchor_date=case.anchor_date.isoformat(),
        )
        assert findings == (), (case.id, case.question, findings)


def test_category_time_and_dedup_have_positive_and_negative_examples() -> None:
    exact = extract_answer_contract("统计美妆品类的在售商品数量")
    descendants = extract_answer_contract("统计美妆及其子类的在售商品数量")
    assert exact.category_scope == "exact"
    assert descendants.category_scope == "descendants"
    positive_category = """
        SELECT c.category_name, COUNT(*) AS product_count
        FROM t_product AS p
        JOIN t_category AS c ON p.category_id = c.category_id
        WHERE c.category_name = '美妆'
        GROUP BY c.category_id, c.category_name
    """
    negative_category = """
        WITH RECURSIVE tree AS (
            SELECT category_id, parent_id FROM t_category WHERE category_name = '美妆'
            UNION ALL
            SELECT c.category_id, c.parent_id
            FROM t_category AS c
            JOIN tree AS t ON c.parent_id = t.category_id
        )
        SELECT category_name, COUNT(*) AS product_count
        FROM t_product
        GROUP BY category_name
    """
    assert check_contract(question="统计美妆品类的在售商品数量", sql=positive_category) == ()
    expanded = check_contract(question="统计美妆品类的在售商品数量", sql=negative_category)
    assert any("精确匹配" in item.message for item in expanded)

    month = "统计上个月状态为已支付的订单数量"
    contract = extract_answer_contract(month, anchor_date="2026-10-01")
    assert contract.time_window == ("2026-09-01 00:00:00", "2026-10-01 00:00:00")
    positive_time = """
        SELECT '2026-09' AS order_month, 'PAID' AS order_status, COUNT(*) AS order_count
        FROM t_order
        WHERE created_at >= TIMESTAMP '2026-09-01 00:00:00'
          AND created_at < TIMESTAMP '2026-10-01 00:00:00'
    """
    negative_time = "SELECT COUNT(*) AS order_count FROM t_order WHERE created_at >= CURRENT_DATE"
    assert check_contract(question=month, sql=positive_time, anchor_date="2026-10-01") == ()
    clock = check_contract(question=month, sql=negative_time, anchor_date="2026-10-01")
    assert any("运行时时钟" in item.message for item in clock)

    orders = "统计自营商家使用满减优惠券的已支付订单数"
    assert extract_answer_contract(orders).dedup_key == "order_id"
    positive_dedup = """
        WITH qualified_orders AS (
            SELECT DISTINCT o.order_id, m.merchant_id, m.merchant_name
            FROM t_order AS o
            JOIN t_merchant AS m ON o.user_id = m.merchant_id
        )
        SELECT merchant_name, COUNT(*) AS order_count
        FROM qualified_orders
        GROUP BY merchant_id, merchant_name
    """
    negative_dedup = """
        SELECT merchant_name, COUNT(*) AS order_count
        FROM t_merchant
        GROUP BY merchant_id, merchant_name
    """
    assert check_contract(question=orders, sql=positive_dedup) == ()
    dedup = check_contract(question=orders, sql=negative_dedup)
    assert any("order_id" in item.message for item in dedup)


def test_prompt_places_the_contract_before_schema_context() -> None:
    question = "统计上个月已支付订单的数量"
    prompt = render_generation_prompt(
        question=question,
        schema_context="t_order(order_id)",
        tools=[],
        contract=extract_answer_contract(question),
    )

    assert prompt.index("答案契约") < prompt.index("可用表")
    assert "2026-09-01 00:00:00" in prompt
    assert "GOLD" not in prompt
    assert "required_tables" not in prompt
    assert "difficulty" not in prompt
