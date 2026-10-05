"""静态复核不读取 Gold，但 Gold SQL 不能被误报。"""

from __future__ import annotations

import re

import sqlglot
from app.agents.text_to_sql.semantic import HUGE_PLAN_ROWS, check_cte_outputs, check_semantics
from app.db.ecommerce_schema import ecommerce_sql
from app.db.tables import FOREIGN_KEYS
from app.evaluation.custom_cases import load_custom_cases
from app.sandbox.gate import allowed_read_only_functions, check_read_only_sql
from app.schemas.catalog import ColumnDocument, SchemaEdge, TableDocument
from sqlglot import exp

_STRUCTURAL = (exp.And, exp.Or, exp.Not, exp.Exists, exp.Cast, exp.TryCast, exp.Case, exp.If)
_LEVEL_QUESTION = "按等级编号升序查询全部会员等级的名称和折扣率"
_LEVEL_SQL = "SELECT level_id, level_name, discount_rate FROM t_user_level ORDER BY level_id"


def test_projection_entity_join_grain_and_result_checks() -> None:
    documents = _documents()
    edges = _edges()
    selected = [document.table_name for document in documents]

    missing_name = check_semantics(
        question=_LEVEL_QUESTION,
        sql="SELECT level_id FROM t_user_level ORDER BY level_id",
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    assert any(item.category == "projection_mismatch" for item in missing_name)
    assert all("required_tables" not in item.message for item in missing_name)

    covered = check_semantics(
        question=_LEVEL_QUESTION,
        sql=_LEVEL_SQL,
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
        plan_rows=5,
    )
    assert covered == ()

    missing_entity = check_semantics(
        question="查询会员等级的名称",
        sql="SELECT 1",
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    assert any(
        item.category == "missing_entity" and "t_user_level" in item.message
        for item in missing_entity
    )

    hidden = check_semantics(
        question="查询会员等级的名称",
        sql="SELECT 1",
        documents=documents,
        edges=edges,
        selected_tables=["t_product"],
        row_count=1,
    )
    assert all(item.category != "missing_entity" for item in hidden)

    cartesian = check_semantics(
        question="查询订单",
        sql="SELECT o.order_id FROM t_order AS o, t_user AS u",
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    assert any(item.category == "cartesian_product" for item in cartesian)

    bad_join = check_semantics(
        question="查询订单",
        sql="SELECT o.order_id FROM t_order AS o JOIN t_user AS u ON o.order_id = u.user_id",
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    assert any(item.category == "join_not_on_graph" for item in bad_join)

    good_join = check_semantics(
        question="查询订单",
        sql="SELECT o.order_id FROM t_order AS o JOIN t_user AS u ON o.user_id = u.user_id",
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    assert all(
        item.category not in {"join_not_on_graph", "cartesian_product"} for item in good_join
    )

    fanout = check_semantics(
        question="统计已支付订单的实付金额",
        sql=(
            "SELECT SUM(o.total_amount) FROM t_order AS o "
            "JOIN t_order_detail AS od ON o.order_id = od.order_id"
        ),
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    assert any(item.category == "aggregation_grain" for item in fanout)

    grouped = check_semantics(
        question="统计每个会员等级的用户数量",
        sql=(
            "SELECT COUNT(*) FROM t_user AS u "
            "JOIN t_user_level AS ul ON u.user_level_id = ul.level_id"
        ),
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    assert any("GROUP BY" in item.message for item in grouped)

    empty = check_semantics(
        question=_LEVEL_QUESTION,
        sql=_LEVEL_SQL,
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=0,
    )
    assert [item.category for item in empty] == ["empty_result"]

    huge = check_semantics(
        question=_LEVEL_QUESTION,
        sql=_LEVEL_SQL,
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1000,
        max_rows=1000,
        plan_rows=float(HUGE_PLAN_ROWS),
    )
    assert {item.category for item in huge} == {"result_too_large", "explain_cardinality"}


def test_cte_lineage_distinguishes_legal_illegal_and_unverified_joins() -> None:
    documents = _documents()
    edges = _edges()
    selected = [document.table_name for document in documents]
    legal = """
        WITH paid_sales AS (
            SELECT p.category_id, SUM(od.quantity) AS qty
            FROM t_order AS o
            JOIN t_order_detail AS od ON o.order_id = od.order_id
            JOIN t_product AS p ON od.product_id = p.product_id
            GROUP BY p.category_id
        )
        SELECT c.category_name, s.qty
        FROM paid_sales AS s
        JOIN t_category AS c ON s.category_id = c.category_id
    """
    illegal = """
        WITH paid_sales AS (
            SELECT o.order_id AS category_id
            FROM t_order AS o
        )
        SELECT c.category_name
        FROM paid_sales AS s
        JOIN t_category AS c ON s.category_id = c.category_id
    """
    unknown = """
        WITH paid_sales AS (
            SELECT 1 AS category_id
        )
        SELECT c.category_name
        FROM paid_sales AS s
        JOIN t_category AS c ON s.category_id = c.category_id
    """
    recursive = """
        WITH RECURSIVE vip_regions AS (
            SELECT r.region_id, r.region_name
            FROM t_region AS r
            WHERE r.region_name = '华北'
        )
        SELECT urm.user_id
        FROM t_user_region_map AS urm
        JOIN vip_regions AS vr ON urm.region_id = vr.region_id
    """

    def categories(sql: str) -> set[str]:
        return {
            item.category
            for item in check_semantics(
                question="查询订单",
                sql=sql,
                documents=documents,
                edges=edges,
                selected_tables=selected,
                row_count=1,
            )
        }

    assert "join_not_on_graph" not in categories(legal)
    assert "join_unverified" not in categories(legal)
    assert "join_not_on_graph" in categories(illegal)
    assert "join_unverified" in categories(unknown)
    assert "join_not_on_graph" not in categories(unknown)
    assert "join_not_on_graph" not in categories(recursive)
    assert "join_unverified" not in categories(recursive)


def test_reported_cte_joins_are_not_false_foreign_key_failures() -> None:
    documents = _documents()
    edges = _edges()
    selected = [document.table_name for document in documents]
    samples = {
        "custom_medium_047": """
            WITH paid_sales AS (
                SELECT p.category_id, SUM(od.quantity) AS total_quantity
                FROM t_order AS o
                JOIN t_order_detail AS od ON o.order_id = od.order_id
                JOIN t_product AS p ON od.product_id = p.product_id
                GROUP BY p.category_id
            )
            SELECT c.category_name, s.total_quantity
            FROM paid_sales AS s
            JOIN t_category AS c ON s.category_id = c.category_id
        """,
        "custom_medium_048": """
            WITH month_sales AS (
                SELECT p.category_id
                FROM t_product AS p
            )
            SELECT c.category_name
            FROM t_category AS c
            JOIN month_sales AS s ON c.category_id = s.category_id
        """,
        "custom_medium_049": """
            WITH paid_sales AS (
                SELECT p.category_id, p.merchant_id
                FROM t_product AS p
            )
            SELECT m.merchant_name
            FROM paid_sales AS s
            JOIN t_merchant AS m ON s.merchant_id = m.merchant_id
        """,
        "custom_medium_050": """
            WITH paid_sales AS (
                SELECT p.category_id
                FROM t_product AS p
                JOIN t_category AS c ON p.category_id = c.category_id
            )
            SELECT s.category_id
            FROM paid_sales AS s
            JOIN t_category AS c ON s.category_id = c.category_id
        """,
        "custom_complex_023": """
            WITH RECURSIVE vip_regions AS (
                SELECT r.region_id
                FROM t_region AS r
                WHERE r.region_name = '华北'
            )
            SELECT urm.user_id
            FROM vip_regions AS vr
            JOIN t_user_region_map AS urm ON vr.region_id = urm.region_id
        """,
    }
    for case_id, sql in samples.items():
        categories = {
            item.category
            for item in check_semantics(
                question="查询订单",
                sql=sql,
                documents=documents,
                edges=edges,
                selected_tables=selected,
                row_count=1,
            )
        }
        assert "join_not_on_graph" not in categories, case_id
        assert "join_unverified" not in categories, case_id


def test_custom_gold_passes_static_review_without_gold_inputs() -> None:
    documents = _documents()
    edges = _edges()
    selected = [document.table_name for document in documents]
    for case in load_custom_cases():
        findings = check_semantics(
            question=case.question,
            sql=case.gold_sql,
            documents=documents,
            edges=edges,
            selected_tables=selected,
            row_count=1,
            max_rows=1000,
            plan_rows=272,
        )
        assert findings == (), (case.id, findings)
        assert check_cte_outputs(case.gold_sql) == (), case.id

    hidden = check_cte_outputs(
        """
        WITH merchants AS (SELECT merchant_id FROM t_merchant)
        SELECT m.is_self_operated FROM merchants AS m
        """
    )
    assert any("is_self_operated" in item.message for item in hidden)


def test_quantity_fanout_requires_detail_dedup_before_the_region_map() -> None:
    documents = _documents()
    edges = _edges()
    selected = [document.table_name for document in documents]
    question = "统计上个月华东大区VIP3以上用户购买自营美妆的已支付商品数量"
    fanned = """
        SELECT m.merchant_name, SUM(od.quantity) AS total_quantity
        FROM t_order_detail AS od
        JOIN t_order AS o ON od.order_id = o.order_id
        JOIN t_user_region_map AS urm ON o.user_id = urm.user_id
        JOIN t_merchant AS m ON od.product_id = m.merchant_id
        GROUP BY m.merchant_name
    """
    findings = check_semantics(
        question=question,
        sql=fanned,
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    assert any(item.category == "missing_fact_dedup" for item in findings)
    deduped = """
        WITH details AS (
            SELECT DISTINCT od.detail_id, od.quantity, m.merchant_id, m.merchant_name
            FROM t_order_detail AS od
            JOIN t_order AS o ON od.order_id = o.order_id
            JOIN t_user_region_map AS urm ON o.user_id = urm.user_id
            JOIN t_merchant AS m ON od.product_id = m.merchant_id
        )
        SELECT merchant_name, SUM(quantity) AS total_quantity
        FROM details
        GROUP BY merchant_id, merchant_name
    """
    cleared = check_semantics(
        question=question,
        sql=deduped,
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    assert "missing_fact_dedup" not in {item.category for item in cleared}
    assert "aggregate_over_fanout" not in {item.category for item in cleared}


def test_cte_outputs_satisfy_requested_projection() -> None:
    documents = _documents()
    edges = _edges()
    selected = [document.table_name for document in documents]
    sql = """
        WITH products AS (
            SELECT p.product_name, m.merchant_name
            FROM t_product AS p
            JOIN t_merchant AS m ON p.merchant_id = m.merchant_id
        ),
        coupons AS (
            SELECT c.coupon_name FROM t_coupon AS c
        )
        SELECT products.merchant_name, products.product_name, coupons.coupon_name
        FROM products
        JOIN coupons ON TRUE
    """
    categories = {
        item.category
        for item in check_semantics(
            question="查询上个月已支付订单中实际使用了促销满减券的商家、商品和优惠券",
            sql=sql,
            documents=documents,
            edges=edges,
            selected_tables=selected,
            row_count=1,
        )
    }
    assert "projection_mismatch" not in categories


def test_user_filter_cte_does_not_export_quantity_fanout() -> None:
    documents = _documents()
    edges = _edges()
    selected = [document.table_name for document in documents]
    sql = """
        WITH region_users AS (
            SELECT DISTINCT m.user_id
            FROM t_user_region_map AS m
            JOIN t_region AS r ON m.region_id = r.region_id
            WHERE r.region_name = '华南'
        )
        SELECT m.merchant_name, SUM(od.quantity) AS total_quantity
        FROM t_order_detail AS od
        JOIN t_order AS o ON od.order_id = o.order_id
        JOIN region_users AS ru ON o.user_id = ru.user_id
        JOIN t_product AS p ON od.product_id = p.product_id
        JOIN t_merchant AS m ON p.merchant_id = m.merchant_id
        GROUP BY m.merchant_name
    """
    findings = check_semantics(
        question="统计华南地区已支付订单的商品购买数量",
        sql=sql,
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    categories = {item.category for item in findings}
    assert "missing_fact_dedup" not in categories
    assert "aggregate_over_fanout" not in categories


def test_quantity_projected_through_a_region_cte_is_inherited_fanout() -> None:
    documents = _documents()
    edges = _edges()
    selected = [document.table_name for document in documents]
    sql = """
        WITH paid_lines AS (
            SELECT od.quantity AS quantity, m.merchant_name AS merchant_name
            FROM t_order_detail AS od
            JOIN t_order AS o ON od.order_id = o.order_id
            JOIN t_user_region_map AS urm ON o.user_id = urm.user_id
            JOIN t_product AS p ON od.product_id = p.product_id
            JOIN t_merchant AS m ON p.merchant_id = m.merchant_id
        )
        SELECT merchant_name, SUM(quantity) AS total_quantity
        FROM paid_lines
        GROUP BY merchant_name
    """
    findings = check_semantics(
        question="统计已支付订单的商品购买数量",
        sql=sql,
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    assert any(item.category == "aggregate_over_fanout" for item in findings)


def test_rejoining_details_after_order_dedup_is_flagged() -> None:
    documents = _documents()
    edges = _edges()
    selected = [document.table_name for document in documents]
    sql = """
        WITH orders AS (
            SELECT DISTINCT o.order_id, o.total_amount
            FROM t_order AS o
        )
        SELECT m.merchant_name, SUM(orders.total_amount) AS net_pay_amount
        FROM orders
        JOIN t_order_detail AS od ON od.order_id = orders.order_id
        JOIN t_product AS p ON p.product_id = od.product_id
        JOIN t_merchant AS m ON m.merchant_id = p.merchant_id
        GROUP BY m.merchant_name
    """
    findings = check_semantics(
        question="统计自营商家的已支付订单数和实付金额",
        sql=sql,
        documents=documents,
        edges=edges,
        selected_tables=selected,
        row_count=1,
    )
    assert any(item.category == "refanout_after_dedup" for item in findings)


def test_unqualified_cte_column_still_proves_the_foreign_key() -> None:
    documents = _documents()
    edges = _edges()
    selected = [document.table_name for document in documents]
    sql = """
        WITH category_scope AS (
            SELECT category_id, category_name FROM t_category WHERE category_name = '家具'
        )
        SELECT cs.category_name, COUNT(p.product_id) AS product_count
        FROM category_scope AS cs
        JOIN t_product AS p ON p.category_id = cs.category_id
        GROUP BY cs.category_name
    """
    categories = {
        item.category
        for item in check_semantics(
            question="统计家具品类的在售商品数量",
            sql=sql,
            documents=documents,
            edges=edges,
            selected_tables=selected,
            row_count=1,
        )
    }
    assert "join_unverified" not in categories
    assert "join_not_on_graph" not in categories


def test_custom_gold_functions_stay_inside_the_existing_allow_list() -> None:
    used: set[str] = set()
    for case in load_custom_cases():
        decision = check_read_only_sql(case.gold_sql)
        assert decision.error is None
        expression = sqlglot.parse_one(case.gold_sql, read="postgres")
        for node in expression.walk():
            if not isinstance(node, exp.Func) or isinstance(node, _STRUCTURAL):
                continue
            name = node.name.lower() if isinstance(node, exp.Anonymous) else node.sql_name().lower()
            used.add(name)

    allowed = allowed_read_only_functions()
    assert used == {"count", "sum"}
    assert used <= allowed
    assert "pg_sleep" not in allowed


def _documents() -> list[TableDocument]:
    columns: dict[str, list[ColumnDocument]] = {}
    table_comments: dict[str, str] = {}
    column_comments: dict[tuple[str, str], str] = {}
    current = ""
    for line in ecommerce_sql().splitlines():
        create = re.match(r"^CREATE TABLE (t_[a-z0-9_]+) \(", line)
        if create:
            current = create.group(1)
            columns[current] = []
            continue
        column = re.match(r"^    ([a-z_]+) ", line)
        if current and column:
            columns[current].append(
                ColumnDocument(name=column.group(1), data_type="text", nullable=True)
            )
        table_comment = re.match(r"^COMMENT ON TABLE (t_[a-z0-9_]+) IS '([^']*)';$", line)
        if table_comment:
            table_comments[table_comment.group(1)] = table_comment.group(2)
        column_comment = re.match(
            r"^COMMENT ON COLUMN (t_[a-z0-9_]+)\.([a-z_]+) IS '([^']*)';$",
            line,
        )
        if column_comment:
            column_comments[(column_comment.group(1), column_comment.group(2))] = (
                column_comment.group(3)
            )
    documents: list[TableDocument] = []
    for name, specs in columns.items():
        comment = table_comments[name]
        documents.append(
            TableDocument(
                database_id="ecommerce",
                schema_name="public",
                table_name=name,
                table_comment=comment,
                columns=[
                    spec.model_copy(update={"comment": column_comments.get((name, spec.name))})
                    for spec in specs
                ],
                is_junction="[Junction Table]" in comment,
                content_hash=f"sha256:{name}",
            )
        )
    return documents


def _edges() -> list[SchemaEdge]:
    return [
        SchemaEdge(
            source_table=item.source_table,
            source_columns=[item.source_column],
            target_table=item.target_table,
            target_columns=[item.target_column],
            constraint_name=item.constraint_name,
            weight=1.0,
            inferred=False,
            confidence=1.0,
        )
        for item in FOREIGN_KEYS
    ]
