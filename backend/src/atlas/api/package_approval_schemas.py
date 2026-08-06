from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.package_approval import ConnectorPackageApprovalRecord

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageApprovalRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-approval-request-input.v1", pattern=STABLE_ID
    )
    source_final_validation_id: str = Field(pattern=STABLE_ID)
    source_final_validation_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    approval_policy_id: str = Field(pattern=STABLE_ID)
    approval_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_request_is_not_approval: bool


class ConnectorPackageApprovalDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-approval-decision-input.v1", pattern=STABLE_ID
    )
    expected_request_version: int = Field(ge=1)
    request_digest: str = Field(pattern=DIGEST)
    outcome: str = Field(pattern=r"^(approve|reject|needs_evidence|defer)$")
    rationale: str = Field(min_length=1, max_length=4000)
    acknowledged_decision_grants_no_runtime_authority: bool


class ConnectorPackageApprovalRequestData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    request_id: str
    schema_version: str
    version: int
    source_final_validation_id: str
    source_final_validation_digest: str
    source_handoff_id: str
    source_project_id: str
    source_actor_set_digest: str
    organization_id: str
    environment_id: str
    requested_by: str
    purpose: str
    approval_policy_id: str
    approval_policy_digest: str
    approval_policy_version: str
    package_digest: str
    inventory_digest: str
    product_family: str
    observed_product_version: str
    evidence_digest: str
    final_policy_id: str
    final_policy_digest: str
    final_policy_version: str
    stage_count: int
    passed_stage_count: int
    finding_count: int
    limitation_count: int
    blocking_risk_count: int
    created_at: datetime
    expires_at: datetime
    canonical_digest: str
    final_validation_completed: bool
    connector_approved: bool
    connector_rejected: bool
    eligible_for_publisher_governance: bool
    promotion_blocked: bool
    reused: bool


class ConnectorPackageApprovalDecisionData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    decision_id: str
    schema_version: str
    version: int
    request_id: str
    request_version: int
    request_digest: str
    outcome: str
    decided_by: str
    rationale: str
    organization_id: str
    environment_id: str
    source_final_validation_id: str
    source_final_validation_digest: str
    package_digest: str
    approval_policy_id: str
    approval_policy_digest: str
    decided_at: datetime
    canonical_digest: str
    reused: bool


class ConnectorPackageApprovalData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    request: ConnectorPackageApprovalRequestData
    decision: ConnectorPackageApprovalDecisionData | None
    state: str
    approval_valid: bool
    connector_approved: bool
    connector_rejected: bool
    eligible_for_publisher_governance: bool
    promotion_blocked: bool
    package_signed: bool
    publisher_attested: bool
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
    def from_domain(cls, record: ConnectorPackageApprovalRecord) -> ConnectorPackageApprovalData:
        return cls.model_validate(record)


class ConnectorPackageApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageApprovalData
    meta: ResponseMeta
