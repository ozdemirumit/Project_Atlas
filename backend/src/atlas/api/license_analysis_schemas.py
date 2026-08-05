from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.license_analysis import ConnectorPackageLicenseAnalysis

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageLicenseAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-license-analysis-request.v1",
        pattern=STABLE_ID,
    )
    source_malware_analysis_id: str = Field(pattern=STABLE_ID)
    source_malware_analysis_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    analysis_profile: str = Field(
        default="atlas.connector-license-policy.python312.v1", pattern=STABLE_ID
    )
    acknowledged_policy_not_legal_advice: bool


class LicensePolicySnapshotSummaryData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    snapshot_id: str
    snapshot_version: str
    snapshot_digest: str
    signing_key_id: str
    issued_at: datetime
    expires_at: datetime
    analysis_profile: str
    analyzer_version: str
    record_count: int
    package_coverage_complete: bool
    source_coverage_complete: bool
    dependency_coverage_complete: bool
    obligation_coverage_complete: bool
    fresh: bool


class LicenseSubjectSummaryData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    package_subject_count: int
    source_subject_count: int
    runtime_dependency_count: int
    transitive_dependency_count: int
    build_dependency_count: int
    scanned_subject_count: int
    permitted_count: int
    review_required_count: int
    prohibited_count: int
    unknown_count: int
    obligation_count: int
    unsatisfied_obligation_count: int
    subject_set_digest: str


class LicenseFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    rule_id: str
    category: str
    severity: str
    subject_scope: str
    subject_fingerprint: str
    disposition: str
    obligations: tuple[str, ...]
    summary: str
    remediation: str


class LicenseCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    state: str
    severity: str
    summary: str
    remediation: str


class ConnectorPackageLicenseAnalysisData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    analysis_id: str
    schema_version: str
    version: int
    lifecycle: str
    outcome: str
    source_malware_analysis_id: str
    source_malware_analysis_digest: str
    source_vulnerability_analysis_id: str
    source_vulnerability_analysis_digest: str
    source_static_dependency_analysis_id: str
    source_static_dependency_analysis_digest: str
    source_authority_behavior_validation_id: str
    source_schema_semantics_validation_id: str
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
    source_authority_validated_by: str
    source_static_analyzed_by: str
    source_vulnerability_analyzed_by: str
    source_malware_analyzed_by: str
    source_custodied_by: str
    source_domain_reviewed_by: str
    source_security_reviewed_by: str
    source_lab_operated_by: str
    organization_id: str
    environment_id: str
    analyzed_by: str
    analysis_profile: str
    analyzer_version: str
    package_digest: str
    package_size_bytes: int
    inventory_digest: str
    dependency_set_digest: str
    policy_snapshot: LicensePolicySnapshotSummaryData
    subject_summary: LicenseSubjectSummaryData
    findings: tuple[LicenseFindingData, ...]
    finding_set_digest: str
    analysis_digest: str
    checks: tuple[LicenseCheckData, ...]
    limitations: tuple[str, ...]
    promotion_blocked: bool
    canonical_digest: str
    analyzed_at: datetime
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
        cls, analysis: ConnectorPackageLicenseAnalysis
    ) -> ConnectorPackageLicenseAnalysisData:
        return cls.model_validate(analysis)


class ConnectorPackageLicenseAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageLicenseAnalysisData
    meta: ResponseMeta
