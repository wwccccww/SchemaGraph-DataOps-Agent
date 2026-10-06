"""LLM preflight 在 402 时以 exit 2 失败。"""

from __future__ import annotations

import httpx
import pytest
from app.evaluation import llm_preflight
from pydantic import SecretStr


@pytest.mark.asyncio
async def test_probe_raises_on_402() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": "payment required"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        from app.llm.gateway import DeepSeekGateway

        gateway = DeepSeekGateway(api_key=SecretStr("test-key"), client=client)
        with pytest.raises(RuntimeError, match="402"):
            await gateway.complete([{"role": "user", "content": "ping"}], temperature=0)


def test_main_exits_0_and_prints_ready_on_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def ok_probe() -> None:
        return None

    monkeypatch.setattr(llm_preflight, "probe_llm_gateway", ok_probe)
    llm_preflight.main()
    assert "llm_preflight=ready" in capsys.readouterr().out


def test_main_exits_2_on_402(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fail_probe() -> None:
        raise RuntimeError("model gateway failed with status 402 (Payment Required)")

    monkeypatch.setattr(llm_preflight, "probe_llm_gateway", fail_probe)
    with pytest.raises(SystemExit) as exc:
        llm_preflight.main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "external_gold_p0_runbook.md" in err
    assert "--gates-only" in err
