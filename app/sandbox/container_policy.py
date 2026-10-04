"""沙箱容器的资源和网络策略。Benchmark 并发保持为 1。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SANDBOX_CPU = 2.0
SANDBOX_MEMORY = "2G"
BENCHMARK_CONCURRENCY = 1
_FORBIDDEN_MARKERS = (
    "docker.sock",
    "/.ssh",
    "/root",
    "/etc/shadow",
    "credentials",
)


def sandbox_violations(compose: Mapping[str, Any]) -> list[str]:
    """返回 compose 文档相对沙箱默认配置的偏差。空列表表示符合策略。"""

    services = compose.get("services")
    networks = compose.get("networks")
    if not isinstance(services, Mapping) or not isinstance(networks, Mapping):
        return ["compose 缺少 services 或 networks"]
    violations: list[str] = []
    for name, service in services.items():
        if not isinstance(service, Mapping):
            violations.append(f"{name} 服务定义无效")
            continue
        violations.extend(_service_violations(str(name), service))
    violations.extend(_role_violations(services, networks))
    return violations


def _service_violations(name: str, service: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    if service.get("volumes"):
        violations.append(f"{name} 不能挂载卷")
    if service.get("privileged") is True:
        violations.append(f"{name} 不能使用 privileged")
    if service.get("pid") == "host" or service.get("network_mode") == "host":
        violations.append(f"{name} 不能共享宿主命名空间")
    if _contains_marker(service, _FORBIDDEN_MARKERS):
        violations.append(f"{name} 包含危险挂载或凭据路径")
    options = service.get("security_opt")
    if not isinstance(options, list) or "no-new-privileges:true" not in options:
        violations.append(f"{name} 必须设置 no-new-privileges")
    return violations


def _role_violations(services: Mapping[str, Any], networks: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    db = services.get("db")
    api = services.get("api")
    if not isinstance(db, Mapping) or not isinstance(api, Mapping):
        return ["compose 必须同时定义 db 和 api"]
    image = db.get("image")
    if not isinstance(image, str) or "pg16" not in image:
        violations.append("db 必须使用 PostgreSQL 16")
    violations.extend(_resource_violations("db", db))
    violations.extend(_resource_violations("api", api))
    db_networks = _service_networks(db)
    api_networks = _service_networks(api)
    if not db_networks or any(not _is_internal(networks, name) for name in db_networks):
        violations.append("db 只能接入 internal 网络")
    if not any(_is_internal(networks, name) for name in api_networks):
        violations.append("api 必须能通过 internal 网络访问 db")
    if not any(not _is_internal(networks, name) for name in api_networks):
        violations.append("api 必须保留模型出站网络")
    for port in _ports(db):
        if not _localhost_binding(port):
            violations.append("db 端口只能绑定 127.0.0.1")
    return violations


def _resource_violations(name: str, service: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    if _cpu_limit(service) != SANDBOX_CPU:
        violations.append(f"{name} 的 CPU 限制必须是 2")
    if _memory_limit(service) != SANDBOX_MEMORY:
        violations.append(f"{name} 的内存限制必须是 2G")
    return violations


def _cpu_limit(service: Mapping[str, Any]) -> float | None:
    limits = _limits(service)
    if limits is None or "cpus" not in limits:
        return None
    cpus = limits["cpus"]
    if isinstance(cpus, int | float | str):
        return float(cpus)
    return None


def _memory_limit(service: Mapping[str, Any]) -> str | None:
    limits = _limits(service)
    if limits is None:
        return None
    memory = limits.get("memory")
    if isinstance(memory, str):
        return memory.upper()
    return None


def _limits(service: Mapping[str, Any]) -> Mapping[str, Any] | None:
    deploy = service.get("deploy")
    if not isinstance(deploy, Mapping):
        return None
    resources = deploy.get("resources")
    if not isinstance(resources, Mapping):
        return None
    limits = resources.get("limits")
    if not isinstance(limits, Mapping):
        return None
    return limits


def _service_networks(service: Mapping[str, Any]) -> list[str]:
    raw = service.get("networks")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str)]
    if isinstance(raw, Mapping):
        return [str(name) for name in raw]
    return []


def _is_internal(networks: Mapping[str, Any], name: str) -> bool:
    spec = networks.get(name)
    return isinstance(spec, Mapping) and spec.get("internal") is True


def _ports(service: Mapping[str, Any]) -> list[object]:
    raw = service.get("ports")
    if isinstance(raw, list):
        return list(raw)
    return []


def _localhost_binding(port: object) -> bool:
    if isinstance(port, str):
        return port.startswith("127.0.0.1:")
    if isinstance(port, Mapping):
        return port.get("host_ip") == "127.0.0.1"
    return False


def _contains_marker(value: object, markers: tuple[str, ...]) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return any(marker in lowered for marker in markers)
    if isinstance(value, Mapping):
        return any(_contains_marker(item, markers) for item in value.values())
    if isinstance(value, list):
        return any(_contains_marker(item, markers) for item in value)
    return False
