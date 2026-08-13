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


class ItsmSandboxOnboardingState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class ItsmSandboxOnboardingRequirementState(StrEnum):
    SATISFIED = "satisfied"
    BLOCKED = "blocked"


ITSM_SANDBOX_ONBOARDING_REQUIREMENTS = (
    "itsm.sandbox-onboarding.profile-current",
    "itsm.sandbox-onboarding.conformance-current",
    "itsm.sandbox-onboarding.adapter-registered",
    "itsm.sandbox-onboarding.adapter-sandbox-approved",
    "itsm.sandbox-onboarding.workload-identity",
    "itsm.sandbox-onboarding.credential-ownership",
    "itsm.sandbox-onboarding.network-trust",
    "itsm.sandbox-onboarding.mapping-change-control",
    "itsm.sandbox-onboarding.rate-backpressure",
    "itsm.sandbox-onboarding.audit-routing",
    "itsm.sandbox-onboarding.availability-recovery",
    "itsm.sandbox-onboarding.owner-approvals",
)


@dataclass(frozen=True, slots=True)
class ItsmSandboxOnboardingAdapterRule:
    adapter_id: str
    adapter_version: str
    require_production_eligible: bool = True

    def __post_init__(self) -> None:
        validate_stable_identifier(self.adapter_id, "ITSM onboarding policy adapter")
        validate_stable_identifier(self.adapter_version, "ITSM onboarding policy adapter version")


@dataclass(frozen=True, slots=True)
class ItsmSandboxOnboardingPolicy:
    schema_version: str
    policy_id: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    issuer: str
    requirement_ids: tuple[str, ...]
    adapter_rules: tuple[ItsmSandboxOnboardingAdapterRule, ...]
    max_conformance_age_seconds: int
    max_evidence_age_seconds: int
    issued_at: datetime
    effective_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.schema_version,
            self.policy_id,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.issuer,
        ):
            validate_stable_identifier(value, "ITSM sandbox onboarding policy identifier")
        if (
            self.schema_version != "atlas.itsm-sandbox-onboarding-policy.v1"
            or self.version < 1
            or not self.requirement_ids
            or len(set(self.requirement_ids)) != len(self.requirement_ids)
            or any(not item.startswith("itsm.sandbox-onboarding.") for item in self.requirement_ids)
            or not self.adapter_rules
            or len({(item.adapter_id, item.adapter_version) for item in self.adapter_rules})
            != len(self.adapter_rules)
            or not 60 <= self.max_conformance_age_seconds <= 86400
            or not 60 <= self.max_evidence_age_seconds <= 604800
            or any(
                item.tzinfo is None for item in (self.issued_at, self.effective_at, self.expires_at)
            )
            or self.effective_at < self.issued_at
            or self.expires_at <= self.effective_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("ITSM sandbox onboarding policy is invalid")


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


@dataclass(frozen=True, slots=True)
class ItsmSandboxOnboardingEvidence:
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    profile_id: str
    profile_version: int
    profile_digest: str
    mapping_version: int
    adapter_id: str
    adapter_version: str
    adapter_registered: bool
    adapter_sandbox_approved: bool
    workload_identity_configured: bool
    credential_reference_owned: bool
    network_trust_approved: bool
    mapping_change_control_configured: bool
    rate_limit_and_backpressure_configured: bool
    audit_routing_configured: bool
    availability_and_recovery_configured: bool
    security_approval_reference: str | None
    deployment_approval_reference: str | None
    observed_at: datetime
    valid_until: datetime
    canonical_digest: str
    production_eligible: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.profile_id,
            self.adapter_id,
            self.adapter_version,
        ):
            validate_stable_identifier(value, "ITSM sandbox onboarding evidence identifier")
        for reference in (
            self.security_approval_reference,
            self.deployment_approval_reference,
        ):
            if reference is not None:
                validate_stable_identifier(reference, "ITSM sandbox onboarding approval reference")
        if (
            self.schema_version != "atlas.itsm-sandbox-onboarding-evidence.v1"
            or self.version != 1
            or self.profile_version < 1
            or self.mapping_version < 1
            or _DIGEST.fullmatch(self.profile_digest) is None
            or _DIGEST.fullmatch(self.canonical_digest) is None
            or self.observed_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_until <= self.observed_at
        ):
            raise ValueError("ITSM sandbox onboarding evidence is invalid")


@dataclass(frozen=True, slots=True)
class ItsmSandboxOnboardingRequirement:
    requirement_id: str
    state: ItsmSandboxOnboardingRequirementState
    reason_code: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.requirement_id, "ITSM sandbox onboarding requirement")
        validate_stable_identifier(self.reason_code, "ITSM sandbox onboarding reason")
        if not self.requirement_id.startswith(
            "itsm.sandbox-onboarding."
        ) or not self.reason_code.startswith("itsm.sandbox-onboarding."):
            raise ValueError("ITSM sandbox onboarding requirement is invalid")


@dataclass(frozen=True, slots=True)
class ItsmSandboxOnboardingReadiness:
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    profile_id: str
    profile_version: int
    profile_digest: str
    mapping_version: int
    conformance_assessment_id: str | None
    conformance_assessment_digest: str | None
    adapter_id: str | None
    adapter_version: str | None
    policy_id: str
    policy_version: int
    policy_digest: str
    policy_issuer: str
    policy_expires_at: datetime
    assessed_at: datetime
    evidence_observed_at: datetime | None
    evidence_valid_until: datetime | None
    state: ItsmSandboxOnboardingState
    requirements: tuple[ItsmSandboxOnboardingRequirement, ...]
    canonical_digest: str
    sandbox_onboarding_ready: bool = False
    production_ready: bool = False
    dispatch_authorized: bool = False
    external_record_mutation_authorized: bool = False
    workflow_approved: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.profile_id,
            self.policy_id,
            self.policy_issuer,
        ):
            validate_stable_identifier(value, "ITSM sandbox onboarding readiness identifier")
        optional_ids = (
            self.conformance_assessment_id,
            self.adapter_id,
            self.adapter_version,
        )
        for optional_value in optional_ids:
            if optional_value is not None:
                validate_stable_identifier(
                    optional_value, "ITSM sandbox onboarding readiness binding"
                )
        conformance_bound = (
            self.conformance_assessment_id is not None
            and self.conformance_assessment_digest is not None
            and self.adapter_id is not None
            and self.adapter_version is not None
        )
        if (
            any(value is not None for value in (*optional_ids, self.conformance_assessment_digest))
            and not conformance_bound
        ):
            raise ValueError("ITSM sandbox onboarding conformance binding is incomplete")
        evidence_bound = (
            self.evidence_observed_at is not None and self.evidence_valid_until is not None
        )
        if (
            any(
                value is not None
                for value in (self.evidence_observed_at, self.evidence_valid_until)
            )
            and not evidence_bound
        ):
            raise ValueError("ITSM sandbox onboarding evidence interval is incomplete")
        if (
            self.schema_version != "atlas.itsm-sandbox-onboarding-readiness.v2"
            or self.version != 1
            or self.profile_version < 1
            or self.mapping_version < 1
            or _DIGEST.fullmatch(self.profile_digest) is None
            or self.policy_version < 1
            or _DIGEST.fullmatch(self.policy_digest) is None
            or self.policy_expires_at.tzinfo is None
            or self.policy_expires_at <= self.assessed_at
            or (
                self.conformance_assessment_digest is not None
                and _DIGEST.fullmatch(self.conformance_assessment_digest) is None
            )
            or self.assessed_at.tzinfo is None
            or (
                evidence_bound
                and (
                    self.evidence_observed_at is None
                    or self.evidence_valid_until is None
                    or self.evidence_valid_until <= self.evidence_observed_at
                )
            )
            or len(self.requirements) != 12
            or len({item.requirement_id for item in self.requirements}) != 12
            or _DIGEST.fullmatch(self.canonical_digest) is None
            or self.sandbox_onboarding_ready
            != all(
                item.state is ItsmSandboxOnboardingRequirementState.SATISFIED
                for item in self.requirements
            )
            or (self.state is ItsmSandboxOnboardingState.READY) != self.sandbox_onboarding_ready
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
            raise ValueError("ITSM sandbox onboarding readiness violates its authority boundary")
