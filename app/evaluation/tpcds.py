"""TPC-DS 派生压力测试用例。

自然语言问题由评测作者编写。Gold SQL 是针对 24 张业务表的 PostgreSQL 适配，
不是官方 TPC-DS 查询，也不能当作官方成绩。导入本模块不会克隆工具或生成数据。
"""

from __future__ import annotations

import textwrap
from datetime import date
from pathlib import Path

import yaml

from app.evaluation.case_yaml import dump_benchmark_cases, projection_names
from app.evaluation.custom_cases import referenced_tables
from app.schemas.benchmark import BenchmarkCase

CASES_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "tpcds_derived" / "cases.yaml"
TPCDS_SOURCE_VERSION = "tpcds-v2.10.0+5a3a81796992b725c2a8b216767e142609966752"
KIT_COMMIT = "5a3a81796992b725c2a8b216767e142609966752"
KIT_REPO = "https://github.com/gregrahn/tpcds-kit.git"
TPCDS_CASE_COUNT = 30
SALES_YEAR = 2001
ANCHOR = date(2026, 10, 1)
BUSINESS_TABLES = frozenset(
    {
        "call_center",
        "catalog_page",
        "catalog_returns",
        "catalog_sales",
        "customer",
        "customer_address",
        "customer_demographics",
        "date_dim",
        "household_demographics",
        "income_band",
        "inventory",
        "item",
        "promotion",
        "reason",
        "ship_mode",
        "store",
        "store_returns",
        "store_sales",
        "time_dim",
        "warehouse",
        "web_page",
        "web_returns",
        "web_sales",
        "web_site",
    }
)


def load_tpcds_cases(path: Path | None = None) -> list[BenchmarkCase]:
    """读取冻结的 30 条派生用例。"""

    payload = yaml.safe_load((path or CASES_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("contract_version") != "1.0":
        raise ValueError("tpcds case file must declare contract_version 1.0")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("tpcds case file must contain a cases list")
    return [BenchmarkCase.model_validate(case) for case in cases]


def build_tpcds_cases() -> list[BenchmarkCase]:
    """生成 30 条已审计的 PostgreSQL 查询。"""

    cases = [_make(index, spec) for index, spec in enumerate(_QUERY_SPECS, start=1)]
    if len(cases) != TPCDS_CASE_COUNT:
        raise RuntimeError("tpcds case builder drifted from 30 queries")
    return cases


def dump_tpcds_cases(cases: list[BenchmarkCase]) -> str:
    """冻结 TPC-DS 派生用例。"""

    return dump_benchmark_cases(cases)


def _make(index: int, spec: tuple[str, str, tuple[str, ...]]) -> BenchmarkCase:
    question, gold_sql, tags = spec
    question = question.replace("__YEAR__", str(SALES_YEAR))
    sql = textwrap.dedent(gold_sql).replace("__YEAR__", str(SALES_YEAR)).strip()
    tables = sorted(referenced_tables(sql, dialect="postgres"))
    if not 5 <= len(tables) <= 12:
        raise RuntimeError(f"tpcds query {index} uses {len(tables)} tables: {tables}")
    if not set(tables) <= BUSINESS_TABLES:
        raise RuntimeError(f"tpcds query {index} references {tables}")
    return BenchmarkCase(
        id=f"tpcds_complex_{index:03d}",
        source="tpcds-derived",
        source_version=TPCDS_SOURCE_VERSION,
        database_id="tpcds",
        difficulty="complex",
        dialect="postgres",
        question=question,
        gold_sql=sql,
        required_tables=tables,
        required_junctions=[],
        order_sensitive=False,
        numeric_tolerance=None,
        expected_columns=projection_names(sql, dialect="postgres"),
        anchor_date=ANCHOR,
        tags=["tpcds-derived", *tags],
    )


_QUERY_SPECS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "统计 __YEAR__ 年能关联到当前住址的顾客，在各州门店购买各商品类别的销售金额。",
        """
        WITH sold AS (
            SELECT ss_item_sk, ss_store_sk, ss_customer_sk, ss_sold_date_sk,
                   ss_ext_sales_price
            FROM store_sales
        )
        SELECT store.s_state AS store_state,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(sold.ss_ext_sales_price) AS sales_amount
        FROM sold
        JOIN date_dim ON sold.ss_sold_date_sk = date_dim.d_date_sk
        JOIN item ON sold.ss_item_sk = item.i_item_sk
        JOIN store ON sold.ss_store_sk = store.s_store_sk
        JOIN customer ON sold.ss_customer_sk = customer.c_customer_sk
        JOIN customer_address
          ON customer.c_current_addr_sk = customer_address.ca_address_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY store.s_state, item.i_category, date_dim.d_year
        """,
        ("cte", "join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年购买过直邮促销商品的顾客，按教育程度和信用评级汇总净利润。",
        """
        SELECT customer_demographics.cd_education_status AS education_status,
               customer_demographics.cd_credit_rating AS credit_rating,
               date_dim.d_year AS sales_year,
               SUM(store_sales.ss_net_profit) AS net_profit
        FROM store_sales
        JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
        JOIN item ON store_sales.ss_item_sk = item.i_item_sk
        JOIN customer ON store_sales.ss_customer_sk = customer.c_customer_sk
        JOIN customer_demographics
          ON customer.c_current_cdemo_sk = customer_demographics.cd_demo_sk
        WHERE date_dim.d_year = __YEAR__
          AND store_sales.ss_item_sk IN (
              SELECT promotion.p_item_sk
              FROM promotion
              WHERE promotion.p_channel_dmail = 'Y'
                AND promotion.p_item_sk IS NOT NULL
          )
        GROUP BY customer_demographics.cd_education_status,
                 customer_demographics.cd_credit_rating,
                 date_dim.d_year
        """,
        ("subquery", "join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年同一门店同一商品既有销售又有退货时，各退货原因和类别的退货金额。",
        """
        WITH sold AS (
            SELECT store_sales.ss_item_sk AS item_sk,
                   store_sales.ss_store_sk AS store_sk,
                   date_dim.d_year AS sales_year
            FROM store_sales
            JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY store_sales.ss_item_sk, store_sales.ss_store_sk, date_dim.d_year
        ),
        returned AS (
            SELECT store_returns.sr_item_sk AS item_sk,
                   store_returns.sr_store_sk AS store_sk,
                   store_returns.sr_reason_sk AS reason_sk,
                   date_dim.d_year AS return_year,
                   SUM(store_returns.sr_return_amt) AS return_amount
            FROM store_returns
            JOIN date_dim ON store_returns.sr_returned_date_sk = date_dim.d_date_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY store_returns.sr_item_sk, store_returns.sr_store_sk,
                     store_returns.sr_reason_sk, date_dim.d_year
        )
        SELECT reason.r_reason_desc AS return_reason,
               item.i_category AS item_category,
               store.s_state AS store_state,
               returned.return_year AS return_year,
               SUM(returned.return_amount) AS return_amount
        FROM returned
        JOIN sold
          ON sold.item_sk = returned.item_sk
         AND sold.store_sk = returned.store_sk
         AND sold.sales_year = returned.return_year
        JOIN item ON item.i_item_sk = returned.item_sk
        JOIN store ON store.s_store_sk = returned.store_sk
        JOIN reason ON reason.r_reason_sk = returned.reason_sk
        GROUP BY reason.r_reason_desc, item.i_category, store.s_state, returned.return_year
        """,
        ("cte", "join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各呼叫中心、配送方式和商品类别的目录销售金额。",
        """
        SELECT call_center.cc_name AS call_center_name,
               ship_mode.sm_type AS ship_type,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(catalog_sales.cs_ext_sales_price) AS sales_amount
        FROM catalog_sales
        JOIN date_dim ON catalog_sales.cs_sold_date_sk = date_dim.d_date_sk
        JOIN item ON catalog_sales.cs_item_sk = item.i_item_sk
        JOIN call_center ON catalog_sales.cs_call_center_sk = call_center.cc_call_center_sk
        JOIN ship_mode ON catalog_sales.cs_ship_mode_sk = ship_mode.sm_ship_mode_sk
        JOIN catalog_page
          ON catalog_sales.cs_catalog_page_sk = catalog_page.cp_catalog_page_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY call_center.cc_name, ship_mode.sm_type, item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各仓库所在州、退货原因和商品类别的目录退货金额，并关联呼叫中心。",
        """
        SELECT warehouse.w_state AS warehouse_state,
               reason.r_reason_desc AS return_reason,
               item.i_category AS item_category,
               call_center.cc_state AS call_center_state,
               date_dim.d_year AS return_year,
               SUM(catalog_returns.cr_return_amount) AS return_amount
        FROM catalog_returns
        JOIN date_dim ON catalog_returns.cr_returned_date_sk = date_dim.d_date_sk
        JOIN item ON catalog_returns.cr_item_sk = item.i_item_sk
        JOIN warehouse ON catalog_returns.cr_warehouse_sk = warehouse.w_warehouse_sk
        JOIN reason ON catalog_returns.cr_reason_sk = reason.r_reason_sk
        JOIN call_center
          ON catalog_returns.cr_call_center_sk = call_center.cc_call_center_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY warehouse.w_state, reason.r_reason_desc, item.i_category,
                 call_center.cc_state, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各网站、配送方式和商品类别的网站销售金额。",
        """
        SELECT web_site.web_name AS web_name,
               ship_mode.sm_type AS ship_type,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(web_sales.ws_ext_sales_price) AS sales_amount
        FROM web_sales
        JOIN date_dim ON web_sales.ws_sold_date_sk = date_dim.d_date_sk
        JOIN item ON web_sales.ws_item_sk = item.i_item_sk
        JOIN web_site ON web_sales.ws_web_site_sk = web_site.web_site_sk
        JOIN ship_mode ON web_sales.ws_ship_mode_sk = ship_mode.sm_ship_mode_sk
        JOIN web_page ON web_sales.ws_web_page_sk = web_page.wp_web_page_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY web_site.web_name, ship_mode.sm_type, item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各网页类型、退货原因和商品类别的网站退货金额。",
        """
        SELECT web_page.wp_type AS page_type,
               reason.r_reason_desc AS return_reason,
               item.i_category AS item_category,
               date_dim.d_year AS return_year,
               SUM(web_returns.wr_return_amt) AS return_amount
        FROM web_returns
        JOIN date_dim ON web_returns.wr_returned_date_sk = date_dim.d_date_sk
        JOIN item ON web_returns.wr_item_sk = item.i_item_sk
        JOIN web_page ON web_returns.wr_web_page_sk = web_page.wp_web_page_sk
        JOIN reason ON web_returns.wr_reason_sk = reason.r_reason_sk
        JOIN customer ON web_returns.wr_refunded_customer_sk = customer.c_customer_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY web_page.wp_type, reason.r_reason_desc, item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "按销售渠道、商品类别和年份汇总 __YEAR__ 年门店、目录和网站三条渠道的销售金额。",
        """
        WITH channel_rows AS (
            SELECT 'store' AS channel, store_sales.ss_item_sk AS item_sk,
                   date_dim.d_year AS sales_year,
                   SUM(store_sales.ss_ext_sales_price) AS sales_amount
            FROM store_sales
            JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY store_sales.ss_item_sk, date_dim.d_year
            UNION ALL
            SELECT 'catalog', catalog_sales.cs_item_sk, date_dim.d_year,
                   SUM(catalog_sales.cs_ext_sales_price)
            FROM catalog_sales
            JOIN date_dim ON catalog_sales.cs_sold_date_sk = date_dim.d_date_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY catalog_sales.cs_item_sk, date_dim.d_year
            UNION ALL
            SELECT 'web', web_sales.ws_item_sk, date_dim.d_year,
                   SUM(web_sales.ws_ext_sales_price)
            FROM web_sales
            JOIN date_dim ON web_sales.ws_sold_date_sk = date_dim.d_date_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY web_sales.ws_item_sk, date_dim.d_year
        )
        SELECT channel_rows.channel AS sales_channel,
               item.i_category AS item_category,
               channel_rows.sales_year AS sales_year,
               SUM(channel_rows.sales_amount) AS sales_amount
        FROM channel_rows
        JOIN item ON item.i_item_sk = channel_rows.item_sk
        GROUP BY channel_rows.channel, item.i_category, channel_rows.sales_year
        """,
        ("cte", "join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各仓库所在州和商品类别的库存数量，只保留当年门店卖过的商品。",
        """
        SELECT warehouse.w_state AS warehouse_state,
               item.i_category AS item_category,
               date_dim.d_year AS inventory_year,
               SUM(inventory.inv_quantity_on_hand) AS quantity_on_hand
        FROM inventory
        JOIN date_dim ON inventory.inv_date_sk = date_dim.d_date_sk
        JOIN item ON inventory.inv_item_sk = item.i_item_sk
        JOIN warehouse ON inventory.inv_warehouse_sk = warehouse.w_warehouse_sk
        WHERE date_dim.d_year = __YEAR__
          AND inventory.inv_item_sk IN (
              SELECT store_sales.ss_item_sk
              FROM store_sales
              JOIN date_dim AS sold_date
                ON store_sales.ss_sold_date_sk = sold_date.d_date_sk
              WHERE sold_date.d_year = __YEAR__
          )
        GROUP BY warehouse.w_state, item.i_category, date_dim.d_year
        """,
        ("subquery", "join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各收入带下界和购买潜力对应的门店销售金额。",
        """
        SELECT income_band.ib_lower_bound AS income_lower,
               household_demographics.hd_buy_potential AS buy_potential,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(store_sales.ss_ext_sales_price) AS sales_amount
        FROM store_sales
        JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
        JOIN item ON store_sales.ss_item_sk = item.i_item_sk
        JOIN customer ON store_sales.ss_customer_sk = customer.c_customer_sk
        JOIN household_demographics
          ON customer.c_current_hdemo_sk = household_demographics.hd_demo_sk
        JOIN income_band
          ON household_demographics.hd_income_band_sk = income_band.ib_income_band_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY income_band.ib_lower_bound, household_demographics.hd_buy_potential,
                 item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各促销名称、门店所在州和商品类别的销售金额。",
        """
        SELECT promotion.p_promo_name AS promo_name,
               store.s_state AS store_state,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(store_sales.ss_ext_sales_price) AS sales_amount
        FROM store_sales
        JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
        JOIN item ON store_sales.ss_item_sk = item.i_item_sk
        JOIN store ON store_sales.ss_store_sk = store.s_store_sk
        JOIN promotion ON store_sales.ss_promo_sk = promotion.p_promo_sk
        JOIN customer ON store_sales.ss_customer_sk = customer.c_customer_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY promotion.p_promo_name, store.s_state, item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各营业班次、门店所在州和商品类别的销售金额。",
        """
        SELECT time_dim.t_shift AS shift_name,
               store.s_state AS store_state,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(store_sales.ss_ext_sales_price) AS sales_amount
        FROM store_sales
        JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
        JOIN time_dim ON store_sales.ss_sold_time_sk = time_dim.t_time_sk
        JOIN item ON store_sales.ss_item_sk = item.i_item_sk
        JOIN store ON store_sales.ss_store_sk = store.s_store_sk
        JOIN customer ON store_sales.ss_customer_sk = customer.c_customer_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY time_dim.t_shift, store.s_state, item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年账单地址州与收货地址州不同的网站订单，按网站和商品类别汇总销售金额。",
        """
        SELECT web_site.web_name AS web_name,
               bill_address.ca_state AS bill_state,
               ship_address.ca_state AS ship_state,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(web_sales.ws_ext_sales_price) AS sales_amount
        FROM web_sales
        JOIN date_dim ON web_sales.ws_sold_date_sk = date_dim.d_date_sk
        JOIN item ON web_sales.ws_item_sk = item.i_item_sk
        JOIN customer ON web_sales.ws_bill_customer_sk = customer.c_customer_sk
        JOIN customer_address AS bill_address
          ON web_sales.ws_bill_addr_sk = bill_address.ca_address_sk
        JOIN customer_address AS ship_address
          ON web_sales.ws_ship_addr_sk = ship_address.ca_address_sk
        JOIN web_site ON web_sales.ws_web_site_sk = web_site.web_site_sk
        WHERE date_dim.d_year = __YEAR__
          AND bill_address.ca_state <> ship_address.ca_state
        GROUP BY web_site.web_name, bill_address.ca_state, ship_address.ca_state,
                 item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年目录销售按婚姻状况、教育程度和收入带下界汇总净利润。",
        """
        SELECT customer_demographics.cd_marital_status AS marital_status,
               customer_demographics.cd_education_status AS education_status,
               income_band.ib_lower_bound AS income_lower,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(catalog_sales.cs_net_profit) AS net_profit
        FROM catalog_sales
        JOIN date_dim ON catalog_sales.cs_sold_date_sk = date_dim.d_date_sk
        JOIN item ON catalog_sales.cs_item_sk = item.i_item_sk
        JOIN customer ON catalog_sales.cs_bill_customer_sk = customer.c_customer_sk
        JOIN customer_demographics
          ON customer.c_current_cdemo_sk = customer_demographics.cd_demo_sk
        JOIN household_demographics
          ON customer.c_current_hdemo_sk = household_demographics.hd_demo_sk
        JOIN income_band
          ON household_demographics.hd_income_band_sk = income_band.ib_income_band_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY customer_demographics.cd_marital_status,
                 customer_demographics.cd_education_status,
                 income_band.ib_lower_bound, item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年既在门店又在网站购买过的顾客，按顾客所在州和商品类别汇总门店销售金额。",
        """
        WITH web_buyers AS (
            SELECT web_sales.ws_bill_customer_sk AS customer_sk,
                   web_sales.ws_item_sk AS item_sk
            FROM web_sales
            JOIN date_dim ON web_sales.ws_sold_date_sk = date_dim.d_date_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY web_sales.ws_bill_customer_sk, web_sales.ws_item_sk
        )
        SELECT customer_address.ca_state AS customer_state,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(store_sales.ss_ext_sales_price) AS sales_amount
        FROM store_sales
        JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
        JOIN item ON store_sales.ss_item_sk = item.i_item_sk
        JOIN customer ON store_sales.ss_customer_sk = customer.c_customer_sk
        JOIN customer_address
          ON customer.c_current_addr_sk = customer_address.ca_address_sk
        JOIN web_buyers
          ON web_buyers.customer_sk = store_sales.ss_customer_sk
         AND web_buyers.item_sk = store_sales.ss_item_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY customer_address.ca_state, item.i_category, date_dim.d_year
        """,
        ("cte", "join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年门店退货和目录退货按原因和商品类别汇总的退货金额。",
        """
        WITH return_rows AS (
            SELECT store_returns.sr_item_sk AS item_sk,
                   store_returns.sr_reason_sk AS reason_sk,
                   date_dim.d_year AS return_year,
                   SUM(store_returns.sr_return_amt) AS return_amount
            FROM store_returns
            JOIN date_dim ON store_returns.sr_returned_date_sk = date_dim.d_date_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY store_returns.sr_item_sk, store_returns.sr_reason_sk, date_dim.d_year
            UNION ALL
            SELECT catalog_returns.cr_item_sk, catalog_returns.cr_reason_sk,
                   date_dim.d_year, SUM(catalog_returns.cr_return_amount)
            FROM catalog_returns
            JOIN date_dim ON catalog_returns.cr_returned_date_sk = date_dim.d_date_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY catalog_returns.cr_item_sk, catalog_returns.cr_reason_sk, date_dim.d_year
        )
        SELECT reason.r_reason_desc AS return_reason,
               item.i_category AS item_category,
               return_rows.return_year AS return_year,
               SUM(return_rows.return_amount) AS return_amount
        FROM return_rows
        JOIN item ON item.i_item_sk = return_rows.item_sk
        JOIN reason ON reason.r_reason_sk = return_rows.reason_sk
        GROUP BY reason.r_reason_desc, item.i_category, return_rows.return_year
        """,
        ("cte", "join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各仓库所在州、促销名称和承运商的网站销售金额。",
        """
        SELECT warehouse.w_state AS warehouse_state,
               promotion.p_promo_name AS promo_name,
               ship_mode.sm_carrier AS carrier,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(web_sales.ws_ext_sales_price) AS sales_amount
        FROM web_sales
        JOIN date_dim ON web_sales.ws_sold_date_sk = date_dim.d_date_sk
        JOIN item ON web_sales.ws_item_sk = item.i_item_sk
        JOIN warehouse ON web_sales.ws_warehouse_sk = warehouse.w_warehouse_sk
        JOIN promotion ON web_sales.ws_promo_sk = promotion.p_promo_sk
        JOIN ship_mode ON web_sales.ws_ship_mode_sk = ship_mode.sm_ship_mode_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY warehouse.w_state, promotion.p_promo_name, ship_mode.sm_carrier,
                 item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各目录部门、呼叫中心和促销名称的目录销售金额。",
        """
        SELECT catalog_page.cp_department AS department,
               call_center.cc_name AS call_center_name,
               promotion.p_promo_name AS promo_name,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(catalog_sales.cs_ext_sales_price) AS sales_amount
        FROM catalog_sales
        JOIN date_dim ON catalog_sales.cs_sold_date_sk = date_dim.d_date_sk
        JOIN item ON catalog_sales.cs_item_sk = item.i_item_sk
        JOIN catalog_page
          ON catalog_sales.cs_catalog_page_sk = catalog_page.cp_catalog_page_sk
        JOIN call_center ON catalog_sales.cs_call_center_sk = call_center.cc_call_center_sk
        JOIN promotion ON catalog_sales.cs_promo_sk = promotion.p_promo_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY catalog_page.cp_department, call_center.cc_name,
                 promotion.p_promo_name, item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各出生年份和顾客所在州的门店销售金额。",
        """
        SELECT customer.c_birth_year AS birth_year,
               customer_address.ca_state AS customer_state,
               store.s_state AS store_state,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(store_sales.ss_ext_sales_price) AS sales_amount
        FROM store_sales
        JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
        JOIN item ON store_sales.ss_item_sk = item.i_item_sk
        JOIN customer ON store_sales.ss_customer_sk = customer.c_customer_sk
        JOIN customer_address
          ON customer.c_current_addr_sk = customer_address.ca_address_sk
        JOIN store ON store_sales.ss_store_sk = store.s_store_sk
        WHERE date_dim.d_year = __YEAR__
          AND customer.c_birth_year IS NOT NULL
        GROUP BY customer.c_birth_year, customer_address.ca_state,
                 store.s_state, item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年周末各营业班次和门店所在州的销售金额。",
        """
        SELECT time_dim.t_shift AS shift_name,
               store.s_state AS store_state,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(store_sales.ss_quantity) AS quantity_sold
        FROM store_sales
        JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
        JOIN time_dim ON store_sales.ss_sold_time_sk = time_dim.t_time_sk
        JOIN item ON store_sales.ss_item_sk = item.i_item_sk
        JOIN store ON store_sales.ss_store_sk = store.s_store_sk
        WHERE date_dim.d_year = __YEAR__
          AND date_dim.d_weekend = 'Y'
        GROUP BY time_dim.t_shift, store.s_state, item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年已婚顾客按教育程度和配送方式汇总的目录净利润。",
        """
        SELECT customer_demographics.cd_education_status AS education_status,
               ship_mode.sm_type AS ship_type,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(catalog_sales.cs_net_profit) AS net_profit
        FROM catalog_sales
        JOIN date_dim ON catalog_sales.cs_sold_date_sk = date_dim.d_date_sk
        JOIN item ON catalog_sales.cs_item_sk = item.i_item_sk
        JOIN customer ON catalog_sales.cs_bill_customer_sk = customer.c_customer_sk
        JOIN customer_demographics
          ON customer.c_current_cdemo_sk = customer_demographics.cd_demo_sk
        JOIN ship_mode ON catalog_sales.cs_ship_mode_sk = ship_mode.sm_ship_mode_sk
        WHERE date_dim.d_year = __YEAR__
          AND customer_demographics.cd_marital_status = 'M'
        GROUP BY customer_demographics.cd_education_status, ship_mode.sm_type,
                 item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "比较 __YEAR__ 年同一商品类别在网站和门店的销售金额。",
        """
        WITH store_totals AS (
            SELECT item.i_category AS item_category,
                   date_dim.d_year AS sales_year,
                   SUM(store_sales.ss_ext_sales_price) AS sales_amount
            FROM store_sales
            JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
            JOIN item ON store_sales.ss_item_sk = item.i_item_sk
            JOIN store ON store_sales.ss_store_sk = store.s_store_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY item.i_category, date_dim.d_year
        ),
        web_totals AS (
            SELECT item.i_category AS item_category,
                   date_dim.d_year AS sales_year,
                   SUM(web_sales.ws_ext_sales_price) AS sales_amount
            FROM web_sales
            JOIN date_dim ON web_sales.ws_sold_date_sk = date_dim.d_date_sk
            JOIN item ON web_sales.ws_item_sk = item.i_item_sk
            JOIN web_site ON web_sales.ws_web_site_sk = web_site.web_site_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY item.i_category, date_dim.d_year
        )
        SELECT store_totals.item_category AS item_category,
               store_totals.sales_year AS sales_year,
               store_totals.sales_amount AS store_sales_amount,
               web_totals.sales_amount AS web_sales_amount
        FROM store_totals
        JOIN web_totals
          ON web_totals.item_category = store_totals.item_category
         AND web_totals.sales_year = store_totals.sales_year
        """,
        ("cte", "join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各仓库所在州和商品类别的在手库存，并汇总这些库存商品当年的门店销售数量。",
        """
        WITH sold AS (
            SELECT store_sales.ss_item_sk AS item_sk,
                   SUM(store_sales.ss_quantity) AS quantity_sold
            FROM store_sales
            JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY store_sales.ss_item_sk
        ),
        stock AS (
            SELECT warehouse.w_state AS warehouse_state,
                   item.i_category AS item_category,
                   date_dim.d_year AS inventory_year,
                   inventory.inv_item_sk AS item_sk,
                   SUM(inventory.inv_quantity_on_hand) AS quantity_on_hand
            FROM inventory
            JOIN date_dim ON inventory.inv_date_sk = date_dim.d_date_sk
            JOIN item ON inventory.inv_item_sk = item.i_item_sk
            JOIN warehouse ON inventory.inv_warehouse_sk = warehouse.w_warehouse_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY warehouse.w_state, item.i_category, date_dim.d_year,
                     inventory.inv_item_sk
        )
        SELECT stock.warehouse_state AS warehouse_state,
               stock.item_category AS item_category,
               stock.inventory_year AS inventory_year,
               SUM(stock.quantity_on_hand) AS quantity_on_hand,
               SUM(sold.quantity_sold) AS quantity_sold
        FROM stock
        JOIN sold ON sold.item_sk = stock.item_sk
        GROUP BY stock.warehouse_state, stock.item_category, stock.inventory_year
        """,
        ("cte", "join", "aggregation"),
    ),
    (
        "比较 __YEAR__ 年同一承运商在目录和网站渠道的销售金额。",
        """
        WITH catalog_totals AS (
            SELECT ship_mode.sm_carrier AS carrier,
                   item.i_category AS item_category,
                   date_dim.d_year AS sales_year,
                   SUM(catalog_sales.cs_ext_sales_price) AS sales_amount
            FROM catalog_sales
            JOIN ship_mode ON catalog_sales.cs_ship_mode_sk = ship_mode.sm_ship_mode_sk
            JOIN date_dim ON catalog_sales.cs_sold_date_sk = date_dim.d_date_sk
            JOIN item ON catalog_sales.cs_item_sk = item.i_item_sk
            JOIN warehouse ON catalog_sales.cs_warehouse_sk = warehouse.w_warehouse_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY ship_mode.sm_carrier, item.i_category, date_dim.d_year
        ),
        web_totals AS (
            SELECT ship_mode.sm_carrier AS carrier,
                   item.i_category AS item_category,
                   date_dim.d_year AS sales_year,
                   SUM(web_sales.ws_ext_sales_price) AS sales_amount
            FROM web_sales
            JOIN ship_mode ON web_sales.ws_ship_mode_sk = ship_mode.sm_ship_mode_sk
            JOIN date_dim ON web_sales.ws_sold_date_sk = date_dim.d_date_sk
            JOIN item ON web_sales.ws_item_sk = item.i_item_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY ship_mode.sm_carrier, item.i_category, date_dim.d_year
        )
        SELECT catalog_totals.carrier AS carrier,
               catalog_totals.item_category AS item_category,
               catalog_totals.sales_year AS sales_year,
               catalog_totals.sales_amount AS catalog_sales_amount,
               web_totals.sales_amount AS web_sales_amount
        FROM catalog_totals
        JOIN web_totals
          ON web_totals.carrier = catalog_totals.carrier
         AND web_totals.item_category = catalog_totals.item_category
         AND web_totals.sales_year = catalog_totals.sales_year
        """,
        ("cte", "join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各促销目的和顾客性别的门店销售金额。",
        """
        SELECT promotion.p_purpose AS promo_purpose,
               customer_demographics.cd_gender AS gender,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(store_sales.ss_ext_sales_price) AS sales_amount
        FROM store_sales
        JOIN promotion ON store_sales.ss_promo_sk = promotion.p_promo_sk
        JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
        JOIN item ON store_sales.ss_item_sk = item.i_item_sk
        JOIN customer ON store_sales.ss_customer_sk = customer.c_customer_sk
        JOIN customer_demographics
          ON customer.c_current_cdemo_sk = customer_demographics.cd_demo_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY promotion.p_purpose, customer_demographics.cd_gender,
                 item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各呼叫中心所在州和顾客所在州的目录销售金额。",
        """
        SELECT call_center.cc_state AS call_center_state,
               customer_address.ca_state AS customer_state,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(catalog_sales.cs_ext_sales_price) AS sales_amount
        FROM catalog_sales
        JOIN call_center ON catalog_sales.cs_call_center_sk = call_center.cc_call_center_sk
        JOIN date_dim ON catalog_sales.cs_sold_date_sk = date_dim.d_date_sk
        JOIN item ON catalog_sales.cs_item_sk = item.i_item_sk
        JOIN customer ON catalog_sales.cs_bill_customer_sk = customer.c_customer_sk
        JOIN customer_address
          ON customer.c_current_addr_sk = customer_address.ca_address_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY call_center.cc_state, customer_address.ca_state,
                 item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各网页类型、顾客性别和网站的销售金额。",
        """
        SELECT web_page.wp_type AS page_type,
               customer_demographics.cd_gender AS gender,
               web_site.web_name AS web_name,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(web_sales.ws_ext_sales_price) AS sales_amount
        FROM web_sales
        JOIN web_page ON web_sales.ws_web_page_sk = web_page.wp_web_page_sk
        JOIN customer ON web_sales.ws_bill_customer_sk = customer.c_customer_sk
        JOIN customer_demographics
          ON customer.c_current_cdemo_sk = customer_demographics.cd_demo_sk
        JOIN date_dim ON web_sales.ws_sold_date_sk = date_dim.d_date_sk
        JOIN item ON web_sales.ws_item_sk = item.i_item_sk
        JOIN web_site ON web_sales.ws_web_site_sk = web_site.web_site_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY web_page.wp_type, customer_demographics.cd_gender, web_site.web_name,
                 item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各购买潜力、受抚养人数和收入带下界的门店销售金额。",
        """
        SELECT household_demographics.hd_buy_potential AS buy_potential,
               household_demographics.hd_dep_count AS dependent_count,
               income_band.ib_lower_bound AS income_lower,
               store.s_state AS store_state,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(store_sales.ss_ext_sales_price) AS sales_amount
        FROM store_sales
        JOIN customer ON store_sales.ss_customer_sk = customer.c_customer_sk
        JOIN household_demographics
          ON customer.c_current_hdemo_sk = household_demographics.hd_demo_sk
        JOIN income_band
          ON household_demographics.hd_income_band_sk = income_band.ib_income_band_sk
        JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
        JOIN item ON store_sales.ss_item_sk = item.i_item_sk
        JOIN store ON store_sales.ss_store_sk = store.s_store_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY household_demographics.hd_buy_potential,
                 household_demographics.hd_dep_count, income_band.ib_lower_bound,
                 store.s_state, item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年各退货原因和顾客所在州的门店退货金额。",
        """
        SELECT reason.r_reason_desc AS return_reason,
               customer_address.ca_state AS customer_state,
               store.s_state AS store_state,
               item.i_category AS item_category,
               date_dim.d_year AS return_year,
               SUM(store_returns.sr_return_amt) AS return_amount
        FROM store_returns
        JOIN reason ON store_returns.sr_reason_sk = reason.r_reason_sk
        JOIN customer ON store_returns.sr_customer_sk = customer.c_customer_sk
        JOIN customer_address
          ON customer.c_current_addr_sk = customer_address.ca_address_sk
        JOIN date_dim ON store_returns.sr_returned_date_sk = date_dim.d_date_sk
        JOIN item ON store_returns.sr_item_sk = item.i_item_sk
        JOIN store ON store_returns.sr_store_sk = store.s_store_sk
        WHERE date_dim.d_year = __YEAR__
        GROUP BY reason.r_reason_desc, customer_address.ca_state, store.s_state,
                 item.i_category, date_dim.d_year
        """,
        ("join", "aggregation"),
    ),
    (
        "统计 __YEAR__ 年电子类商品中，同年同店发生过退货的销售，"
        "按门店州、顾客州、性别、收入带和促销名称汇总销售金额。",
        """
        WITH returned_items AS (
            SELECT store_returns.sr_item_sk AS item_sk,
                   store_returns.sr_store_sk AS store_sk,
                   date_dim.d_year AS return_year
            FROM store_returns
            JOIN date_dim ON store_returns.sr_returned_date_sk = date_dim.d_date_sk
            JOIN reason ON store_returns.sr_reason_sk = reason.r_reason_sk
            WHERE date_dim.d_year = __YEAR__
            GROUP BY store_returns.sr_item_sk, store_returns.sr_store_sk, date_dim.d_year
        )
        SELECT store.s_state AS store_state,
               customer_address.ca_state AS customer_state,
               customer_demographics.cd_gender AS gender,
               income_band.ib_lower_bound AS income_lower,
               promotion.p_promo_name AS promo_name,
               item.i_category AS item_category,
               date_dim.d_year AS sales_year,
               SUM(store_sales.ss_ext_sales_price) AS sales_amount
        FROM store_sales
        JOIN date_dim ON store_sales.ss_sold_date_sk = date_dim.d_date_sk
        JOIN item ON store_sales.ss_item_sk = item.i_item_sk
        JOIN returned_items
          ON returned_items.item_sk = store_sales.ss_item_sk
         AND returned_items.store_sk = store_sales.ss_store_sk
         AND returned_items.return_year = date_dim.d_year
        JOIN store ON store_sales.ss_store_sk = store.s_store_sk
        JOIN customer ON store_sales.ss_customer_sk = customer.c_customer_sk
        JOIN customer_address
          ON customer.c_current_addr_sk = customer_address.ca_address_sk
        JOIN customer_demographics
          ON customer.c_current_cdemo_sk = customer_demographics.cd_demo_sk
        JOIN household_demographics
          ON customer.c_current_hdemo_sk = household_demographics.hd_demo_sk
        JOIN income_band
          ON household_demographics.hd_income_band_sk = income_band.ib_income_band_sk
        JOIN promotion ON store_sales.ss_promo_sk = promotion.p_promo_sk
        WHERE date_dim.d_year = __YEAR__
          AND item.i_category = 'Electronics'
        GROUP BY store.s_state, customer_address.ca_state, customer_demographics.cd_gender,
                 income_band.ib_lower_bound, promotion.p_promo_name, item.i_category,
                 date_dim.d_year
        """,
        ("cte", "join", "aggregation"),
    ),
)
