"""DeepSeek-V3 tokenizer。只在第一次计数时下载词表。"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path

import httpx

DEEPSEEK_TOKENIZER_MODEL = "deepseek-ai/DeepSeek-V3"
DEEPSEEK_TOKENIZER_REVISION = "e815299b0bcbac849fa540c768ef21845365c9eb"
DEEPSEEK_TOKENIZER_SHA256 = "621ac2e32d0dba658404412318818aaa8ce8cda492e59830109d8da6b517fb41"


class DeepSeekTokenCounter:
    """用固定修订版的 DeepSeek-V3 词表计数。"""

    model_name = DEEPSEEK_TOKENIZER_MODEL
    revision = DEEPSEEK_TOKENIZER_REVISION

    def __init__(self, counter: Callable[[str], int] | None = None) -> None:
        self._counter = counter

    def count(self, text: str) -> int:
        if text == "":
            return 0
        if self._counter is None:
            self._counter = _load_counter()
        return self._counter(text)


def _load_counter() -> Callable[[str], int]:
    from tokenizers import Tokenizer

    path = _tokenizer_file()
    tokenizer = Tokenizer.from_file(str(path))

    def count(text: str) -> int:
        return len(tokenizer.encode(text).ids)

    return count


def _tokenizer_file() -> Path:
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    path = cache_root / "schemagraph" / f"deepseek-v3-{DEEPSEEK_TOKENIZER_REVISION}.json"
    if path.is_file() and _sha256(path) == DEEPSEEK_TOKENIZER_SHA256:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    url = (
        f"https://huggingface.co/{DEEPSEEK_TOKENIZER_MODEL}/resolve/"
        f"{DEEPSEEK_TOKENIZER_REVISION}/tokenizer.json"
    )
    temporary = path.with_suffix(".json.partial")
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            temporary.write_bytes(response.content)
        if _sha256(temporary) != DEEPSEEK_TOKENIZER_SHA256:
            raise RuntimeError("DeepSeek tokenizer hash mismatch")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
