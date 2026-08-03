from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from atlas.modules.connectors.domain.models import (
    ConnectorHealth,
    ConnectorInstance,
    RegisteredPackage,
)


@dataclass(frozen=True, slots=True)
class ConnectorSelfTestResult:
    health: ConnectorHealth
    checked_at: datetime
    code: str

    def __post_init__(self) -> None:
        if self.checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")

    @property
    def passed(self) -> bool:
        return self.health is ConnectorHealth.HEALTHY


class ConnectorSelfTester(Protocol):
    async def self_test(self, instance: ConnectorInstance) -> ConnectorSelfTestResult: ...


class ConnectorRegistryRepository(Protocol):
    async def get_package(
        self, package_id: str, package_version: str
    ) -> RegisteredPackage | None: ...

    async def add_package(self, package: RegisteredPackage) -> None: ...

    async def list_packages(self) -> tuple[RegisteredPackage, ...]: ...

    async def get_instance(self, instance_id: str) -> ConnectorInstance | None: ...

    async def add_instance(self, instance: ConnectorInstance) -> None: ...

    async def replace_instance(self, instance: ConnectorInstance) -> None: ...

    async def list_instances(self) -> tuple[ConnectorInstance, ...]: ...
