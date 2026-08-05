from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.contract_validation import ConnectorPackageContractValidation
from atlas.modules.connectors.domain.license_analysis import ConnectorPackageLicenseAnalysis
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)


class PackageContractValidationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PackageContractValidationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageContractValidation | None: ...

    async def get_by_source_analysis(
        self, *, source_license_analysis_id: str
    ) -> ConnectorPackageContractValidation | None: ...

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageContractValidation | None: ...

    async def add(self, validation: ConnectorPackageContractValidation) -> bool: ...

    async def close(self) -> None: ...


class ContractLicenseSource(Protocol):
    async def get_by_id(self, *, analysis_id: str) -> ConnectorPackageLicenseAnalysis | None: ...


class ContractInventorySource(Protocol):
    async def get_by_id(
        self, *, inventory_id: str
    ) -> ConnectorPackageSupplyChainInventory | None: ...


class ContractAcquisitionSource(Protocol):
    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None: ...


class ContractArchiveSource(Protocol):
    async def read(self, *, package_digest: str, size_bytes: int) -> bytes: ...
