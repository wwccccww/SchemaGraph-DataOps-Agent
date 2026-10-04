"""扫描已跟踪文件中的高置信密钥。不读取未跟踪的 .env。"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----")
_AWS_ACCESS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_MODEL_KEY = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
_PG_URL = re.compile(r"\bpostgres(?:ql)?://[^\s/@:]+:[^\s/@]+@", re.IGNORECASE)
_ASSIGNMENT = re.compile(r"(?i)(?:api[_-]?key|secret|password|token)\s*[=:]\s*['\"]?([^\s'\"]+)")
_LIVE_SECRET = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")
_PLACEHOLDERS = frozenset(
    {
        "replace-with-local-password",
        "replace-with-local-sandbox-password",
        "replace-with-deepseek-api-key",
    }
)
_ASSIGNMENT_FILES = frozenset({"docker-compose.yml", "Dockerfile", ".env.example"})


@dataclass(frozen=True)
class SecretFinding:
    """一处命中。只保留位置和规则名，不保留匹配原文。"""

    path: str
    line: int
    rule: str


def scan_tracked_files(root: Path) -> list[SecretFinding]:
    """扫描 git 已跟踪的文本文件。"""

    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    findings: list[SecretFinding] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode()
        file = root / relative
        if not file.is_file():
            continue
        data = file.read_bytes()
        if b"\0" in data[:1024]:
            continue
        findings.extend(scan_text(relative, data.decode("utf-8", errors="replace")))
    return findings


def scan_text(path: str, text: str) -> list[SecretFinding]:
    """按行扫描一段文本。连接串和赋值只检查部署文件与 app。"""

    findings: list[SecretFinding] = []
    assignment_scope = _in_assignment_scope(path)
    for number, line in enumerate(text.splitlines(), start=1):
        if _PRIVATE_KEY.search(line):
            findings.append(SecretFinding(path, number, "private_key"))
        if _AWS_ACCESS_KEY.search(line):
            findings.append(SecretFinding(path, number, "aws_access_key"))
        if _MODEL_KEY.search(line):
            findings.append(SecretFinding(path, number, "model_key"))
        if not assignment_scope:
            continue
        if _PG_URL.search(line):
            findings.append(SecretFinding(path, number, "postgres_url"))
        findings.extend(_assignment_findings(path, number, line))
    return findings


def _in_assignment_scope(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith("app/") or normalized in _ASSIGNMENT_FILES


def _assignment_findings(path: str, number: int, line: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for match in _ASSIGNMENT.finditer(line):
        if _is_live_secret(match.group(1)):
            findings.append(SecretFinding(path, number, "assigned_secret"))
    return findings


def _is_live_secret(value: str) -> bool:
    if value in _PLACEHOLDERS or value.startswith("${") or value.startswith("<"):
        return False
    return _LIVE_SECRET.fullmatch(value) is not None
