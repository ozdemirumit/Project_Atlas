from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationReceipt,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageInstallationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-installation-input.v1", pattern=STABLE_ID
    )
    source_registration_record_id: str = Field(pattern=STABLE_ID)
    source_registration_record_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    installation_policy_id: str = Field(pattern=STABLE_ID)
    installation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_installation_grants_no_instance_or_runtime_authority: bool


class ConnectorPackageInstallationEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    installer_profile_id: str
    installation_store_profile_id: str
    artifact_reference_schema: str
    package_digest: str
    package_size_bytes: int
    stored_at: datetime


class ConnectorPackageInstallationReceiptData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    schema_version: str
    version: int
    source_registration_record_id: str
    source_registration_record_digest: str
    source_publication_receipt_id: str
    source_publication_receipt_digest: str
    source_signing_receipt_id: str
    source_signing_receipt_digest: str
    source_approval_request_id: str
    source_approval_request_digest: str
    source_final_validation_id: str
    source_final_validation_digest: str
    source_acquisition_id: str
    source_acquisition_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    package_size_bytes: int
    publisher_id: str
    connector_id: str
    release_version: str
    provenance_digest: str
    manifest_digest: str
    sdk_profile: str
    registry_profile_id: str
    registration_policy_id: str
    registration_policy_digest: str
    installation_policy_id: str
    installation_policy_digest: str
    installation_policy_version: str
    installation: ConnectorPackageInstallationEvidenceData
    installed_by: str
    purpose: str
    installed_at: datetime
    canonical_digest: str
    package_published: bool
    connector_registered: bool
    package_installed: bool
    eligible_for_instance_governance: bool
    promotion_blocked: bool
    reused: bool
    connector_enabled: bool
    instance_created: bool
    target_configured: bool
    credentials_resolved: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(
        cls, receipt: ConnectorPackageInstallationReceipt
    ) -> ConnectorPackageInstallationReceiptData:
        installation = receipt.installation
        return cls(
            **{
                field: getattr(receipt, field)
                for field in cls.model_fields
                if field not in {"installation"}
            },
            installation=ConnectorPackageInstallationEvidenceData(
                installer_profile_id=installation.installer_profile_id,
                installation_store_profile_id=installation.installation_store_profile_id,
                artifact_reference_schema=installation.artifact_reference_schema,
                package_digest=installation.package_digest,
                package_size_bytes=installation.package_size_bytes,
                stored_at=installation.stored_at,
            ),
        )


class ConnectorPackageInstallationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageInstallationReceiptData
    meta: ResponseMeta
