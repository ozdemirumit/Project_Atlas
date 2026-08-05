from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.license_analysis import (
    ConnectorPackageLicenseAnalysis,
    LicensePolicySnapshot,
)
from atlas.modules.connectors.domain.malware_analysis import ConnectorPackageMalwareAnalysis
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)


class PackageLicenseAnalysisError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PackageLicenseAnalysisRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, analysis_id: str) -> ConnectorPackageLicenseAnalysis | None: ...

    async def get_by_source_analysis(
        self, *, source_malware_analysis_id: str
    ) -> ConnectorPackageLicenseAnalysis | None: ...

    async def get_by_create_key(
        self, *, analyzed_by: str, idempotency_key: str
    ) -> ConnectorPackageLicenseAnalysis | None: ...

    async def add(self, analysis: ConnectorPackageLicenseAnalysis) -> bool: ...

    async def close(self) -> None: ...


class LicenseMalwareSource(Protocol):
    async def get_by_id(self, *, analysis_id: str) -> ConnectorPackageMalwareAnalysis | None: ...


class LicenseInventorySource(Protocol):
    async def get_by_id(
        self, *, inventory_id: str
    ) -> ConnectorPackageSupplyChainInventory | None: ...


class LicenseAcquisitionSource(Protocol):
    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None: ...


class LicenseArchiveSource(Protocol):
    async def read(self, *, package_digest: str, size_bytes: int) -> bytes: ...


class LicensePolicySnapshotProvider(Protocol):
    async def current(
        self, *, organization_id: str, environment_id: str
    ) -> LicensePolicySnapshot: ...
