"""BIRD 复杂用例。

问题、db_id 和 Gold SQL 来自固定的公开开发集。evidence 不是用例字段，
也不会进入问数 Prompt。导入本模块不会下载数据库或调用模型。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import yaml

from app.evaluation.case_yaml import dump_benchmark_cases, projection_names
from app.evaluation.custom_cases import referenced_tables
from app.sandbox.sqlite import check_sqlite_read_only
from app.schemas.benchmark import BenchmarkCase

QUESTIONS_PATH = (
    Path(__file__).resolve().parents[2] / "benchmarks" / "bird_complex" / "dev_20251106.json"
)
CASES_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "bird_complex" / "cases.yaml"
EXCLUSIONS_PATH = (
    Path(__file__).resolve().parents[2] / "benchmarks" / "bird_complex" / "exclusions.json"
)
CHECKSUMS_PATH = (
    Path(__file__).resolve().parents[2] / "benchmarks" / "bird_complex" / "database_checksums.json"
)
BIRD_SOURCE_VERSION = "bird-sql-dev-20251106@3c11fb193e5439b338e23677fa0aae11e8b85db9"
QUESTIONS_SHA256 = "ffd8018378ddb1a8794753e0a31cfc81862ff7318a5184c22f3dc4ce03a03feb"
DATASET_COMMIT = "3c11fb193e5439b338e23677fa0aae11e8b85db9"
DATABASE_ZIP_SHA256 = "aeb211c0e39010bbdae3838bb5e8bd27dc446ed77495b1709f85ccc9bf67f2be"
DATABASE_DRIVE_ID = "13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG"
BIRD_CASE_COUNT = 50
ANCHOR = date(2026, 10, 1)
_ORDER_REQUEST = re.compile(
    r"\b(?:sorted|sorting|ascending|descending|alphabetical)\b"
    r"|\border(?:ed)?\s+by\b"
    r"|\bin\s+(?:ascending|descending)\s+order\b",
    re.IGNORECASE,
)


def load_bird_questions(path: Path | None = None) -> list[dict[str, object]]:
    """读取固定问题文件。默认路径必须匹配已记录的摘要。"""

    file = path or QUESTIONS_PATH
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    if path is None and digest != QUESTIONS_SHA256:
        raise ValueError("bird question file does not match the pinned digest")
    payload = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("bird questions must be a list")
    rows: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("bird question must be an object")
        rows.append(item)
    return rows


def load_bird_exclusions(path: Path | None = None) -> set[int]:
    """读取无法由受限适配器执行的 question_id。"""

    file = path or EXCLUSIONS_PATH
    payload = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("bird exclusions must be an object")
    raw = payload.get("question_ids")
    if not isinstance(raw, list) or not all(isinstance(item, int) for item in raw):
        raise ValueError("bird exclusions need integer question_ids")
    return set(raw)


def load_database_checksums(path: Path | None = None) -> dict[str, str]:
    """读取各 SQLite 文件的 sha256。键是 db_id。"""

    file = path or CHECKSUMS_PATH
    payload = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("bird checksum file must be an object")
    checksums: dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("bird checksum entries must be strings")
        checksums[key] = value
    return checksums


def load_bird_cases(path: Path | None = None) -> list[BenchmarkCase]:
    """读取冻结的 50 条 BIRD 用例。"""

    payload = yaml.safe_load((path or CASES_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("contract_version") != "1.0":
        raise ValueError("bird case file must declare contract_version 1.0")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("bird case file must contain a cases list")
    return [BenchmarkCase.model_validate(case) for case in cases]


def build_bird_cases(
    questions: Sequence[Mapping[str, object]] | None = None,
    exclusions: set[int] | None = None,
) -> list[BenchmarkCase]:
    """按 question_id 升序取前 50 条可静态判定为只读的复杂用例。"""

    rows = list(questions) if questions is not None else load_bird_questions()
    skipped = exclusions if exclusions is not None else load_bird_exclusions()
    cases: list[BenchmarkCase] = []
    for row in _challenging(rows):
        question_id = int(str(row["question_id"]))
        if question_id in skipped:
            continue
        if check_sqlite_read_only(str(row["SQL"])) is None:
            continue
        cases.append(materialize_bird_case(row))
        if len(cases) == BIRD_CASE_COUNT:
            break
    if len(cases) != BIRD_CASE_COUNT:
        raise RuntimeError("bird case builder did not reach 50 executable cases")
    return cases


def materialize_bird_case(row: Mapping[str, object]) -> BenchmarkCase:
    """把原始问题行变成用例。不复制 evidence。"""

    question_id = int(str(row["question_id"]))
    question = str(row["question"]).strip()
    gold_sql = str(row["SQL"]).strip()
    database_id = str(row["db_id"])
    tables = sorted(referenced_tables(gold_sql, dialect="sqlite"))
    return BenchmarkCase(
        id=f"bird_{question_id:04d}",
        source="bird",
        source_version=BIRD_SOURCE_VERSION,
        database_id=database_id,
        difficulty="complex",
        dialect="sqlite",
        question=question,
        gold_sql=gold_sql,
        required_tables=tables,
        required_junctions=[],
        order_sensitive=question_requests_order(question),
        numeric_tolerance=None,
        expected_columns=projection_names(gold_sql, dialect="sqlite"),
        anchor_date=ANCHOR,
        tags=["bird", "challenging", database_id],
    )


def dump_bird_cases(cases: list[BenchmarkCase]) -> str:
    """冻结 BIRD 用例。"""

    return dump_benchmark_cases(cases)


def question_requests_order(question: str) -> bool:
    """只有问题明确要求排序时，结果顺序才属于答案。"""

    return _ORDER_REQUEST.search(question) is not None


def challenging_question_ids(questions: Sequence[Mapping[str, object]]) -> list[int]:
    """复杂题的 question_id，升序。"""

    return [int(str(row["question_id"])) for row in _challenging(questions)]


def _challenging(questions: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    rows = [row for row in questions if row.get("difficulty") == "challenging"]
    return sorted(rows, key=lambda row: int(str(row["question_id"])))
