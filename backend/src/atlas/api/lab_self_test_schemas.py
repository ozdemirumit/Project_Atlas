from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.lab_self_test import ConnectorPackageLabSelfTest

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageLabSelfTestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-lab-self-test-request.v1", pattern=STABLE_ID
    )
    source_runner_validation_id: str = Field(pattern=STABLE_ID)
    source_runner_validation_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    lab_plan_id: str = Field(pattern=STABLE_ID)
    lab_plan_digest: str = Field(pattern=DIGEST)
    validation_profile: str = Field(
        default="atlas.connector-lab-self-test.readonly.v1", pattern=STABLE_ID
    )
    acknowledged_non_production_read_only_lab_access: bool


class LabCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    state: str
    severity: str
    summary: str
    remediation: str


class ConnectorPackageLabSelfTestData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    self_test_id: str
    schema_version: str
    version: int
    outcome: str
    source_runner_validation_id: str
    source_runner_validation_digest: str
    source_contract_validation_id: str
    source_contract_validation_digest: str
    source_inventory_id: str
    source_acquisition_id: str
    source_project_id: str
    source_runner_validated_by: str
    source_actor_set_digest: str
    lab_plan_id: str
    lab_plan_digest: str
    lab_plan_approved_by: str
    credential_custodied_by: str
    organization_id: str
    environment_id: str
    validated_by: str
    target_alias: str
    product_family: str
    observed_product_version: str
    validation_profile: str
    adapter_contract: str
    runner_runtime: str
    package_digest: str
    package_size_bytes: int
    inventory_digest: str
    capability_count: int
    tested_capability_count: int
    request_count: int
    request_bytes: int
    response_bytes: int
    checks: tuple[LabCheckData, ...]
    duration_ms: int
    evidence_digest: str
    lease_issued: bool
    lease_released: bool
    credentials_revoked: bool
    session_closed: bool
    workspace_removed: bool
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
    def from_domain(cls, self_test: ConnectorPackageLabSelfTest) -> ConnectorPackageLabSelfTestData:
        return cls.model_validate(self_test)


class ConnectorPackageLabSelfTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageLabSelfTestData
    meta: ResponseMeta
