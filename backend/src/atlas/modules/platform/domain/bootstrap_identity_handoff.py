from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.release_preflight import SHA256_PATTERN, DeploymentProfile


class IdentityPlanState(StrEnum):
    PASSED = "passed"


class IdentityTargetState(StrEnum):
    EMPTY = "empty"
    REUSABLE = "reusable"


class IdentityHandoffState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IdentityStateDisposition(StrEnum):
    PUBLISHED = "published"
    REUSED = "reused"


@dataclass(frozen=True, slots=True)
class BootstrapIdentityGroupMapping:
    mapping_id: str
    directory_group_reference: str
    role_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.mapping_id, "identity mapping id")
        validate_stable_identifier(self.directory_group_reference, "directory group reference")
        if (
            not self.role_ids
            or len(self.role_ids) > 8
            or len(set(self.role_ids)) != len(self.role_ids)
        ):
            raise ValueError("identity role mapping is invalid")
        for role_id in self.role_ids:
            validate_stable_identifier(role_id, "identity role id")


@dataclass(frozen=True, slots=True)
class BootstrapIdentityPlan:
    schema_version: str
    release_id: str
    profile: DeploymentProfile
    organization_id: str
    environment_id: str
    site_id: str
    configuration_digest: str
    trust_plan_digest: str
    data_plan_digest: str
    service_plan_digest: str
    identity_plan_digest: str
    target_id: str
    target_kind: str
    target_state: IdentityTargetState
    bootstrap_administrator_subject_id: str
    credential_verifier_reference_id: str
    credential_replacement_required: bool
    recovery_identity_id: str
    recovery_seal_required: bool
    provider_id: str
    provider_protocol: str
    pilot_subject_id: str
    group_mappings: tuple[BootstrapIdentityGroupMapping, ...]
    state: IdentityPlanState
    result_code: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.schema_version != "atlas.bootstrap-identity-plan.v1":
            raise ValueError("bootstrap identity plan schema is unsupported")
        for value, label in (
            (self.release_id, "release id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.site_id, "site id"),
            (self.target_id, "identity target id"),
            (self.target_kind, "identity target kind"),
            (self.bootstrap_administrator_subject_id, "bootstrap administrator id"),
            (self.credential_verifier_reference_id, "credential verifier reference"),
            (self.recovery_identity_id, "recovery identity id"),
            (self.provider_id, "identity provider id"),
            (self.pilot_subject_id, "pilot subject id"),
            (self.result_code, "identity plan result code"),
        ):
            validate_stable_identifier(value, label)
        if any(
            not SHA256_PATTERN.fullmatch(value)
            for value in (
                self.configuration_digest,
                self.trust_plan_digest,
                self.data_plan_digest,
                self.service_plan_digest,
                self.identity_plan_digest,
            )
        ):
            raise ValueError("bootstrap identity plan digest is invalid")
        if (
            self.provider_protocol != "ldaps"
            or not self.credential_replacement_required
            or not self.recovery_seal_required
            or not self.group_mappings
            or len(self.group_mappings) > 8
            or self.generated_at.tzinfo is None
        ):
            raise ValueError("bootstrap identity policy is unsafe")
        mapping_ids = tuple(item.mapping_id for item in self.group_mappings)
        group_ids = tuple(item.directory_group_reference for item in self.group_mappings)
        if len(set(mapping_ids)) != len(mapping_ids) or len(set(group_ids)) != len(group_ids):
            raise ValueError("bootstrap identity mappings contain duplicates")


@dataclass(frozen=True, slots=True)
class IdentityStateEvidence:
    evidence_id: str
    sha256: str
    size_bytes: int
    disposition: IdentityStateDisposition

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_id, "identity evidence id")
        if not SHA256_PATTERN.fullmatch(self.sha256) or self.size_bytes < 1:
            raise ValueError("identity state evidence is invalid")


@dataclass(frozen=True, slots=True)
class IdentityHandoffExecution:
    execution_id: str
    phase_id: str
    release_id: str
    profile: DeploymentProfile
    configuration_digest: str
    trust_plan_digest: str
    data_plan_digest: str
    service_plan_digest: str
    identity_schema_version: str
    identity_plan_digest: str
    target_id: str
    state: IdentityHandoffState
    result_code: str
    started_at: datetime
    completed_at: datetime | None
    group_mapping_count: int
    validation_count: int
    credential_replacement_required: bool
    recovery_identity_verified: bool
    bootstrap_material_sealed: bool
    pilot_identity_verified: bool
    enterprise_authentication_validated: bool
    evidence: tuple[IdentityStateEvidence, ...]

    def __post_init__(self) -> None:
        for value, label in (
            (self.execution_id, "execution id"),
            (self.phase_id, "phase id"),
            (self.release_id, "release id"),
            (self.identity_schema_version, "identity schema version"),
            (self.target_id, "identity target id"),
            (self.result_code, "identity result code"),
        ):
            validate_stable_identifier(value, label)
        if (
            self.phase_id != "phase.identity"
            or self.identity_schema_version != "atlas.bootstrap-identity-plan.v1"
        ):
            raise ValueError("identity handoff phase identity is invalid")
        if any(
            not SHA256_PATTERN.fullmatch(value)
            for value in (
                self.configuration_digest,
                self.trust_plan_digest,
                self.data_plan_digest,
                self.service_plan_digest,
                self.identity_plan_digest,
            )
        ):
            raise ValueError("identity handoff digest is invalid")
        if self.started_at.tzinfo is None or (
            self.completed_at is not None and self.completed_at.tzinfo is None
        ):
            raise ValueError("identity handoff timestamps must be timezone-aware")
        final_values = (
            self.group_mapping_count,
            self.validation_count,
            self.credential_replacement_required,
            self.recovery_identity_verified,
            self.bootstrap_material_sealed,
            self.pilot_identity_verified,
            self.enterprise_authentication_validated,
            bool(self.evidence),
        )
        if self.state is IdentityHandoffState.RUNNING:
            if self.completed_at is not None or any(final_values):
                raise ValueError("running identity handoff cannot contain final evidence")
        elif self.completed_at is None or self.completed_at < self.started_at:
            raise ValueError("finished identity handoff requires a valid completion time")
        if self.state is IdentityHandoffState.COMPLETED:
            if (
                self.group_mapping_count < 1
                or self.validation_count != 5
                or not all(final_values[2:7])
                or len(self.evidence) != 1
            ):
                raise ValueError("completed identity handoff evidence is incomplete")
        elif any(final_values):
            raise ValueError("failed identity handoff cannot contain verified evidence")


@dataclass(frozen=True, slots=True)
class IdentityHandoffReceipt:
    group_mapping_count: int
    validation_count: int
    evidence: tuple[IdentityStateEvidence, ...]

    def __post_init__(self) -> None:
        if self.group_mapping_count < 1 or self.validation_count != 5 or len(self.evidence) != 1:
            raise ValueError("identity handoff receipt is incomplete")
