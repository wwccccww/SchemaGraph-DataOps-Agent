"""OpenAI 兼容的 DeepSeek 聊天接口。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

import httpx
from pydantic import SecretStr

DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class ChatModel(Protocol):
    """生成一条补全。调用方负责不把补全写入普通日志。"""

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float,
    ) -> str:
        """返回模型原文。"""


class DeepSeekGateway:
    """DeepSeek-V3 的 OpenAI 兼容网关。缺少密钥时拒绝调用。"""

    def __init__(
        self,
        *,
        api_key: SecretStr | None,
        base_url: str = DEFAULT_DEEPSEEK_BASE_URL,
        model: str = DEEPSEEK_MODEL,
        timeout_seconds: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if api_key is None or api_key.get_secret_value().strip() == "":
            raise RuntimeError("DEEPSEEK_API_KEY is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._client = client

    @property
    def model(self) -> str:
        """模型名。Trace 只记录这个名字，不记录密钥。"""

        return self._model

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float,
    ) -> str:
        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if self._client is None:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                return await self._complete(client, messages, temperature=temperature)
        return await self._complete(self._client, messages, temperature=temperature)

    async def _complete(
        self,
        client: httpx.AsyncClient,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float,
    ) -> str:
        payload = {
            "model": self._model,
            "messages": [dict(message) for message in messages],
            "temperature": temperature,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
        response = await client.post(
            f"{self._base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"model gateway failed with status {response.status_code}")
        body = response.json()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("model gateway returned an unexpected payload") from exc
        if not isinstance(content, str) or content.strip() == "":
            raise RuntimeError("model gateway returned an empty completion")
        return content
