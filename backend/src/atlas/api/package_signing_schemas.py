from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.package_signing import ConnectorPackageSigningReceipt

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageSigningInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-signing-input.v1", pattern=STABLE_ID
    )
    source_attestation_report_id: str = Field(pattern=STABLE_ID)
    source_attestation_report_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    signing_policy_id: str = Field(pattern=STABLE_ID)
    signing_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_signing_grants_no_runtime_authority: bool


class ConnectorPackageSigningEnvelopeData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    envelope_id: str
    schema_version: str
    version: int
    source_attestation_report_id: str
    source_attestation_report_digest: str
    source_approval_request_id: str
    source_approval_request_digest: str
    source_approval_decision_id: str
    source_approval_decision_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    publisher_id: str
    connector_id: str
    release_version: str
    provenance_digest: str
    publisher_claim_id: str
    publisher_claim_digest: str
    attestation_policy_id: str
    attestation_policy_digest: str
    signing_policy_id: str
    signing_policy_digest: str
    signing_policy_version: str
    signer_profile_id: str
    requested_by: str
    purpose: str
    created_at: datetime
    canonical_digest: str


class ConnectorPackageSignatureData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    signer_profile_id: str
    signer_workload_id: str
    key_id: str
    algorithm: str
    envelope_digest: str
    signature_digest: str
    issued_at: datetime
    expires_at: datetime
    signature_verified: bool


class ConnectorPackageSigningReceiptData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    receipt_id: str
    schema_version: str
    version: int
    envelope: ConnectorPackageSigningEnvelopeData
    signature: ConnectorPackageSignatureData
    organization_id: str
    environment_id: str
    requested_by: str
    signing_policy_id: str
    signing_policy_digest: str
    signed_at: datetime
    canonical_digest: str
    publisher_attested: bool
    package_signed: bool
    eligible_for_registry_governance: bool
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
        cls, receipt: ConnectorPackageSigningReceipt
    ) -> ConnectorPackageSigningReceiptData:
        return cls.model_validate(receipt)


class ConnectorPackageSigningResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageSigningReceiptData
    meta: ResponseMeta
