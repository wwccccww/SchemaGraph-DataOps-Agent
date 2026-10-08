"""50 条慢 SQL Benchmark 用例加载与静态规则覆盖。"""

from __future__ import annotations

import yaml

from app.agents.slow_sql.rules import _RULE_ORDER, diagnose_sql
from app.evaluation.slow_sql import FULL_PATH, FULL_SLOW_SQL_CASE_COUNT, load_full_slow_sql_cases
from app.evaluation.slow_sql_catalog import FULL_CASE_COUNT, full_slow_sql_case_payloads


def test_full_yaml_matches_catalog() -> None:
    payload = yaml.safe_load(FULL_PATH.read_text(encoding="utf-8"))
    assert payload["case_count"] == FULL_CASE_COUNT
    assert payload["cases"] == full_slow_sql_case_payloads()


def test_catalog_defines_fifty_cases() -> None:
    payloads = full_slow_sql_case_payloads()
    assert len(payloads) == FULL_CASE_COUNT == FULL_SLOW_SQL_CASE_COUNT
    ids = [item["id"] for item in payloads]
    assert len(ids) == len(set(ids))


def test_full_yaml_loads_fifty_cases() -> None:
    text = FULL_PATH.read_text(encoding="utf-8")
    assert "reference" not in text.lower()
    assert "gold_sql" not in text
    cases = load_full_slow_sql_cases()
    assert len(cases) == 50
    assert cases[0].snapshot_version == "ecommerce-v1"
    assert cases[0].database_id == "ecommerce"


def test_each_full_case_triggers_declared_antipattern() -> None:
    cases = load_full_slow_sql_cases()
    for case in cases:
        findings = {item.rule_id for item in diagnose_sql(case.sql)}
        if case.antipattern == "seq-scan-on-large-table":
            # 全表扫描由 EXPLAIN 计划诊断；静态规则不标记此类。
            assert case.index_preconditions, case.id
            assert any("idx_order_status" in item for item in case.index_preconditions)
            continue
        assert case.antipattern in findings, (
            f"{case.id} expected {case.antipattern}, got {sorted(findings)}"
        )
        assert (
            case.antipattern in case.allowed_rewrite_categories
            or "rewrite" in case.allowed_rewrite_categories
        )


def test_full_benchmark_covers_all_rule_categories() -> None:
    cases = load_full_slow_sql_cases()
    covered = {case.antipattern for case in cases}
    assert covered == set(_RULE_ORDER)
