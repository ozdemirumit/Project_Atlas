from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.bootstrap_rollback import (
    ComponentVersionCompatibility,
    RollbackAttempt,
    RollbackOutcome,
    RollbackPlan,
    RollbackSupportDeclaration,
    SchemaCompatibilityCheck,
)


class RollbackSupportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: str = Field(min_length=1, max_length=128)
    application_rollback_supported: bool
    data_rollback_supported: bool
    unsupported_rationale: str | None = None

    def to_domain(self) -> RollbackSupportDeclaration:
        return RollbackSupportDeclaration(
            release_id=self.release_id,
            application_rollback_supported=self.application_rollback_supported,
            data_rollback_supported=self.data_rollback_supported,
            unsupported_rationale=self.unsupported_rationale,
        )


class SchemaCompatibilityCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_schema_revision: str = Field(min_length=1, max_length=128)
    target_schema_revision: str = Field(min_length=1, max_length=128)
    irreversible_migrations_applied: list[str] = Field(default_factory=list)
    compatible: bool

    def to_domain(self) -> SchemaCompatibilityCheck:
        return SchemaCompatibilityCheck(
            current_schema_revision=self.current_schema_revision,
            target_schema_revision=self.target_schema_revision,
            irreversible_migrations_applied=tuple(self.irreversible_migrations_applied),
            compatible=self.compatible,
        )


class ComponentVersionCompatibilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    current_version: str = Field(min_length=1, max_length=64)
    target_version: str = Field(min_length=1, max_length=64)
    compatible: bool
    incompatibility_reason: str | None = None

    def to_domain(self) -> ComponentVersionCompatibility:
        return ComponentVersionCompatibility(
            component=self.component,
            current_version=self.current_version,
            target_version=self.target_version,
            compatible=self.compatible,
            incompatibility_reason=self.incompatibility_reason,
        )


class BootstrapRollbackPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1, max_length=128)
    release_id: str = Field(min_length=1, max_length=128)
    target_release_id: str = Field(min_length=1, max_length=128)
    support: RollbackSupportInput
    schema_check: SchemaCompatibilityCheckInput
    component_compatibility: list[ComponentVersionCompatibilityInput] = Field(default_factory=list)
    configuration_rollback_independent: bool
    secret_rollback_independent: bool
    artifacts_available_until: datetime


class BootstrapRollbackAttemptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str = Field(min_length=1, max_length=128)
    started_at: datetime
    outcome: RollbackOutcome
    post_rollback_health_check_passed: bool
    post_rollback_security_check_passed: bool
    failure_recovery_reference: str | None = None


class RollbackSupportData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: str
    application_rollback_supported: bool
    data_rollback_supported: bool
    unsupported_rationale: str | None


class SchemaCompatibilityCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_schema_revision: str
    target_schema_revision: str
    irreversible_migrations_applied: list[str]
    compatible: bool


class ComponentVersionCompatibilityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    current_version: str
    target_version: str
    compatible: bool
    incompatibility_reason: str | None


class BootstrapRollbackPlanData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    release_id: str
    target_release_id: str
    support: RollbackSupportData
    schema_check: SchemaCompatibilityCheckData
    component_compatibility: list[ComponentVersionCompatibilityData]
    configuration_rollback_independent: bool
    secret_rollback_independent: bool
    artifacts_available_until: datetime
    generated_at: datetime
    is_permitted: bool

    @classmethod
    def from_domain(cls, plan: RollbackPlan) -> BootstrapRollbackPlanData:
        return cls(
            plan_id=plan.plan_id,
            release_id=plan.release_id,
            target_release_id=plan.target_release_id,
            support=RollbackSupportData(
                release_id=plan.support.release_id,
                application_rollback_supported=plan.support.application_rollback_supported,
                data_rollback_supported=plan.support.data_rollback_supported,
                unsupported_rationale=plan.support.unsupported_rationale,
            ),
            schema_check=SchemaCompatibilityCheckData(
                current_schema_revision=plan.schema_check.current_schema_revision,
                target_schema_revision=plan.schema_check.target_schema_revision,
                irreversible_migrations_applied=list(
                    plan.schema_check.irreversible_migrations_applied
                ),
                compatible=plan.schema_check.compatible,
            ),
            component_compatibility=[
                ComponentVersionCompatibilityData(
                    component=item.component,
                    current_version=item.current_version,
                    target_version=item.target_version,
                    compatible=item.compatible,
                    incompatibility_reason=item.incompatibility_reason,
                )
                for item in plan.component_compatibility
            ],
            configuration_rollback_independent=plan.configuration_rollback_independent,
            secret_rollback_independent=plan.secret_rollback_independent,
            artifacts_available_until=plan.artifacts_available_until,
            generated_at=plan.generated_at,
            is_permitted=plan.is_permitted,
        )


class BootstrapRollbackAttemptData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    plan_id: str
    started_at: datetime
    completed_at: datetime
    outcome: RollbackOutcome
    post_rollback_health_check_passed: bool
    post_rollback_security_check_passed: bool
    failure_recovery_reference: str | None

    @classmethod
    def from_domain(cls, attempt: RollbackAttempt) -> BootstrapRollbackAttemptData:
        return cls(
            attempt_id=attempt.attempt_id,
            plan_id=attempt.plan_id,
            started_at=attempt.started_at,
            completed_at=attempt.completed_at,
            outcome=attempt.outcome,
            post_rollback_health_check_passed=attempt.post_rollback_health_check_passed,
            post_rollback_security_check_passed=attempt.post_rollback_security_check_passed,
            failure_recovery_reference=attempt.failure_recovery_reference,
        )


class BootstrapRollbackPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapRollbackPlanData
    meta: ResponseMeta


class BootstrapRollbackAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BootstrapRollbackAttemptData
    meta: ResponseMeta
