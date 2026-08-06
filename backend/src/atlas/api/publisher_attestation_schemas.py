from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.publisher_attestation import (
    ConnectorPublisherAttestationReport,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPublisherAttestationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-publisher-attestation-input.v1", pattern=STABLE_ID
    )
    source_approval_request_id: str = Field(pattern=STABLE_ID)
    source_approval_request_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    publisher_claim_id: str = Field(pattern=STABLE_ID)
    publisher_claim_digest: str = Field(pattern=DIGEST)
    attestation_policy_id: str = Field(pattern=STABLE_ID)
    attestation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_attestation_grants_no_lifecycle_authority: bool


class ConnectorPublisherAttestationData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    report_id: str
    schema_version: str
    version: int
    source_approval_request_id: str
    source_approval_request_digest: str
    source_approval_decision_id: str
    source_approval_decision_digest: str
    organization_id: str
    environment_id: str
    verified_by: str
    purpose: str
    package_digest: str
    publisher_claim_id: str
    publisher_claim_digest: str
    publisher_id: str
    publisher_display_name: str
    connector_id: str
    release_version: str
    provenance_digest: str
    support_contact_ref: str
    support_expires_at: datetime
    claim_issued_by: str
    attestation_policy_id: str
    attestation_policy_digest: str
    attestation_policy_version: str
    check_codes: tuple[str, ...]
    outcome: str
    reason_codes: tuple[str, ...]
    verified_at: datetime
    canonical_digest: str
    publisher_attested: bool
    eligible_for_package_signing_governance: bool
    promotion_blocked: bool
    reused: bool
    package_signed: bool
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
        cls, report: ConnectorPublisherAttestationReport
    ) -> ConnectorPublisherAttestationData:
        return cls.model_validate(report)


class ConnectorPublisherAttestationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPublisherAttestationData
    meta: ResponseMeta
