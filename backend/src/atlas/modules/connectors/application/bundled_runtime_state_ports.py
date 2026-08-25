from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.bundled_runtime_state import (
    BundledConnectorRuntimeState,
)


class BundledConnectorRuntimeStateError(RuntimeError):
    pass


class BundledConnectorRuntimeStateRepository(Protocol):
    async def get(
        self, *, organization_id: str, environment_id: str, instance_id: str
    ) -> BundledConnectorRuntimeState | None: ...

    async def put(self, record: BundledConnectorRuntimeState, *, expected_version: int) -> bool: ...

    async def clear(
        self, *, organization_id: str, environment_id: str, instance_id: str
    ) -> None: ...
