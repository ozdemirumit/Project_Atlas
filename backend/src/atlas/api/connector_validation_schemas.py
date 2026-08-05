from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.validation_intake import ConnectorPackageValidation

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorPackageValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-package-validation-request.v1", pattern=STABLE_ID
    )
    source_acquisition_id: str = Field(pattern=STABLE_ID)
    source_acquisition_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    validation_profile: str = Field(
        default="atlas.connector-validation-intake.builder-v1", pattern=STABLE_ID
    )
    acknowledged_untrusted_quarantined_package: bool


class PackageValidationCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    state: str
    severity: str
    summary: str
    evidence_paths: list[str]
    remediation: str


class ValidatedSchemaEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_path: str
    digest: str
    schema_id: str
    purpose: str
    capability_id: str | None


class ConnectorPackageValidationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_id: str
    schema_version: str
    version: int
    lifecycle: str
    outcome: str
    source_acquisition_id: str
    source_acquisition_digest: str
    source_handoff_id: str
    source_handoff_digest: str
    source_project_id: str
    source_acquired_by: str
    organization_id: str
    environment_id: str
    validated_by: str
    validation_profile: str
    validator_version: str
    package_digest: str
    package_size_bytes: int
    manifest_path: str
    manifest_digest: str | None
    capability_ids: list[str]
    schema_evidence: list[ValidatedSchemaEvidenceData]
    checks: list[PackageValidationCheckData]
    limitations: list[str]
    canonical_digest: str
    validated_at: datetime
    source_integrity_accepted: bool
    manifest_schema_validation_completed: bool
    dependency_scan_completed: bool
    vulnerability_scan_completed: bool
    malware_scan_completed: bool
    secret_content_scan_completed: bool
    license_scan_completed: bool
    static_code_validation_completed: bool
    contract_validation_completed: bool
    runner_validation_completed: bool
    lab_validation_completed: bool
    package_signed: bool
    publisher_attested: bool
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
    def from_domain(cls, validation: ConnectorPackageValidation) -> ConnectorPackageValidationData:
        return cls(
            validation_id=validation.validation_id,
            schema_version=validation.schema_version,
            version=validation.version,
            lifecycle=validation.lifecycle.value,
            outcome=validation.outcome.value,
            source_acquisition_id=validation.source_acquisition_id,
            source_acquisition_digest=validation.source_acquisition_digest,
            source_handoff_id=validation.source_handoff_id,
            source_handoff_digest=validation.source_handoff_digest,
            source_project_id=validation.source_project_id,
            source_acquired_by=validation.source_acquired_by,
            organization_id=validation.organization_id,
            environment_id=validation.environment_id,
            validated_by=validation.validated_by,
            validation_profile=validation.validation_profile,
            validator_version=validation.validator_version,
            package_digest=validation.package_digest,
            package_size_bytes=validation.package_size_bytes,
            manifest_path=validation.manifest_path,
            manifest_digest=validation.manifest_digest,
            capability_ids=list(validation.capability_ids),
            schema_evidence=[
                ValidatedSchemaEvidenceData(
                    relative_path=item.relative_path,
                    digest=item.digest,
                    schema_id=item.schema_id,
                    purpose=item.purpose.value,
                    capability_id=item.capability_id,
                )
                for item in validation.schema_evidence
            ],
            checks=[
                PackageValidationCheckData(
                    code=item.code,
                    state=item.state.value,
                    severity=item.severity.value,
                    summary=item.summary,
                    evidence_paths=list(item.evidence_paths),
                    remediation=item.remediation,
                )
                for item in validation.checks
            ],
            limitations=list(validation.limitations),
            canonical_digest=validation.canonical_digest,
            validated_at=validation.validated_at,
            source_integrity_accepted=validation.source_integrity_accepted,
            manifest_schema_validation_completed=(validation.manifest_schema_validation_completed),
            dependency_scan_completed=validation.dependency_scan_completed,
            vulnerability_scan_completed=validation.vulnerability_scan_completed,
            malware_scan_completed=validation.malware_scan_completed,
            secret_content_scan_completed=validation.secret_content_scan_completed,
            license_scan_completed=validation.license_scan_completed,
            static_code_validation_completed=validation.static_code_validation_completed,
            contract_validation_completed=validation.contract_validation_completed,
            runner_validation_completed=validation.runner_validation_completed,
            lab_validation_completed=validation.lab_validation_completed,
            package_signed=validation.package_signed,
            publisher_attested=validation.publisher_attested,
            connector_registered=validation.connector_registered,
            connector_approved=validation.connector_approved,
            connector_installed=validation.connector_installed,
            connector_enabled=validation.connector_enabled,
            target_configured=validation.target_configured,
            credentials_resolved=validation.credentials_resolved,
            runtime_trust_granted=validation.runtime_trust_granted,
            execution_authorized=validation.execution_authorized,
            deployment_approved=validation.deployment_approved,
            infrastructure_mutation_performed=validation.infrastructure_mutation_performed,
            reused=validation.reused,
        )


class ConnectorPackageValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorPackageValidationData
    meta: ResponseMeta
