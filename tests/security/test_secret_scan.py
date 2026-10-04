"""已跟踪文件不能包含高置信密钥。测试样本本身拆开书写。"""

from __future__ import annotations

from pathlib import Path

from app.observability.secret_scan import scan_text, scan_tracked_files

_ROOT = Path(__file__).resolve().parents[2]


def test_tracked_files_have_no_high_confidence_secrets() -> None:
    assert scan_tracked_files(_ROOT) == []


def test_scanner_flags_private_keys_cloud_keys_and_model_keys() -> None:
    private = "-----BEGIN " + "PRIVATE KEY-----"
    aws = "AKIA" + "IOSFODNN7EXAMPLE"
    token = "sk-" + ("a" * 20)
    text = "\n".join([private, aws, token])

    findings = scan_text("docs/example.md", text)

    assert [item.rule for item in findings] == ["private_key", "aws_access_key", "model_key"]
    assert all(item.path == "docs/example.md" for item in findings)


def test_assignment_scope_flags_urls_and_live_secrets_but_allows_placeholders() -> None:
    url = "postgres://" + "sandbox:super-secret@db:5432/text2sql_db"
    live = "api_key=" + ("b" * 24)
    placeholders = "\n".join(
        [
            "POSTGRES_PASSWORD=replace-with-local-password",
            "SANDBOX_DB_PASSWORD=replace-with-local-sandbox-password",
            "DEEPSEEK_API_KEY=replace-with-deepseek-api-key",
        ]
    )

    assert [item.rule for item in scan_text("app/config.py", url)] == ["postgres_url"]
    assert [item.rule for item in scan_text(".env.example", live)] == ["assigned_secret"]
    assert scan_text(".env.example", placeholders) == []
    assert scan_text("tests/unit/test_error_hash.py", url) == []
