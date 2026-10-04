"""向量编码器。默认模型是固定版本的 BAAI/bge-m3。"""

from __future__ import annotations

import importlib
import math
from collections.abc import Sequence
from typing import Protocol

BGE_M3_MODEL = "BAAI/bge-m3"
BGE_M3_REVISION = "6892b95fed65c899a30896eb40d619ae284d0455"
EMBEDDING_DIMENSION = 1024


class Embedder(Protocol):
    """把检索文本编码为同一向量空间。"""

    model_name: str
    model_version: str
    dimension: int

    def embed_texts(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """按输入顺序返回向量。文档和查询使用同一个编码器。"""


class BgeM3Embedder:
    """BGE-M3 稠密向量。查询不加指令前缀，与文档共用一个空间。"""

    model_name = BGE_M3_MODEL
    model_version = BGE_M3_REVISION
    dimension = EMBEDDING_DIMENSION

    def __init__(self) -> None:
        self._encoder: _Encoder | None = None

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts or any(text.strip() == "" for text in texts):
            raise ValueError("embedding text must be non-empty")
        encoded = self._load().encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        rows = encoded.tolist()
        if len(rows) != len(texts):
            raise RuntimeError("embedder returned an unexpected number of vectors")
        return [_vector(row, self.dimension) for row in rows]

    def _load(self) -> _Encoder:
        if self._encoder is None:
            try:
                module = importlib.import_module("sentence_transformers")
            except ImportError as exc:
                raise RuntimeError(
                    "BAAI/bge-m3 requires the retrieval extra: uv sync --group retrieval"
                ) from exc
            encoder_type = module.SentenceTransformer
            self._encoder = encoder_type(self.model_name, revision=self.model_version)
        return self._encoder


class _Encoder(Protocol):
    def encode(
        self,
        texts: list[str],
        *,
        normalize_embeddings: bool,
        show_progress_bar: bool,
    ) -> _Array:
        """sentence-transformers 的最小调用面。"""


class _Array(Protocol):
    def tolist(self) -> list[list[float]]:
        """把编码结果转成普通列表。"""


def vector_literal(values: Sequence[float]) -> str:
    """生成只含数字的 pgvector 字面量，供绑定参数使用。"""

    numbers = _vector(values, EMBEDDING_DIMENSION)
    return "[" + ",".join(format(number, ".8f") for number in numbers) + "]"


def _vector(values: Sequence[float], dimension: int) -> list[float]:
    if len(values) != dimension:
        raise ValueError(f"expected {dimension} embedding dimensions")
    numbers: list[float] = []
    for value in values:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("embedding values must be finite")
        numbers.append(number)
    return numbers
