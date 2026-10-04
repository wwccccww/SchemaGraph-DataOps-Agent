"""结构化沙箱错误与稳定 Error Hash。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_LINE = re.compile(r"\bLINE \d+:")
_POSITION = re.compile(r"\b(?:at character|at or near) \d+\b", re.IGNORECASE)
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_ADDRESS = re.compile(r"\b0x[0-9a-fA-F]+\b")
_CONNECTION = re.compile(r"\b(?:postgres|postgresql|https?)://\S+", re.IGNORECASE)
_PATH = re.compile(r"(?:/[A-Za-z0-9._-]+){2,}")
_SECRET = re.compile(r"(?i)(password|secret|api[_-]?key)\s*[:=]\s*\S+")
_TEMP_NAME = re.compile(r"\bpg_temp(?:_\d+)?\b", re.IGNORECASE)
_LITERAL = re.compile(r"'(?:''|[^'])*'")
_MESSAGE_LIMIT = 500


@dataclass(frozen=True)
class ExecutionError:
    """可回传给模型的最小错误。不含原始异常和连接信息。"""

    category: str
    sqlstate: str | None
    exception_type: str
    normalized_message: str
    error_hash: str
    retryable: bool


def normalize_message(message: str) -> str:
    """去掉位置、临时名、字面量、凭据和路径，保留错误类别。"""

    text = _ANSI.sub("", message)
    text = _SECRET.sub(r"\1=<redacted>", text)
    text = _CONNECTION.sub("<connection>", text)
    text = _PATH.sub("<path>", text)
    text = _UUID.sub("<uuid>", text)
    text = _ADDRESS.sub("<address>", text)
    text = _TEMP_NAME.sub("<temp>", text)
    text = _LINE.sub("LINE <n>:", text)
    text = re.sub(r"LINE <n>:.*", "LINE <n>", text)
    text = _POSITION.sub("at character <n>", text)
    text = _LITERAL.sub("<literal>", text)
    text = " ".join(text.split())
    return text[:_MESSAGE_LIMIT]


def error_hash(sqlstate: str | None, exception_type: str, normalized_message: str) -> str:
    """对 sqlstate、异常类型和规范化消息做稳定摘要。"""

    payload = f"{sqlstate or ''}|{exception_type}|{normalized_message}"
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"sha256:{digest}"


def make_error(
    *,
    category: str,
    message: str,
    exception_type: str,
    sqlstate: str | None = None,
    retryable: bool,
) -> ExecutionError:
    """生成已经规范化的错误。"""

    normalized = normalize_message(message)
    return ExecutionError(
        category=category,
        sqlstate=sqlstate,
        exception_type=exception_type,
        normalized_message=normalized,
        error_hash=error_hash(sqlstate, exception_type, normalized),
        retryable=retryable,
    )
