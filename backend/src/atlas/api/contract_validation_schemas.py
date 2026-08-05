from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.contract_validation import ConnectorPackageContractValidation

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageContractValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-contract-validation-request.v1", pattern=STABLE_ID
    )
    source_license_analysis_id: str = Field(pattern=STABLE_ID)
    source_license_analysis_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    validation_profile: str = Field(
        default="atlas.connector-contract.python312.v1", pattern=STABLE_ID
    )
    acknowledged_static_contract_only: bool


class ContractCoverageSummaryData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    manifest_count: int
    configuration_schema_count: int
    capability_count: int
    input_schema_count: int
    output_schema_count: int
    handler_count: int
    covered_capability_count: int
    contract_test_count: int
    synthetic_fixture_count: int
    orphan_artifact_count: int
    contract_set_digest: str


class ContractFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    rule_id: str
    category: str
    severity: str
    artifact_scope: str
    subject_fingerprint: str
    summary: str
    remediation: str


class ContractCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    state: str
    severity: str
    summary: str
    remediation: str


class ConnectorPackageContractValidationData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    validation_id: str
    schema_version: str
    version: int
    lifecycle: str
    outcome: str
    source_license_analysis_id: str
    source_license_analysis_digest: str
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
    source_license_analyzed_by: str
    source_custodied_by: str
    source_domain_reviewed_by: str
    source_security_reviewed_by: str
    source_lab_operated_by: str
    organization_id: str
    environment_id: str
    validated_by: str
    validation_profile: str
    validator_version: str
    package_digest: str
    package_size_bytes: int
    inventory_digest: str
    dependency_set_digest: str
    coverage: ContractCoverageSummaryData
    findings: tuple[ContractFindingData, ...]
    finding_set_digest: str
    validation_digest: str
    checks: tuple[ContractCheckData, ...]
    limitations: tuple[str, ...]
    promotion_blocked: bool
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
        cls, validation: ConnectorPackageContractValidation
    ) -> ConnectorPackageContractValidationData:
        return cls.model_validate(validation)


class ConnectorPackageContractValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageContractValidationData
    meta: ResponseMeta
