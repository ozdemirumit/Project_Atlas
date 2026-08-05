from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.static_dependency_analysis import (
    ConnectorPackageStaticDependencyAnalysis,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageStaticDependencyAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-static-dependency-analysis-request.v1",
        pattern=STABLE_ID,
    )
    source_authority_behavior_validation_id: str = Field(pattern=STABLE_ID)
    source_authority_behavior_validation_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    analysis_profile: str = Field(
        default="atlas.connector-static-dependency.python312.v1", pattern=STABLE_ID
    )
    acknowledged_offline_static_dependency_limitations: bool


class StaticSourceSummaryData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    source_file_count: int
    module_count: int
    function_count: int
    import_count: int
    external_import_count: int
    unresolved_import_count: int
    source_set_digest: str


class DependencyHygieneSummaryData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    runtime_dependency_count: int
    build_dependency_count: int
    imported_dependency_count: int
    dependency_lock_present: bool
    dependency_lock_required: bool
    dependency_set_digest: str
    metadata_consistent: bool
    imports_reconciled: bool
    deterministic_constraints: bool


class StaticDependencyFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    rule_code: str
    category: str
    severity: str
    relative_path: str
    line_number: int
    evidence_fingerprint: str
    summary: str
    remediation: str


class StaticDependencyCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    state: str
    severity: str
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str


class ConnectorPackageStaticDependencyAnalysisData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    analysis_id: str
    schema_version: str
    version: int
    lifecycle: str
    outcome: str
    source_authority_behavior_validation_id: str
    source_authority_behavior_validation_digest: str
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
    source_summary: StaticSourceSummaryData
    dependency_summary: DependencyHygieneSummaryData
    findings: tuple[StaticDependencyFindingData, ...]
    finding_set_digest: str
    analysis_digest: str
    checks: tuple[StaticDependencyCheckData, ...]
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
        cls, analysis: ConnectorPackageStaticDependencyAnalysis
    ) -> ConnectorPackageStaticDependencyAnalysisData:
        return cls.model_validate(analysis)


class ConnectorPackageStaticDependencyAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageStaticDependencyAnalysisData
    meta: ResponseMeta
