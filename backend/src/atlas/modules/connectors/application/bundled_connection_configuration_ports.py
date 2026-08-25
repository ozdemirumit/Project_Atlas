from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)


class BundledConnectionConfigurationError(RuntimeError):
    pass


class BundledConnectionConfigurationRepository(Protocol):
    async def get(
        self, *, organization_id: str, environment_id: str, instance_id: str
    ) -> BundledConnectionConfiguration | None: ...

    async def put(self, record: BundledConnectionConfiguration) -> None: ...
