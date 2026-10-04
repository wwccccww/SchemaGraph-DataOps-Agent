"""每个请求一条 OpenTelemetry Trace。默认不把 Span 发到收集器。"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import TypedDict

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Span

TRACE_FIELDS: tuple[str, ...] = (
    "request_type",
    "model_name",
    "retrieved_seed_tables",
    "expanded_tables",
    "schema_context_tokens",
    "selected_tools",
    "generation_attempt",
    "sql_hash",
    "error_hash",
    "db_execution_ms",
    "planner_total_cost",
    "result_row_count",
    "circuit_breaker_triggered",
)
_SPAN_BUFFER = 64
_exporter = InMemorySpanExporter(max_spans=_SPAN_BUFFER)
_provider = TracerProvider(resource=Resource.create({"service.name": "schemagraph-dataops-agent"}))
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
if os.environ.get("OTEL_TRACES_EXPORTER") == "console":
    _provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))


class RequestTrace(TypedDict):
    """架构规定的 Trace 字段。不包含问题、SQL、Prompt 或结果行。"""

    request_type: str
    model_name: str
    retrieved_seed_tables: tuple[str, ...]
    expanded_tables: tuple[str, ...]
    schema_context_tokens: int
    selected_tools: tuple[str, ...]
    generation_attempt: int
    sql_hash: str
    error_hash: str
    db_execution_ms: float
    planner_total_cost: float
    result_row_count: int
    circuit_breaker_triggered: bool


def sql_hash(sql: str | None) -> str:
    """对 SQL 做稳定摘要。空 SQL 不产生哈希。"""

    if sql is None or sql == "":
        return ""
    digest = hashlib.sha256(sql.encode()).hexdigest()
    return f"sha256:{digest}"


def model_name_of(model: object) -> str:
    """读取模型名。测试替身没有该属性时记为 unspecified。"""

    value = getattr(model, "model", None)
    if isinstance(value, str) and value.strip():
        return value
    return "unspecified"


@contextmanager
def request_span(name: str) -> Iterator[Span]:
    """打开一条请求 Span。调用方只在结束前写入约定字段。"""

    tracer = _provider.get_tracer("schemagraph.dataops")
    with tracer.start_as_current_span(name) as span:
        yield span


def set_request_attributes(span: Span, fields: RequestTrace) -> None:
    """写入全部约定字段。多写或少写都拒绝，避免把状态原文放进 Trace。"""

    unexpected = set(fields) - set(TRACE_FIELDS)
    missing = set(TRACE_FIELDS) - set(fields)
    if unexpected or missing:
        raise ValueError("trace fields must match the architecture contract")
    span.set_attributes(
        {
            "request_type": fields["request_type"],
            "model_name": fields["model_name"],
            "retrieved_seed_tables": fields["retrieved_seed_tables"],
            "expanded_tables": fields["expanded_tables"],
            "schema_context_tokens": fields["schema_context_tokens"],
            "selected_tools": fields["selected_tools"],
            "generation_attempt": fields["generation_attempt"],
            "sql_hash": fields["sql_hash"],
            "error_hash": fields["error_hash"],
            "db_execution_ms": fields["db_execution_ms"],
            "planner_total_cost": fields["planner_total_cost"],
            "result_row_count": fields["result_row_count"],
            "circuit_breaker_triggered": fields["circuit_breaker_triggered"],
        }
    )


def finished_spans() -> tuple[ReadableSpan, ...]:
    """返回内存中尚未丢弃的 Span，供测试读取。"""

    return _exporter.get_finished_spans()


def clear_spans() -> None:
    """清空内存中的 Span。生产导出器本身不保留超过上限的历史。"""

    _exporter.clear()


def attribute_map(span: ReadableSpan) -> Mapping[str, object]:
    """读取 Span 属性。没有属性时返回空映射。"""

    return dict(span.attributes or {})
