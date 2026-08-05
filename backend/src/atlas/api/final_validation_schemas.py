from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.final_validation import ConnectorPackageFinalValidation

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageFinalValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-final-validation-request.v1", pattern=STABLE_ID
    )
    source_lab_self_test_id: str = Field(pattern=STABLE_ID)
    source_lab_self_test_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    policy_id: str = Field(pattern=STABLE_ID)
    policy_digest: str = Field(pattern=DIGEST)
    acknowledged_evidence_only_no_approval: bool


class FinalStageEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    stage_code: str
    evidence_id: str
    evidence_digest: str
    observed_at: datetime
    outcome: str
    promotion_blocked: bool
    finding_count: int
    limitation_count: int


class FinalRiskSummaryData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    source_stage: str
    source_evidence_id: str
    source_evidence_digest: str
    classification: str
    severity: str
    blocking: bool
    occurrence_count: int
    next_step: str


class FinalValidationCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    state: str
    severity: str
    summary: str
    remediation: str


class ConnectorPackageFinalValidationData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    validation_id: str
    schema_version: str
    version: int
    outcome: str
    source_lab_self_test_id: str
    source_lab_self_test_digest: str
    source_handoff_id: str
    source_handoff_digest: str
    source_project_id: str
    source_actor_set_digest: str
    organization_id: str
    environment_id: str
    validated_by: str
    policy_id: str
    policy_digest: str
    policy_version: str
    package_digest: str
    inventory_digest: str
    product_family: str
    observed_product_version: str
    capability_count: int
    tested_capability_count: int
    stage_evidence: tuple[FinalStageEvidenceData, ...]
    stage_count: int
    passed_stage_count: int
    finding_count: int
    limitation_count: int
    blocking_risk_count: int
    risks: tuple[FinalRiskSummaryData, ...]
    checks: tuple[FinalValidationCheckData, ...]
    limitations: tuple[str, ...]
    eligible_for_human_approval: bool
    promotion_blocked: bool
    evidence_digest: str
    canonical_digest: str
    validated_at: datetime
    secret_content_scan_completed: bool
    prohibited_content_scan_completed: bool
    schema_semantic_validation_completed: bool
    permission_behavior_validation_completed: bool
    static_code_validation_completed: bool
    vulnerability_scan_completed: bool
    malware_scan_completed: bool
    license_scan_completed: bool
    contract_validation_completed: bool
    runner_validation_completed: bool
    lab_validation_completed: bool
    final_validation_completed: bool
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
        cls, validation: ConnectorPackageFinalValidation
    ) -> ConnectorPackageFinalValidationData:
        return cls.model_validate(validation)


class ConnectorPackageFinalValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageFinalValidationData
    meta: ResponseMeta
