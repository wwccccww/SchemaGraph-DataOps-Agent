"""外部报告按来源分开，并且不写入自建 Target。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

import pytest
from app.evaluation.external_report import GoldTrace, build_external_summary, write_external_report
from app.schemas.benchmark import BenchmarkCase, BenchmarkSource


def _case(case_id: str, source: BenchmarkSource) -> BenchmarkCase:
    dialect: Literal["postgres", "sqlite"] = "sqlite" if source == "bird" else "postgres"
    return BenchmarkCase(
        id=case_id,
        source=source,
        source_version="v1",
        database_id="sample",
        difficulty="complex",
        dialect=dialect,
        question="统计样例销售金额",
        gold_sql="SELECT 1 AS total",
        required_tables=["store_sales"],
        required_junctions=[],
        order_sensitive=False,
        numeric_tolerance=None,
        expected_columns=["total"],
        anchor_date=date(2026, 10, 1),
        tags=["aggregation"],
    )


def test_external_summary_leaves_measured_accuracy_empty(tmp_path: Path) -> None:
    case = _case("bird_0001", "bird")
    trace = GoldTrace("bird_0001", "ok", 3, "abc", None)
    summary = build_external_summary(
        [case],
        [trace],
        source="bird",
        benchmark_version="bird-test",
        git_commit="abc1234",
        database_snapshot="snapshot",
        started_at="2026-10-04T00:00:00Z",
        environment={"executor": "sqlite-readonly-adapter"},
    )

    directory = write_external_report(
        tmp_path,
        stamp="20261004T000000Z",
        commit="abc1234",
        summary=summary,
        traces=[trace],
    )
    text = (directory / "summary.json").read_text(encoding="utf-8")

    assert summary["target"] is None
    assert summary["mixed_with_custom"] is False
    assert summary["official_tpcds_result"] is False
    assert summary["measured"] == {"execution_accuracy": None}
    for token in ("0.83", "0.968", "0.684", "0.742", "0.81", "0.72", "0.86", "custom_"):
        assert token not in text
    with pytest.raises(FileExistsError):
        write_external_report(
            tmp_path,
            stamp="20261004T000000Z",
            commit="abc1234",
            summary=summary,
            traces=[trace],
        )


def test_custom_cases_cannot_enter_an_external_report() -> None:
    case = _case("custom_basic_001", "custom")
    with pytest.raises(ValueError, match="custom"):
        build_external_summary(
            [case],
            [GoldTrace(case.id, "ok", 1, "abc", None)],
            source="bird",
            benchmark_version="bird-test",
            git_commit="abc1234",
            database_snapshot="snapshot",
            started_at="2026-10-04T00:00:00Z",
            environment={},
        )


def test_report_file_matches_the_trace(tmp_path: Path) -> None:
    case = _case("tpcds_complex_001", "tpcds-derived")
    trace = GoldTrace(case.id, "error", None, None, "42P01")
    summary = build_external_summary(
        [case],
        [trace],
        source="tpcds-derived",
        benchmark_version="tpcds-test",
        git_commit="abc1234",
        database_snapshot="snapshot",
        started_at="2026-10-04T00:00:00Z",
        environment={"postgres": "16"},
    )
    directory = write_external_report(
        tmp_path / "tpcds",
        stamp="20261004T010000Z",
        commit="abc1234",
        summary=summary,
        traces=[trace],
    )
    case_path = directory / "cases" / "tpcds_complex_001.json"
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    assert payload["status"] == "error"
    assert payload["error"] == "42P01"
