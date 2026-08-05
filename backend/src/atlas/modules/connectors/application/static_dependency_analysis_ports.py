from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.authority_behavior_validation import (
    ConnectorPackageAuthorityBehaviorValidation,
)
from atlas.modules.connectors.domain.static_dependency_analysis import (
    ConnectorPackageStaticDependencyAnalysis,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)


class PackageStaticDependencyAnalysisError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PackageStaticDependencyAnalysisRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(
        self, *, analysis_id: str
    ) -> ConnectorPackageStaticDependencyAnalysis | None: ...

    async def get_by_source_validation(
        self, *, source_authority_behavior_validation_id: str
    ) -> ConnectorPackageStaticDependencyAnalysis | None: ...

    async def get_by_create_key(
        self, *, analyzed_by: str, idempotency_key: str
    ) -> ConnectorPackageStaticDependencyAnalysis | None: ...

    async def add(self, analysis: ConnectorPackageStaticDependencyAnalysis) -> bool: ...

    async def close(self) -> None: ...


class StaticDependencyAuthorityBehaviorSource(Protocol):
    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageAuthorityBehaviorValidation | None: ...


class StaticDependencyInventorySource(Protocol):
    async def get_by_id(
        self, *, inventory_id: str
    ) -> ConnectorPackageSupplyChainInventory | None: ...


class StaticDependencyAcquisitionSource(Protocol):
    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None: ...


class StaticDependencyArchiveSource(Protocol):
    async def read(self, *, package_digest: str, size_bytes: int) -> bytes: ...
