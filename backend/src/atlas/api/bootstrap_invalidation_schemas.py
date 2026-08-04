from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_invalidation import BootstrapInvalidationPreview
from atlas.modules.platform.domain.bootstrap_state import BootstrapRunIdentity
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class BootstrapInvalidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.bootstrap-invalidation-request.v1"]
    release_id: str = Field(pattern=STABLE_ID_PATTERN)
    profile: DeploymentProfile
    organization_id: str = Field(pattern=STABLE_ID_PATTERN)
    environment_id: str = Field(pattern=STABLE_ID_PATTERN)
    site_id: str = Field(pattern=STABLE_ID_PATTERN)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    resume_key: str = Field(pattern=STABLE_ID_PATTERN)
    configuration_digest: str = Field(pattern=DIGEST_PATTERN)
    phase_ids: list[str] = Field(min_length=1, max_length=32)

    @field_validator("phase_ids")
    @classmethod
    def validate_phase_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(
            re.fullmatch(STABLE_ID_PATTERN, item) is None for item in values
        ):
            raise ValueError("phase order is invalid")
        return values

    def to_domain(self) -> BootstrapRunIdentity:
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


class BootstrapInputChangeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    reason_code: str
    old_reference: str
    new_reference: str
    earliest_affected_phase_id: str


class BootstrapInvalidationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: str
    schema_version: str
    state: str
    source_run_id: str | None
    source_run_version: int | None
    changes: list[BootstrapInputChangeData]
    earliest_affected_phase_id: str | None
    reusable_checkpoint_phase_ids: list[str]
    invalidated_checkpoint_phase_ids: list[str]
    downstream_phase_ids: list[str]
    remediation: str | None
    generated_at: datetime
    correlation_id: str
    execution_authorized: bool
    lease_mutation_authorized: bool
    checkpoint_mutation_authorized: bool
    infrastructure_mutation_authorized: bool

    @classmethod
    def from_domain(cls, preview: BootstrapInvalidationPreview) -> BootstrapInvalidationData:
        return cls(
            preview_id=preview.preview_id,
            schema_version=preview.schema_version,
            state=preview.state.value,
            source_run_id=preview.source_run_id,
            source_run_version=preview.source_run_version,
            changes=[
                BootstrapInputChangeData(
                    field=item.field,
                    reason_code=item.reason_code,
                    old_reference=item.old_reference,
                    new_reference=item.new_reference,
                    earliest_affected_phase_id=item.earliest_affected_phase_id,
                )
                for item in preview.changes
            ],
            earliest_affected_phase_id=preview.earliest_affected_phase_id,
            reusable_checkpoint_phase_ids=list(preview.reusable_checkpoint_phase_ids),
            invalidated_checkpoint_phase_ids=list(preview.invalidated_checkpoint_phase_ids),
            downstream_phase_ids=list(preview.downstream_phase_ids),
            remediation=preview.remediation,
            generated_at=preview.generated_at,
            correlation_id=preview.correlation_id,
            execution_authorized=preview.execution_authorized,
            lease_mutation_authorized=preview.lease_mutation_authorized,
            checkpoint_mutation_authorized=preview.checkpoint_mutation_authorized,
            infrastructure_mutation_authorized=preview.infrastructure_mutation_authorized,
        )


class BootstrapInvalidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapInvalidationData
    meta: ResponseMeta
