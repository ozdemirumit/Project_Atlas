from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.runner_validation import ConnectorPackageRunnerValidation

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageRunnerValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-runner-validation-request.v1", pattern=STABLE_ID
    )
    source_contract_validation_id: str = Field(pattern=STABLE_ID)
    source_contract_validation_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    validation_profile: str = Field(
        default="atlas.connector-runner.python312.v1", pattern=STABLE_ID
    )
    acknowledged_disconnected_synthetic_execution: bool


class RunnerCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    state: str
    severity: str
    summary: str
    remediation: str


class ConnectorPackageRunnerValidationData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    validation_id: str
    schema_version: str
    version: int
    outcome: str
    source_contract_validation_id: str
    source_contract_validation_digest: str
    source_license_analysis_id: str
    source_license_analysis_digest: str
    source_inventory_id: str
    source_acquisition_id: str
    source_project_id: str
    source_contract_validated_by: str
    source_actor_set_digest: str
    organization_id: str
    environment_id: str
    validated_by: str
    validation_profile: str
    adapter_contract: str
    harness_version: str
    runtime_version: str
    package_digest: str
    package_size_bytes: int
    inventory_digest: str
    capability_count: int
    invoked_capability_count: int
    fail_closed_count: int
    bounded_literal_count: int
    checks: tuple[RunnerCheckData, ...]
    child_started: bool
    child_exit_code: int | None
    duration_ms: int
    output_digest: str
    output_size_bytes: int
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
    def from_domain(
        cls, validation: ConnectorPackageRunnerValidation
    ) -> ConnectorPackageRunnerValidationData:
        return cls.model_validate(validation)


class ConnectorPackageRunnerValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageRunnerValidationData
    meta: ResponseMeta
