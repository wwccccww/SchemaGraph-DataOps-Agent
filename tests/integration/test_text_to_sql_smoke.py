"""10 条冒烟用例可生成、执行并计算 EX，失败路径会修复或熔断。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest
from app.agents.text_to_sql.runtime import build_services
from app.agents.text_to_sql.workflow import run_text_to_sql
from app.db.catalog import load_table_documents
from app.db.engine import get_admin_engine
from app.db.seed import seed_ecommerce
from app.db.tables import JUNCTION_TABLES
from app.evaluation.smoke import load_smoke_cases
from app.evaluation.text_to_sql import score_case, score_smoke_cases
from app.graph.expand import EstimatedTokenCounter
from app.mcp.definitions import TOOLS
from app.retrieval.embedder import EMBEDDING_DIMENSION
from app.retrieval.index import (
    ensure_embedding_tables,
    upsert_schema_embeddings,
    upsert_tool_embeddings,
)
from app.retrieval.text import schema_document_text
from app.sandbox.execute import ExecutionError, ExecutionSuccess, execute_readonly
from app.schemas.benchmark import BenchmarkCase
from app.schemas.catalog import TableDocument

pytestmark = pytest.mark.integration

_PREFERRED_AXES = {
    "t_user": 4,
    "t_user_level": 6,
    "t_order": 1,
    "t_product": 3,
    "t_merchant": 8,
}


class LookupEmbedder:
    """按预定文本返回向量，避免在测试中下载 BGE-M3。"""

    model_name = "test-embedder"
    model_version = "test-v1"
    dimension = EMBEDDING_DIMENSION

    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._mapping = mapping

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._mapping[text] for text in texts]


class GoldModel:
    """用问题文本返回答案。答案来自测试夹具，不来自 Prompt。"""

    def __init__(self, cases: Sequence[BenchmarkCase]) -> None:
        self._answers = {case.question: case.gold_sql for case in cases}
        self.prompts: list[str] = []

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float,
    ) -> str:
        del temperature
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        for question, sql in self._answers.items():
            if f"问题：\n{question}\n" in prompt:
                return sql
        raise AssertionError("prompt is missing the question")


class SequenceModel:
    """按调用顺序返回 SQL。"""

    def __init__(self, answers: Sequence[str]) -> None:
        self._answers = list(answers)
        self.prompts: list[str] = []

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float,
    ) -> str:
        del temperature
        self.prompts.append(messages[-1]["content"])
        return self._answers[min(len(self.prompts) - 1, len(self._answers) - 1)]


def _axis(index: int, scale: float = 1.0) -> list[float]:
    values = [0.0] * EMBEDDING_DIMENSION
    values[index] = scale
    return values


def _query(*pairs: tuple[int, float]) -> list[float]:
    values = [0.0] * EMBEDDING_DIMENSION
    for index, scale in pairs:
        values[index] = scale
    return values


def _embedder(documents: Sequence[TableDocument], cases: Sequence[BenchmarkCase]) -> LookupEmbedder:
    mapping = {
        schema_document_text(document): _axis(0)
        if document.is_junction
        else _axis(_PREFERRED_AXES.get(document.table_name, 20 + index))
        for index, document in enumerate(documents)
    }
    question_vector = _query((4, 1.0), (6, 0.9), (1, 0.8), (3, 0.7), (8, 0.6))
    for case in cases:
        mapping[case.question] = question_vector
    for offset, tool in enumerate(TOOLS):
        mapping[tool.embedding_text()] = _axis(40 + offset)
    return LookupEmbedder(mapping)


async def _guarded_execute(sql: str, *, max_rows: int) -> ExecutionSuccess | ExecutionError:
    if "INSERT" in sql.upper() or "UPDATE" in sql.upper() or "DELETE" in sql.upper():
        raise AssertionError("write SQL reached the database")
    return await execute_readonly(sql, max_rows=max_rows)


async def test_smoke_cases_and_failure_paths(database_settings) -> None:
    del database_settings
    await seed_ecommerce()
    cases = load_smoke_cases()
    async with get_admin_engine().begin() as conn:
        documents = await load_table_documents(conn)
        embedder = _embedder(documents, cases)
        await ensure_embedding_tables(conn)
        await upsert_schema_embeddings(conn, documents, embedder)
        await upsert_tool_embeddings(conn, embedder)

    gold_model = GoldModel(cases)
    services = build_services(
        embedder=embedder,
        model=gold_model,
        token_counter=EstimatedTokenCounter(),
    )
    services = _with_executor(services)
    scores = await score_smoke_cases(services)

    assert [score.ex for score in scores] == [1] * 10
    assert all(score.attempts == 1 for score in scores)
    for case, prompt in zip(cases, gold_model.prompts, strict=True):
        assert " ".join(case.gold_sql.split()) not in " ".join(prompt.split())
        assert "required_tables" not in prompt
    assert set(JUNCTION_TABLES).isdisjoint(
        (
            await run_text_to_sql(
                services,
                question=cases[0].question,
                database_id="ecommerce",
                execute=False,
            )
        ).schema_context.seed_tables  # type: ignore[union-attr]
    )

    basic = cases[0]
    repair_model = SequenceModel(["INSERT INTO t_user_level VALUES (1, 'x', 1)", basic.gold_sql])
    repair_services = _with_executor(
        build_services(
            embedder=embedder,
            model=repair_model,
            token_counter=EstimatedTokenCounter(),
        )
    )
    repaired = await score_case(basic, repair_services)
    assert repaired.ex == 1
    assert repaired.attempts == 2
    assert "上一次 SQL" in repair_model.prompts[1]
    assert "postgres://" not in repair_model.prompts[1]

    database_model = SequenceModel(["SELECT missing_column FROM t_user_level", basic.gold_sql])
    database_services = _with_executor(
        build_services(
            embedder=embedder,
            model=database_model,
            token_counter=EstimatedTokenCounter(),
        )
    )
    repaired_database = await score_case(basic, database_services)
    assert repaired_database.ex == 1
    assert repaired_database.attempts == 2
    assert "missing_column" in database_model.prompts[1]
    assert "password" not in database_model.prompts[1].lower()

    breaker_model = SequenceModel(["SELECT missing_column FROM t_user_level"])
    breaker_services = _with_executor(
        build_services(
            embedder=embedder,
            model=breaker_model,
            token_counter=EstimatedTokenCounter(),
        )
    )
    first = await run_text_to_sql(
        breaker_services,
        question=basic.question,
        database_id="ecommerce",
    )
    second = await run_text_to_sql(
        breaker_services,
        question=basic.question,
        database_id="ecommerce",
    )
    assert first.status == "failed"
    assert first.attempts == 3
    assert first.error is not None
    assert first.error.category == "circuit_breaker"
    assert second.attempts == 3
    assert second.error is not None
    assert second.error.category == "circuit_breaker"
    assert len(breaker_model.prompts) == 6


def _with_executor(services):  # type: ignore[no-untyped-def]
    return type(services)(
        model=services.model,
        select_tools=services.select_tools,
        select_seeds=services.select_seeds,
        load_catalog=services.load_catalog,
        execute=_guarded_execute,
        token_counter=services.token_counter,
    )
