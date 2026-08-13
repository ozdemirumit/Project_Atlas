from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit

from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_PROFILE_KEY = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
_PROVIDER_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
ALLOWED_SOURCE_FIELDS = frozenset(
    {
        "generated_content_label",
        "incident_reference",
        "u_atlas_report_reference",
        "u_atlas_review_state",
        "work_notes",
    }
)


class ItsmProviderFamily(StrEnum):
    SERVICE_NOW = "service_now"
    JIRA_SERVICE_MANAGEMENT = "jira_service_management"
    GENERIC_REST = "generic_rest"


class ItsmAllowedOperation(StrEnum):
    APPEND_ANALYSIS = "append_analysis"
    CREATE_INCIDENT_DRAFT = "create_incident_draft"


class ItsmWriteSemantics(StrEnum):
    APPEND_ONLY = "append_only"
    REFERENCE_ONLY = "reference_only"


class ItsmProfileLifecycle(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class ItsmReadinessState(StrEnum):
    READY_FOR_SANDBOX = "ready_for_sandbox"
    BLOCKED = "blocked"


class ItsmCheckState(StrEnum):
    SATISFIED = "satisfied"
    BLOCKED = "blocked"


class ItsmSandboxConformanceState(StrEnum):
    CONFORMANT = "conformant"
    UNAVAILABLE = "unavailable"
    PROFILE_BLOCKED = "profile_blocked"
    TRUST_FAILED = "trust_failed"
    CREDENTIAL_FAILED = "credential_failed"
    PERMISSION_FAILED = "permission_failed"
    MAPPING_FAILED = "mapping_failed"
    ROUND_TRIP_FAILED = "round_trip_failed"


@dataclass(frozen=True, slots=True)
class ItsmFieldMapping:
    source_field: str
    provider_field: str
    write_semantics: ItsmWriteSemantics

    def __post_init__(self) -> None:
        if (
            self.source_field not in ALLOWED_SOURCE_FIELDS
            or _PROVIDER_FIELD.fullmatch(self.provider_field) is None
        ):
            raise ValueError("ITSM field mapping is outside the allowlist")
        if (
            self.source_field == "work_notes"
            and self.write_semantics is not ItsmWriteSemantics.APPEND_ONLY
        ):
            raise ValueError("ITSM work notes must remain append-only")
        if (
            self.source_field != "work_notes"
            and self.write_semantics is not ItsmWriteSemantics.REFERENCE_ONLY
        ):
            raise ValueError("ITSM reference fields cannot be mutable")


@dataclass(frozen=True, slots=True)
class ItsmReadinessCheck:
    check_id: str
    state: ItsmCheckState
    reason_code: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.check_id, "ITSM readiness check")
        validate_stable_identifier(self.reason_code, "ITSM readiness reason")


@dataclass(frozen=True, slots=True)
class ItsmReadinessAssessment:
    state: ItsmReadinessState
    checks: tuple[ItsmReadinessCheck, ...]
    assessed_at: datetime
    canonical_digest: str
    dispatch_authorized: bool = False
    external_record_mutation_authorized: bool = False
    workflow_approved: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if (
            len(self.checks) != 6
            or len({item.check_id for item in self.checks}) != len(self.checks)
            or self.assessed_at.tzinfo is None
            or _DIGEST.fullmatch(self.canonical_digest) is None
            or (self.state is ItsmReadinessState.READY_FOR_SANDBOX)
            != all(item.state is ItsmCheckState.SATISFIED for item in self.checks)
            or any(
                (
                    self.dispatch_authorized,
                    self.external_record_mutation_authorized,
                    self.workflow_approved,
                    self.execution_authorized,
                )
            )
        ):
            raise ValueError("ITSM readiness assessment violates its authority boundary")


@dataclass(frozen=True, slots=True)
class ItsmIntegrationProfile:
    profile_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    profile_key: str
    display_name: str
    provider_family: ItsmProviderFamily
    instance_reference: str
    owner_id: str
    purpose: str
    endpoint_origin: str
    trust_boundary_reference: str
    secret_reference_id: str
    classification_ceiling: DataClassification
    allowed_operations: tuple[ItsmAllowedOperation, ...]
    mapping_version: int
    field_mappings: tuple[ItsmFieldMapping, ...]
    sandbox_validation_reference: str | None
    sandbox_validation_digest: str | None
    audit_profile_id: str
    lifecycle: ItsmProfileLifecycle
    readiness: ItsmReadinessAssessment
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    canonical_digest: str
    create_request_fingerprint: str
    create_idempotency_key: str
    retired_by: str | None = None
    retired_at: datetime | None = None
    retirement_reason: str | None = None
    retirement_request_fingerprint: str | None = None
    retirement_idempotency_key: str | None = None
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.profile_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.profile_key,
            self.instance_reference,
            self.owner_id,
            self.trust_boundary_reference,
            self.secret_reference_id,
            self.audit_profile_id,
            self.created_by,
            self.updated_by,
        ):
            validate_stable_identifier(value, "ITSM profile identifier")
        endpoint = urlsplit(self.endpoint_origin)
        if (
            self.version < 1
            or _PROFILE_KEY.fullmatch(self.profile_key) is None
            or not 3 <= len(self.display_name.strip()) <= 160
            or not 20 <= len(self.purpose.strip()) <= 1000
            or endpoint.scheme != "https"
            or not endpoint.netloc
            or endpoint.path not in {"", "/"}
            or endpoint.query
            or endpoint.fragment
            or not self.secret_reference_id.startswith("secret.")
            or not self.allowed_operations
            or len(set(self.allowed_operations)) != len(self.allowed_operations)
            or self.mapping_version < 1
            or not self.field_mappings
            or len({item.source_field for item in self.field_mappings}) != len(self.field_mappings)
            or self.created_at.tzinfo is None
            or self.updated_at.tzinfo is None
            or self.updated_at < self.created_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
            or _DIGEST.fullmatch(self.create_request_fingerprint) is None
            or not 8 <= len(self.create_idempotency_key) <= 128
        ):
            raise ValueError("ITSM integration profile is invalid")
        sandbox_values = (self.sandbox_validation_reference, self.sandbox_validation_digest)
        if any(value is not None for value in sandbox_values) and not all(
            value is not None for value in sandbox_values
        ):
            raise ValueError("ITSM sandbox validation binding is incomplete")
        if self.sandbox_validation_reference is not None:
            validate_stable_identifier(
                self.sandbox_validation_reference, "ITSM sandbox validation reference"
            )
            assert self.sandbox_validation_digest is not None
            if _DIGEST.fullmatch(self.sandbox_validation_digest) is None:
                raise ValueError("ITSM sandbox validation digest is invalid")
        retired = self.lifecycle is ItsmProfileLifecycle.RETIRED
        retirement = (
            self.retired_by,
            self.retired_at,
            self.retirement_reason,
            self.retirement_request_fingerprint,
            self.retirement_idempotency_key,
        )
        if retired != all(value is not None for value in retirement):
            raise ValueError("ITSM profile retirement metadata is incomplete")
        if self.retired_by is not None:
            validate_stable_identifier(self.retired_by, "ITSM profile retirement actor")
        if retired and (
            self.version < 2
            or self.retired_at is None
            or self.retired_at != self.updated_at
            or self.retirement_reason is None
            or not 20 <= len(self.retirement_reason.strip()) <= 1000
            or self.retirement_request_fingerprint is None
            or _DIGEST.fullmatch(self.retirement_request_fingerprint) is None
            or self.retirement_idempotency_key is None
            or not 8 <= len(self.retirement_idempotency_key) <= 128
        ):
            raise ValueError("ITSM profile retirement metadata is invalid")


@dataclass(frozen=True, slots=True)
class ItsmSandboxDiagnostic:
    adapter_id: str
    adapter_version: str
    organization_id: str
    environment_id: str
    site_id: str
    profile_id: str
    profile_version: int
    challenge_digest: str
    state: ItsmSandboxConformanceState
    reason_code: str
    production_eligible: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.adapter_id,
            self.adapter_version,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.profile_id,
            self.reason_code,
        ):
            validate_stable_identifier(value, "ITSM sandbox diagnostic identifier")
        if (
            self.profile_version < 1
            or _DIGEST.fullmatch(self.challenge_digest) is None
            or not self.reason_code.startswith("itsm.sandbox-conformance.")
        ):
            raise ValueError("ITSM sandbox diagnostic is invalid")


@dataclass(frozen=True, slots=True)
class ItsmSandboxConformanceAssessment:
    assessment_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    profile_id: str
    profile_version: int
    profile_digest: str
    mapping_version: int
    assessed_by: str
    adapter_id: str
    adapter_version: str
    adapter_production_eligible: bool
    diagnostic_contract_version: str
    challenge_digest: str
    observed_at: datetime
    valid_until: datetime
    state: ItsmSandboxConformanceState
    reason_codes: tuple[str, ...]
    request_fingerprint: str
    idempotency_key: str
    canonical_digest: str
    diagnostic_only: bool = True
    sandbox_conformant: bool = False
    production_ready: bool = False
    dispatch_authorized: bool = False
    external_record_mutation_authorized: bool = False
    workflow_approved: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.assessment_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.profile_id,
            self.assessed_by,
            self.adapter_id,
            self.adapter_version,
            self.diagnostic_contract_version,
        ):
            validate_stable_identifier(value, "ITSM sandbox conformance identifier")
        if (
            self.schema_version != "atlas.itsm-sandbox-conformance-assessment.v1"
            or self.version != 1
            or self.profile_version < 1
            or self.mapping_version < 1
            or _DIGEST.fullmatch(self.profile_digest) is None
            or _DIGEST.fullmatch(self.challenge_digest) is None
            or _DIGEST.fullmatch(self.request_fingerprint) is None
            or _DIGEST.fullmatch(self.canonical_digest) is None
            or self.observed_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_until <= self.observed_at
            or not self.reason_codes
            or any(
                not reason.startswith("itsm.sandbox-conformance.") for reason in self.reason_codes
            )
            or not 8 <= len(self.idempotency_key) <= 128
            or not self.diagnostic_only
            or self.sandbox_conformant != (self.state is ItsmSandboxConformanceState.CONFORMANT)
            or self.production_ready
            or any(
                (
                    self.dispatch_authorized,
                    self.external_record_mutation_authorized,
                    self.workflow_approved,
                    self.execution_authorized,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("ITSM sandbox conformance assessment is invalid")
