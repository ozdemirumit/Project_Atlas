from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageSupplyChainInventoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-supply-chain-inventory-request.v1", pattern=STABLE_ID
    )
    source_validation_id: str = Field(pattern=STABLE_ID)
    source_validation_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    inventory_profile: str = Field(
        default="atlas.connector-supply-chain-inventory.python312.v1", pattern=STABLE_ID
    )
    acknowledged_untrusted_package_content: bool


class PackageFileEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    relative_path: str
    digest: str
    size_bytes: int
    content_class: str


class PackageDependencyEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    name: str
    version_constraint: str
    kind: str
    source_path: str


class PackageInventoryCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    state: str
    severity: str
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str


class ConnectorPackageSupplyChainInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    inventory_id: str
    schema_version: str
    version: int
    lifecycle: str
    outcome: str
    source_validation_id: str
    source_validation_digest: str
    source_acquisition_id: str
    source_acquisition_digest: str
    source_handoff_id: str
    source_project_id: str
    source_acquired_by: str
    source_validated_by: str
    source_custodied_by: str
    source_domain_reviewed_by: str
    source_security_reviewed_by: str
    source_lab_operated_by: str
    organization_id: str
    environment_id: str
    inventoried_by: str
    inventory_profile: str
    inspector_version: str
    package_digest: str
    package_size_bytes: int
    files: tuple[PackageFileEvidenceData, ...]
    dependencies: tuple[PackageDependencyEvidenceData, ...]
    inventory_digest: str
    dependency_set_digest: str
    runtime_dependency_count: int
    build_dependency_count: int
    dependency_lock_present: bool
    checks: tuple[PackageInventoryCheckData, ...]
    limitations: tuple[str, ...]
    canonical_digest: str
    inventoried_at: datetime
    content_inventory_completed: bool
    dependency_inventory_completed: bool
    vulnerability_scan_completed: bool
    malware_scan_completed: bool
    secret_content_scan_completed: bool
    prohibited_content_scan_completed: bool
    license_scan_completed: bool
    static_code_validation_completed: bool
    contract_validation_completed: bool
    runner_validation_completed: bool
    lab_validation_completed: bool
    package_signed: bool
    publisher_attested: bool
    connector_rejected: bool
    connector_registered: bool
    connector_approved: bool
    connector_installed: bool
    connector_enabled: bool
    target_configured: bool
    credentials_resolved: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, inventory: ConnectorPackageSupplyChainInventory
    ) -> ConnectorPackageSupplyChainInventoryData:
        return cls.model_validate(inventory)


class ConnectorPackageSupplyChainInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageSupplyChainInventoryData
    meta: ResponseMeta
