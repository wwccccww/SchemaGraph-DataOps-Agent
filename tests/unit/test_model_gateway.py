"""DeepSeek 网关只返回补全文本，不回传密钥或响应体。"""

from __future__ import annotations

import json

import httpx
import pytest
from app.config.settings import Settings
from app.llm.gateway import DEEPSEEK_MODEL, DeepSeekGateway
from app.llm.tokenizer import (
    DEEPSEEK_TOKENIZER_REVISION,
    DEEPSEEK_TOKENIZER_SHA256,
    DeepSeekTokenCounter,
)
from pydantic import SecretStr, ValidationError


def test_gateway_requires_a_real_key() -> None:
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        DeepSeekGateway(api_key=None)


def test_settings_reject_placeholder_api_key() -> None:
    with pytest.raises(ValidationError):
        Settings(
            postgres_user="text2sql_admin",
            postgres_password=SecretStr("local-admin-secret"),
            sandbox_db_password=SecretStr("local-sandbox-secret"),
            deepseek_api_key=SecretStr("replace-with-deepseek-api-key"),
        )


def test_settings_hide_api_key() -> None:
    settings = Settings(
        postgres_user="text2sql_admin",
        postgres_password=SecretStr("local-admin-secret"),
        sandbox_db_password=SecretStr("local-sandbox-secret"),
        deepseek_api_key=SecretStr("deepseek-test-key"),
    )

    assert "deepseek-test-key" not in repr(settings)


async def test_gateway_reads_the_completion_and_hides_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer deepseek-test-key"
        body = json.loads(request.content.decode())
        assert body["model"] == DEEPSEEK_MODEL
        assert body["temperature"] == 0
        assert body["stream"] is False
        return httpx.Response(200, json={"choices": [{"message": {"content": "SELECT 1"}}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        gateway = DeepSeekGateway(api_key=SecretStr("deepseek-test-key"), client=client)
        sql = await gateway.complete(
            [{"role": "user", "content": "问题"}],
            temperature=0,
        )

    assert sql == "SELECT 1"


async def test_gateway_error_does_not_include_the_response_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "deepseek-test-key leaked"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        gateway = DeepSeekGateway(api_key=SecretStr("deepseek-test-key"), client=client)
        with pytest.raises(RuntimeError, match="status 401") as caught:
            await gateway.complete([{"role": "user", "content": "问题"}], temperature=0)

    assert "deepseek-test-key" not in str(caught.value)
    assert "leaked" not in str(caught.value)


def test_tokenizer_identity_is_pinned() -> None:
    counter = DeepSeekTokenCounter(counter=lambda text: len(text.split()))

    assert len(DEEPSEEK_TOKENIZER_REVISION) == 40
    assert len(DEEPSEEK_TOKENIZER_SHA256) == 64
    assert counter.count("") == 0
    assert counter.count("订单 表") == 2
