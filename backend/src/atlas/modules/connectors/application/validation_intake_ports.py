from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.validation_intake import ConnectorPackageValidation


class PackageValidationError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PackageValidationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageValidation | None: ...

    async def get_by_acquisition(
        self, *, source_acquisition_id: str
    ) -> ConnectorPackageValidation | None: ...

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageValidation | None: ...

    async def add(self, validation: ConnectorPackageValidation) -> bool: ...

    async def close(self) -> None: ...


class PackageAcquisitionSource(Protocol):
    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None: ...


class AcquiredPackageSource(Protocol):
    async def read(self, *, package_digest: str, size_bytes: int) -> bytes: ...
