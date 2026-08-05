from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.authority_behavior_validation import (
    ConnectorPackageAuthorityBehaviorValidation,
)
from atlas.modules.connectors.domain.schema_semantics_validation import (
    ConnectorPackageSchemaSemanticsValidation,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)


class PackageAuthorityBehaviorValidationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PackageAuthorityBehaviorValidationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageAuthorityBehaviorValidation | None: ...

    async def get_by_source_validation(
        self, *, source_schema_semantics_validation_id: str
    ) -> ConnectorPackageAuthorityBehaviorValidation | None: ...

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageAuthorityBehaviorValidation | None: ...

    async def add(self, validation: ConnectorPackageAuthorityBehaviorValidation) -> bool: ...

    async def close(self) -> None: ...


class AuthorityBehaviorSchemaSemanticsSource(Protocol):
    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageSchemaSemanticsValidation | None: ...


class AuthorityBehaviorInventorySource(Protocol):
    async def get_by_id(
        self, *, inventory_id: str
    ) -> ConnectorPackageSupplyChainInventory | None: ...


class AuthorityBehaviorAcquisitionSource(Protocol):
    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None: ...


class AuthorityBehaviorArchiveSource(Protocol):
    async def read(self, *, package_digest: str, size_bytes: int) -> bytes: ...
