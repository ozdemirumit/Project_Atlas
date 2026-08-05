from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.authority_behavior_validation import (
    ConnectorPackageAuthorityBehaviorValidation,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageAuthorityBehaviorValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-authority-behavior-validation-request.v1",
        pattern=STABLE_ID,
    )
    source_schema_semantics_validation_id: str = Field(pattern=STABLE_ID)
    source_schema_semantics_validation_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    validation_profile: str = Field(
        default="atlas.connector-authority-behavior.python312.v1", pattern=STABLE_ID
    )
    acknowledged_static_analysis_limitations: bool


class CapabilityBehaviorSummaryData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    capability_id: str
    declared_class: str
    required_permission: str
    module_path: str
    source_digest: str
    observed_categories: tuple[str, ...]
    network_call_count: int
    mutation_call_count: int
    declaration_matches: bool
    permission_matches: bool
    behavior_compatible: bool
    statically_resolved: bool


class AuthorityBehaviorFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    rule_code: str
    category: str
    severity: str
    relative_path: str
    line_number: int
    evidence_fingerprint: str
    summary: str
    remediation: str


class AuthorityBehaviorCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    state: str
    severity: str
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str


class ConnectorPackageAuthorityBehaviorValidationData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    validation_id: str
    schema_version: str
    version: int
    lifecycle: str
    outcome: str
    source_schema_semantics_validation_id: str
    source_schema_semantics_validation_digest: str
    source_content_policy_scan_id: str
    source_inventory_id: str
    source_validation_id: str
    source_acquisition_id: str
    source_handoff_id: str
    source_project_id: str
    source_acquired_by: str
    source_manifest_validated_by: str
    source_inventoried_by: str
    source_content_scanned_by: str
    source_schema_validated_by: str
    source_custodied_by: str
    source_domain_reviewed_by: str
    source_security_reviewed_by: str
    source_lab_operated_by: str
    organization_id: str
    environment_id: str
    validated_by: str
    validation_profile: str
    analyzer_version: str
    package_digest: str
    package_size_bytes: int
    inventory_digest: str
    semantic_validation_digest: str
    capabilities: tuple[CapabilityBehaviorSummaryData, ...]
    capability_set_digest: str
    findings: tuple[AuthorityBehaviorFindingData, ...]
    finding_set_digest: str
    behavior_validation_digest: str
    checks: tuple[AuthorityBehaviorCheckData, ...]
    limitations: tuple[str, ...]
    promotion_blocked: bool
    canonical_digest: str
    validated_at: datetime
    secret_content_scan_completed: bool
    prohibited_content_scan_completed: bool
    schema_semantic_validation_completed: bool
    permission_behavior_validation_completed: bool
    vulnerability_scan_completed: bool
    malware_scan_completed: bool
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
        cls, validation: ConnectorPackageAuthorityBehaviorValidation
    ) -> ConnectorPackageAuthorityBehaviorValidationData:
        return cls.model_validate(validation)


class ConnectorPackageAuthorityBehaviorValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageAuthorityBehaviorValidationData
    meta: ResponseMeta
