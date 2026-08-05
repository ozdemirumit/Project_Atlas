from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.authority_behavior_validation import (
    ConnectorPackageAuthorityBehaviorValidation,
)
from atlas.modules.connectors.domain.content_policy_scan import ConnectorPackageContentPolicyScan
from atlas.modules.connectors.domain.contract_validation import ConnectorPackageContractValidation
from atlas.modules.connectors.domain.final_validation import (
    ConnectorPackageFinalValidation,
    FinalValidationPolicySnapshot,
)
from atlas.modules.connectors.domain.lab_self_test import ConnectorPackageLabSelfTest
from atlas.modules.connectors.domain.license_analysis import ConnectorPackageLicenseAnalysis
from atlas.modules.connectors.domain.malware_analysis import ConnectorPackageMalwareAnalysis
from atlas.modules.connectors.domain.runner_validation import ConnectorPackageRunnerValidation
from atlas.modules.connectors.domain.schema_semantics_validation import (
    ConnectorPackageSchemaSemanticsValidation,
)
from atlas.modules.connectors.domain.static_dependency_analysis import (
    ConnectorPackageStaticDependencyAnalysis,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)
from atlas.modules.connectors.domain.validation_intake import ConnectorPackageValidation
from atlas.modules.connectors.domain.vulnerability_analysis import (
    ConnectorPackageVulnerabilityAnalysis,
)
from atlas.modules.mcp_builder.domain.candidate_handoff import McpBuilderCandidateHandoff


class PackageFinalValidationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class FinalValidationPolicySource(Protocol):
    async def get_by_id(self, *, policy_id: str) -> FinalValidationPolicySnapshot | None: ...


class FinalHandoffSource(Protocol):
    async def get_by_id(self, *, handoff_id: str) -> McpBuilderCandidateHandoff | None: ...


class FinalAcquisitionSource(Protocol):
    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None: ...


class FinalPackageValidationSource(Protocol):
    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageValidation | None: ...


class FinalInventorySource(Protocol):
    async def get_by_id(
        self, *, inventory_id: str
    ) -> ConnectorPackageSupplyChainInventory | None: ...


class FinalContentPolicySource(Protocol):
    async def get_by_id(self, *, scan_id: str) -> ConnectorPackageContentPolicyScan | None: ...


class FinalSchemaSemanticsSource(Protocol):
    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageSchemaSemanticsValidation | None: ...


class FinalAuthorityBehaviorSource(Protocol):
    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageAuthorityBehaviorValidation | None: ...


class FinalStaticDependencySource(Protocol):
    async def get_by_id(
        self, *, analysis_id: str
    ) -> ConnectorPackageStaticDependencyAnalysis | None: ...


class FinalVulnerabilitySource(Protocol):
    async def get_by_id(
        self, *, analysis_id: str
    ) -> ConnectorPackageVulnerabilityAnalysis | None: ...


class FinalMalwareSource(Protocol):
    async def get_by_id(self, *, analysis_id: str) -> ConnectorPackageMalwareAnalysis | None: ...


class FinalLicenseSource(Protocol):
    async def get_by_id(self, *, analysis_id: str) -> ConnectorPackageLicenseAnalysis | None: ...


class FinalContractSource(Protocol):
    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageContractValidation | None: ...


class FinalRunnerSource(Protocol):
    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageRunnerValidation | None: ...


class FinalLabSource(Protocol):
    async def get_by_id(self, *, self_test_id: str) -> ConnectorPackageLabSelfTest | None: ...


class PackageFinalValidationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageFinalValidation | None: ...

    async def get_by_source_self_test(
        self, *, source_lab_self_test_id: str
    ) -> ConnectorPackageFinalValidation | None: ...

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageFinalValidation | None: ...

    async def add(self, validation: ConnectorPackageFinalValidation) -> bool: ...

    async def close(self) -> None: ...
