"""P0 全量模型评测前探测 DeepSeek 网关（避免 402 下空跑长脚本）。"""

from __future__ import annotations

import asyncio
import sys

from app.config.llm_settings import get_llm_settings
from app.llm.gateway import DeepSeekGateway


async def probe_llm_gateway(*, timeout_seconds: float = 30.0) -> None:
    settings = get_llm_settings()
    if settings.deepseek_api_key is None:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    gateway = DeepSeekGateway(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout_seconds=timeout_seconds,
    )
    await gateway.complete([{"role": "user", "content": "Reply with exactly: OK"}], temperature=0)


def main() -> None:
    try:
        asyncio.run(probe_llm_gateway())
        print("llm_preflight=ready")
    except RuntimeError as exc:
        message = str(exc)
        print(message, file=sys.stderr)
        if "402" in message:
            print(
                "P0 full eval blocked: use ./scripts/print_external_p0_status.sh "
                "and --replay-run until billing is restored.",
                file=sys.stderr,
            )
            print(
                "P0/P1 ops: docs/external_gold_p0_runbook.md; "
                "./scripts/p0_post_billing_acceptance.sh --gates-only",
                file=sys.stderr,
            )
            raise SystemExit(2) from exc
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
