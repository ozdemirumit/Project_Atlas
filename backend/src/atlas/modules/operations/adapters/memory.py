from __future__ import annotations

import asyncio

from atlas.modules.operations.domain.models import OperationResource

_Key = tuple[str, str, str]


class InMemoryOperationResourceRepository:
    durable = False

    def __init__(self) -> None:
        self._resources: dict[_Key, OperationResource] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(operation_id: str, organization_id: str, environment_id: str) -> _Key:
        return (operation_id, organization_id, environment_id)

    async def get(
        self, *, operation_id: str, organization_id: str, environment_id: str
    ) -> OperationResource | None:
        return self._resources.get(self._key(operation_id, organization_id, environment_id))

    async def add(self, resource: OperationResource) -> bool:
        async with self._lock:
            key = self._key(
                resource.operation_id, resource.organization_id, resource.environment_id
            )
            if key in self._resources:
                return False
            self._resources[key] = resource
            return True

    async def update(self, *, expected: OperationResource, replacement: OperationResource) -> bool:
        async with self._lock:
            key = self._key(
                expected.operation_id, expected.organization_id, expected.environment_id
            )
            if self._resources.get(key) != expected:
                return False
            self._resources[key] = replacement
            return True

    async def close(self) -> None:
        return None
