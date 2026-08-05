from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageAcquisitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-acquisition-request.v1", pattern=STABLE_ID
    )
    source_handoff_id: str = Field(pattern=STABLE_ID)
    source_handoff_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    acquisition_profile: str = Field(
        default="atlas.connector-acquisition.builder-handoff.v1", pattern=STABLE_ID
    )
    acknowledged_unsigned_unattested_quarantine: bool


class AcquiredCapabilityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    capability_class: str
    required_permission: str
    supported_product_versions: list[str]


class ConnectorPackageAcquisitionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acquisition_id: str
    schema_version: str
    version: int
    state: str
    source_type: str
    source_handoff_id: str
    source_handoff_digest: str
    source_project_id: str
    source_custodied_by: str
    organization_id: str
    environment_id: str
    acquired_by: str
    acquisition_profile: str
    archive_contract_version: str
    package_filename: str
    package_digest: str
    package_size_bytes: int
    publisher_identity: str
    signature_state: str
    attestation_state: str
    capabilities: list[AcquiredCapabilityData]
    limitations: list[str]
    canonical_digest: str
    acquired_at: datetime
    package_acquired: bool
    integrity_verified: bool
    package_signed: bool
    publisher_attested: bool
    registry_validation_completed: bool
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
        cls, acquisition: ConnectorPackageAcquisition
    ) -> ConnectorPackageAcquisitionData:
        return cls(
            acquisition_id=acquisition.acquisition_id,
            schema_version=acquisition.schema_version,
            version=acquisition.version,
            state=acquisition.state.value,
            source_type=acquisition.source_type.value,
            source_handoff_id=acquisition.source_handoff_id,
            source_handoff_digest=acquisition.source_handoff_digest,
            source_project_id=acquisition.source_project_id,
            source_custodied_by=acquisition.source_custodied_by,
            organization_id=acquisition.organization_id,
            environment_id=acquisition.environment_id,
            acquired_by=acquisition.acquired_by,
            acquisition_profile=acquisition.acquisition_profile,
            archive_contract_version=acquisition.archive_contract_version,
            package_filename=acquisition.package_filename,
            package_digest=acquisition.package_digest,
            package_size_bytes=acquisition.package_size_bytes,
            publisher_identity=acquisition.publisher_identity,
            signature_state=acquisition.signature_state.value,
            attestation_state=acquisition.attestation_state.value,
            capabilities=[
                AcquiredCapabilityData(
                    capability_id=item.capability_id,
                    capability_class=item.capability_class,
                    required_permission=item.required_permission,
                    supported_product_versions=list(item.supported_product_versions),
                )
                for item in acquisition.capabilities
            ],
            limitations=list(acquisition.limitations),
            canonical_digest=acquisition.canonical_digest,
            acquired_at=acquisition.acquired_at,
            package_acquired=acquisition.package_acquired,
            integrity_verified=acquisition.integrity_verified,
            package_signed=acquisition.package_signed,
            publisher_attested=acquisition.publisher_attested,
            registry_validation_completed=acquisition.registry_validation_completed,
            connector_registered=acquisition.connector_registered,
            connector_approved=acquisition.connector_approved,
            connector_installed=acquisition.connector_installed,
            connector_enabled=acquisition.connector_enabled,
            target_configured=acquisition.target_configured,
            credentials_resolved=acquisition.credentials_resolved,
            runtime_trust_granted=acquisition.runtime_trust_granted,
            execution_authorized=acquisition.execution_authorized,
            deployment_approved=acquisition.deployment_approved,
            infrastructure_mutation_performed=acquisition.infrastructure_mutation_performed,
            reused=acquisition.reused,
        )


class ConnectorPackageAcquisitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageAcquisitionData
    meta: ResponseMeta
