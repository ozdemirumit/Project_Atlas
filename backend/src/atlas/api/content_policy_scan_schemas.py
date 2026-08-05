from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.content_policy_scan import ConnectorPackageContentPolicyScan

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageContentPolicyScanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-content-policy-scan-request.v1", pattern=STABLE_ID
    )
    source_inventory_id: str = Field(pattern=STABLE_ID)
    source_inventory_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    scan_profile: str = Field(
        default="atlas.connector-content-policy-scan.python312.v1", pattern=STABLE_ID
    )
    acknowledged_untrusted_package_content: bool


class ContentPolicyFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    rule_code: str
    kind: str
    severity: str
    relative_path: str
    line_number: int | None
    evidence_fingerprint: str
    summary: str
    remediation: str


class ContentPolicyCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    state: str
    severity: str
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str


class ConnectorPackageContentPolicyScanData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    scan_id: str
    schema_version: str
    version: int
    lifecycle: str
    outcome: str
    source_inventory_id: str
    source_inventory_digest: str
    source_validation_id: str
    source_validation_digest: str
    source_acquisition_id: str
    source_acquisition_digest: str
    source_handoff_id: str
    source_project_id: str
    source_acquired_by: str
    source_validated_by: str
    source_inventoried_by: str
    source_custodied_by: str
    source_domain_reviewed_by: str
    source_security_reviewed_by: str
    source_lab_operated_by: str
    organization_id: str
    environment_id: str
    scanned_by: str
    scan_profile: str
    scanner_version: str
    package_digest: str
    package_size_bytes: int
    inventory_digest: str
    dependency_set_digest: str
    scanned_file_count: int
    findings: tuple[ContentPolicyFindingData, ...]
    finding_set_digest: str
    content_scan_digest: str
    checks: tuple[ContentPolicyCheckData, ...]
    limitations: tuple[str, ...]
    promotion_blocked: bool
    canonical_digest: str
    scanned_at: datetime
    secret_content_scan_completed: bool
    prohibited_content_scan_completed: bool
    vulnerability_scan_completed: bool
    malware_scan_completed: bool
    license_scan_completed: bool
    static_code_validation_completed: bool
    schema_semantic_validation_completed: bool
    permission_behavior_validation_completed: bool
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
        cls, scan: ConnectorPackageContentPolicyScan
    ) -> ConnectorPackageContentPolicyScanData:
        return cls.model_validate(scan)


class ConnectorPackageContentPolicyScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageContentPolicyScanData
    meta: ResponseMeta
