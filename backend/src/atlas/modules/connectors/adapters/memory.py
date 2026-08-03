from __future__ import annotations

import asyncio

from atlas.modules.connectors.application.registry import ConnectorRegistryError
from atlas.modules.connectors.domain.models import ConnectorInstance, RegisteredPackage


class InMemoryConnectorRegistryRepository:
    def __init__(self) -> None:
        self._packages: dict[tuple[str, str], RegisteredPackage] = {}
        self._instances: dict[str, ConnectorInstance] = {}
        self._lock = asyncio.Lock()

    async def get_package(self, package_id: str, package_version: str) -> RegisteredPackage | None:
        return self._packages.get((package_id, package_version))

    async def add_package(self, package: RegisteredPackage) -> None:
        key = (package.manifest.package_id, package.manifest.package_version)
        async with self._lock:
            if key in self._packages:
                raise ConnectorRegistryError(
                    "package_version_conflict", "The connector package version already exists."
                )
            self._packages[key] = package

    async def list_packages(self) -> tuple[RegisteredPackage, ...]:
        return tuple(
            sorted(
                self._packages.values(),
                key=lambda item: (item.manifest.package_id, item.manifest.package_version),
            )
        )

    async def get_instance(self, instance_id: str) -> ConnectorInstance | None:
        return self._instances.get(instance_id)

    async def add_instance(self, instance: ConnectorInstance) -> None:
        async with self._lock:
            if instance.instance_id in self._instances:
                raise ConnectorRegistryError(
                    "instance_conflict", "The connector instance identifier already exists."
                )
            self._instances[instance.instance_id] = instance

    async def replace_instance(self, instance: ConnectorInstance) -> None:
        async with self._lock:
            if instance.instance_id not in self._instances:
                raise ConnectorRegistryError(
                    "instance_not_found", "Connector instance was not found."
                )
            self._instances[instance.instance_id] = instance

    async def list_instances(self) -> tuple[ConnectorInstance, ...]:
        return tuple(sorted(self._instances.values(), key=lambda item: item.instance_id))
