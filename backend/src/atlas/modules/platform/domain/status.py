from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ComponentState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    name: str
    status: ComponentState
    required: bool
    code: str


@dataclass(frozen=True, slots=True)
class PlatformHealth:
    service_name: str
    service_version: str
    environment: str
    status: ComponentState
    ready: bool
    components: tuple[ComponentHealth, ...]
    warnings: tuple[str, ...]


class HealthProbe(Protocol):
    name: str

    @property
    def required(self) -> bool: ...

    async def check(self) -> ComponentHealth: ...
