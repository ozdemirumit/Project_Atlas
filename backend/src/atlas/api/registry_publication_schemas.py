from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationReceipt,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorRegistryPublicationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-registry-publication-input.v1", pattern=STABLE_ID
    )
    source_signing_receipt_id: str = Field(pattern=STABLE_ID)
    source_signing_receipt_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    publication_policy_id: str = Field(pattern=STABLE_ID)
    publication_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_publication_grants_no_runtime_authority: bool


class ConnectorPackageSignatureVerificationData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    verifier_profile_id: str
    verifier_workload_id: str
    key_id: str
    algorithm: str
    envelope_digest: str
    signature_digest: str
    verified_at: datetime
    signature_valid: bool


class ConnectorInternalRegistryPublicationData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    registry_profile_id: str
    publisher_workload_id: str
    artifact_reference_schema: str
    package_digest: str
    package_size_bytes: int
    source_signing_receipt_digest: str
    publication_digest: str
    published_at: datetime
    integrity_verified: bool
    reused: bool


class ConnectorRegistryPublicationReceiptData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    receipt_id: str
    schema_version: str
    version: int
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
    publication_policy_id: str
    publication_policy_digest: str
    publication_policy_version: str
    verification: ConnectorPackageSignatureVerificationData
    publication: ConnectorInternalRegistryPublicationData
    requested_by: str
    purpose: str
    published_at: datetime
    canonical_digest: str
    publisher_attested: bool
    package_signed: bool
    package_published: bool
    eligible_for_registration_governance: bool
    promotion_blocked: bool
    reused: bool
    connector_registered: bool
    connector_installed: bool
    connector_enabled: bool
    target_configured: bool
    credentials_resolved: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(
        cls, receipt: ConnectorInternalRegistryPublicationReceipt
    ) -> ConnectorRegistryPublicationReceiptData:
        return cls.model_validate(receipt)


class ConnectorRegistryPublicationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorRegistryPublicationReceiptData
    meta: ResponseMeta
