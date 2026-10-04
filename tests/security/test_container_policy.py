"""Compose 必须符合沙箱的资源、网络和挂载约束。"""

from __future__ import annotations

from pathlib import Path

import yaml
from app.sandbox.container_policy import BENCHMARK_CONCURRENCY, sandbox_violations

_COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def test_benchmark_concurrency_stays_sequential() -> None:
    assert BENCHMARK_CONCURRENCY == 1


def test_compose_matches_the_sandbox_policy() -> None:
    document = yaml.safe_load(_COMPOSE.read_text())

    assert sandbox_violations(document) == []


def test_socket_mounts_and_open_db_networks_are_rejected() -> None:
    document = {
        "services": {
            "db": {
                "image": "postgres:15",
                "privileged": True,
                "volumes": ["/var/run/docker.sock:/var/run/docker.sock"],
                "ports": ["5432:5432"],
                "networks": ["egress"],
                "security_opt": ["no-new-privileges:true"],
            },
            "api": {
                "networks": ["sandbox"],
                "security_opt": ["no-new-privileges:true"],
            },
        },
        "networks": {
            "sandbox": {"driver": "bridge", "internal": True},
            "egress": {"driver": "bridge"},
        },
    }

    violations = sandbox_violations(document)

    assert "db 必须使用 PostgreSQL 16" in violations
    assert "db 不能使用 privileged" in violations
    assert "db 不能挂载卷" in violations
    assert "db 包含危险挂载或凭据路径" in violations
    assert "db 只能接入 internal 网络" in violations
    assert "db 端口只能绑定 127.0.0.1" in violations
    assert "db 的 CPU 限制必须是 2" in violations
    assert "api 的内存限制必须是 2G" in violations
    assert "api 必须保留模型出站网络" in violations
