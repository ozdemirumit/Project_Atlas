from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.content_policy_scan import ConnectorPackageContentPolicyScan
from atlas.modules.connectors.domain.schema_semantics_validation import (
    ConnectorPackageSchemaSemanticsValidation,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)


class PackageSchemaSemanticsValidationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PackageSchemaSemanticsValidationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageSchemaSemanticsValidation | None: ...

    async def get_by_source_scan(
        self, *, source_content_policy_scan_id: str
    ) -> ConnectorPackageSchemaSemanticsValidation | None: ...

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageSchemaSemanticsValidation | None: ...

    async def add(self, validation: ConnectorPackageSchemaSemanticsValidation) -> bool: ...

    async def close(self) -> None: ...


class SchemaSemanticsContentPolicySource(Protocol):
    async def get_by_id(self, *, scan_id: str) -> ConnectorPackageContentPolicyScan | None: ...


class SchemaSemanticsInventorySource(Protocol):
    async def get_by_id(
        self, *, inventory_id: str
    ) -> ConnectorPackageSupplyChainInventory | None: ...


class SchemaSemanticsAcquisitionSource(Protocol):
    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None: ...


class SchemaSemanticsArchiveSource(Protocol):
    async def read(self, *, package_digest: str, size_bytes: int) -> bytes: ...
