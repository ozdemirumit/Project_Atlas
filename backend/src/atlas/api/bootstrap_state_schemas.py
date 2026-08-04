from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import (
    ArtifactAcquisitionExecution,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapMutationResult,
    BootstrapRunIdentity,
    BootstrapRunRecord,
    BootstrapStateView,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class BootstrapClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-claim.v1"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    phase_ids: list[str] = Field(min_length=1, max_length=32)
    lease_minutes: int = Field(ge=1, le=15)
    justification: str | None = Field(default=None, min_length=12, max_length=500)

    @field_validator("phase_ids")
    @classmethod
    def validate_phase_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("phase IDs must be unique")
        if any(re.fullmatch(STABLE_ID_PATTERN, item) is None for item in values):
            raise ValueError("phase IDs must be stable identifiers")
        return values

    @field_validator("justification")
    @classmethod
    def validate_claim_justification(cls, value: str | None) -> str | None:
        if value is not None and (
            value != value.strip() or any(ord(character) < 32 for character in value)
        ):
            raise ValueError("justification must be trimmed single-line text")
        return value

    def to_identity(self) -> BootstrapRunIdentity:
        return BootstrapRunIdentity(
            release_id=self.release_id,
            profile=self.profile,
            organization_id=self.organization_id,
            environment_id=self.environment_id,
            site_id=self.site_id,
            plan_digest=self.plan_digest,
            resume_key=self.resume_key,
            configuration_digest=self.configuration_digest,
            phase_ids=tuple(self.phase_ids),
        )


class BootstrapCheckpointInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-checkpoint.v1"]
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    phase_id: str = Field(pattern=STABLE_ID_PATTERN)
    state: Literal["completed", "failed"]
    safe_output_references: list[str] = Field(default_factory=list, max_length=20)
    expected_version: int = Field(ge=1)

    @field_validator("safe_output_references")
    @classmethod
    def validate_output_references(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("output references must be unique")
        for value in values:
            if not value.startswith(("evidence.", "result.", "artifact.")):
                raise ValueError("output must use an opaque safe reference")
            if re.fullmatch(STABLE_ID_PATTERN, value) is None:
                raise ValueError("output references must be stable identifiers")
        return values


class BootstrapReleaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-release.v1"]
    expected_version: int = Field(ge=1)


class BootstrapRebaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-rebase.v1"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    phase_ids: list[str] = Field(min_length=1, max_length=32)
    expected_version: int = Field(ge=1)
    preview_source_version: int = Field(ge=1)
    justification: str = Field(min_length=12, max_length=500)

    @field_validator("phase_ids")
    @classmethod
    def validate_rebase_phase_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(
            re.fullmatch(STABLE_ID_PATTERN, item) is None for item in values
        ):
            raise ValueError("phase IDs must be unique stable identifiers")
        return values

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("justification must be trimmed single-line text")
        return value

    def to_identity(self) -> BootstrapRunIdentity:
        return BootstrapRunIdentity(
            release_id=self.release_id,
            profile=self.profile,
            organization_id=self.organization_id,
            environment_id=self.environment_id,
            site_id=self.site_id,
            plan_digest=self.plan_digest,
            resume_key=self.resume_key,
            configuration_digest=self.configuration_digest,
            phase_ids=tuple(self.phase_ids),
        )


class BootstrapCheckpointData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase_id: str
    state: str
    safe_output_references: list[str]
    recorded_at: datetime


class VerifiedArtifactData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    sha256: str
    size_bytes: int
    disposition: str


class ArtifactAcquisitionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str
    phase_id: str
    release_id: str
    manifest_digest: str
    mode: str
    preflight_report_id: str
    state: str
    result_code: str
    started_at: datetime
    completed_at: datetime | None
    evidence: list[VerifiedArtifactData]
    artifact_count: int
    total_bytes: int

    @classmethod
    def from_domain(cls, execution: ArtifactAcquisitionExecution) -> ArtifactAcquisitionData:
        return cls(
            execution_id=execution.execution_id,
            phase_id=execution.phase_id,
            release_id=execution.release_id,
            manifest_digest=execution.manifest_digest,
            mode=execution.mode.value,
            preflight_report_id=execution.preflight_report_id,
            state=execution.state.value,
            result_code=execution.result_code,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            evidence=[
                VerifiedArtifactData(
                    artifact_id=item.artifact_id,
                    sha256=item.sha256,
                    size_bytes=item.size_bytes,
                    disposition=item.disposition.value,
                )
                for item in execution.evidence
            ],
            artifact_count=len(execution.evidence),
            total_bytes=execution.total_bytes,
        )


class BootstrapRunData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    version: int
    state: str
    release_id: str
    profile: str
    organization_id: str
    environment_id: str
    site_id: str
    plan_digest: str
    resume_key: str
    configuration_digest: str
    phase_ids: list[str]
    checkpoints: list[BootstrapCheckpointData]
    completed_phase_ids: list[str]
    failed_phase_id: str | None
    current_phase_id: str | None
    lease_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    artifact_acquisition: ArtifactAcquisitionData | None

    @classmethod
    def from_domain(cls, record: BootstrapRunRecord) -> BootstrapRunData:
        return cls(
            run_id=record.run_id,
            version=record.version,
            state=record.state.value,
            release_id=record.identity.release_id,
            profile=record.identity.profile.value,
            organization_id=record.identity.organization_id,
            environment_id=record.identity.environment_id,
            site_id=record.identity.site_id,
            plan_digest=record.identity.plan_digest,
            resume_key=record.identity.resume_key,
            configuration_digest=record.identity.configuration_digest,
            phase_ids=list(record.identity.phase_ids),
            checkpoints=[
                BootstrapCheckpointData(
                    phase_id=item.phase_id,
                    state=item.state.value,
                    safe_output_references=list(item.safe_output_references),
                    recorded_at=item.recorded_at,
                )
                for item in record.checkpoints
            ],
            completed_phase_ids=list(record.completed_phase_ids),
            failed_phase_id=record.failed_phase_id,
            current_phase_id=record.current_phase_id,
            lease_expires_at=record.lease_expires_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
            artifact_acquisition=(
                ArtifactAcquisitionData.from_domain(record.artifact_acquisition)
                if record.artifact_acquisition is not None
                else None
            ),
        )


class BootstrapStateData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData | None
    durable: bool
    lease_available: bool
    lease_held_by_current_actor: bool
    execution_authorized: bool
    infrastructure_mutation_authorized: bool

    @classmethod
    def from_view(cls, view: BootstrapStateView) -> BootstrapStateData:
        return cls(
            run=BootstrapRunData.from_domain(view.record) if view.record is not None else None,
            durable=view.durable,
            lease_available=view.lease_available,
            lease_held_by_current_actor=view.lease_held_by_current_actor,
            execution_authorized=view.execution_authorized,
            infrastructure_mutation_authorized=view.infrastructure_mutation_authorized,
        )


class BootstrapMutationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData
    replayed: bool
    reclaimed_expired_lease: bool
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    @classmethod
    def from_domain(cls, result: BootstrapMutationResult) -> BootstrapMutationData:
        return cls(
            run=BootstrapRunData.from_domain(result.record),
            replayed=result.replayed,
            reclaimed_expired_lease=result.reclaimed_expired_lease,
        )


class BootstrapRebaseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: BootstrapRunData
    replayed: bool
    preserved_checkpoint_phase_ids: list[str]
    invalidated_checkpoint_phase_ids: list[str]
    invalidation_reason_codes: list[str]
    earliest_affected_phase_id: str
    execution_authorized: bool = False
    lease_mutation_authorized: bool = False
    infrastructure_mutation_authorized: bool = False

    @classmethod
    def from_domain(cls, result: BootstrapMutationResult) -> BootstrapRebaseData:
        if result.earliest_affected_phase_id is None:
            raise ValueError("rebase result requires an invalidation boundary")
        return cls(
            run=BootstrapRunData.from_domain(result.record),
            replayed=result.replayed,
            preserved_checkpoint_phase_ids=list(result.preserved_checkpoint_phase_ids),
            invalidated_checkpoint_phase_ids=list(result.invalidated_checkpoint_phase_ids),
            invalidation_reason_codes=list(result.invalidation_reason_codes),
            earliest_affected_phase_id=result.earliest_affected_phase_id,
        )


class BootstrapStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapStateData
    meta: ResponseMeta


class BootstrapMutationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapMutationData
    meta: ResponseMeta


class BootstrapRebaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapRebaseData
    meta: ResponseMeta
