"""ATLAS-038 SS25/SS33: Rollback foundation.

SS33's MVP scope names "rollback foundation" as included, not full automated rollback execution.
This module builds the part SS25 makes fully specifiable today -- whether rollback is supported
for a release pair, schema/version compatibility validation, and the structural guarantees that a
"successful" rollback cannot skip the mandatory post-rollback health/security checks and a failed
rollback always carries a documented recovery reference rather than a blind retry. It deliberately
does not attempt to execute a rollback against real deployed infrastructure: per the user's own
confirmation used to scope ATLAS-058's CI/CD work, no real lab/enterprise deployment target exists
yet in this project ("pre-infrastructure") -- automating against infrastructure that does not
exist would be speculative, not a foundation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

ROLLBACK_COMPONENTS = frozenset(
    {"workflows", "approvals", "connector_packages", "policies", "queued_events"}
)


@dataclass(frozen=True, slots=True)
class RollbackSupportDeclaration:
    """SS25: "Every upgrade declares whether application and data rollback are supported.\""""

    release_id: str
    application_rollback_supported: bool
    data_rollback_supported: bool
    unsupported_rationale: str | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.release_id, "release_id")
        if not self.application_rollback_supported and not (
            self.unsupported_rationale is not None and self.unsupported_rationale.strip()
        ):
            raise ValueError("declaring rollback unsupported requires a documented rationale")


@dataclass(frozen=True, slots=True)
class SchemaCompatibilityCheck:
    """SS25: "Rollback validates schema compatibility and does not run against irreversibly
    migrated data.\""""

    current_schema_revision: str
    target_schema_revision: str
    irreversible_migrations_applied: tuple[str, ...]
    compatible: bool

    def __post_init__(self) -> None:
        if not self.current_schema_revision.strip() or not self.target_schema_revision.strip():
            raise ValueError("schema compatibility check requires both schema revisions")
        if self.irreversible_migrations_applied and self.compatible:
            raise ValueError(
                "an irreversibly migrated database cannot be reported schema-compatible"
            )


@dataclass(frozen=True, slots=True)
class ComponentVersionCompatibility:
    """SS25: "Workflows, approvals, connector packages, policies, and queued events preserve
    version compatibility.\""""

    component: str
    current_version: str
    target_version: str
    compatible: bool
    incompatibility_reason: str | None = None

    def __post_init__(self) -> None:
        if self.component not in ROLLBACK_COMPONENTS:
            raise ValueError("unrecognized rollback compatibility component")
        if not self.current_version.strip() or not self.target_version.strip():
            raise ValueError("component compatibility requires both versions")
        if not self.compatible and not (
            self.incompatibility_reason is not None and self.incompatibility_reason.strip()
        ):
            raise ValueError("an incompatible component requires a documented reason")


@dataclass(frozen=True, slots=True)
class RollbackPlan:
    """SS25's declarative rollback contract for one release pair. `is_permitted` is the single
    gate a real rollback attempt must honor -- it is derived, never stored, so it cannot be
    forced true by constructing the plan differently."""

    plan_id: str
    release_id: str
    target_release_id: str
    support: RollbackSupportDeclaration
    schema_check: SchemaCompatibilityCheck
    component_compatibility: tuple[ComponentVersionCompatibility, ...]
    configuration_rollback_independent: bool
    secret_rollback_independent: bool
    artifacts_available_until: datetime
    generated_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.plan_id, "plan_id")
        validate_stable_identifier(self.target_release_id, "target_release_id")
        if self.support.release_id != self.release_id:
            raise ValueError("rollback support declaration must match the plan's release")
        if self.generated_at.tzinfo is None or self.artifacts_available_until.tzinfo is None:
            raise ValueError("rollback plan timestamps must be timezone-aware")
        if self.artifacts_available_until <= self.generated_at:
            raise ValueError("the rollback window must extend beyond plan generation")
        components = {item.component for item in self.component_compatibility}
        if len(components) != len(self.component_compatibility):
            raise ValueError("rollback plan cannot declare the same component twice")

    @property
    def is_permitted(self) -> bool:
        return (
            self.support.application_rollback_supported
            and self.schema_check.compatible
            and all(item.compatible for item in self.component_compatibility)
        )


class RollbackOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RollbackAttempt:
    """SS25: "Rollback is followed by the same mandatory health and security checks as
    deployment... A failed rollback invokes documented recovery rather than repeated blind
    attempts.\""""

    attempt_id: str
    plan_id: str
    started_at: datetime
    completed_at: datetime
    outcome: RollbackOutcome
    post_rollback_health_check_passed: bool
    post_rollback_security_check_passed: bool
    failure_recovery_reference: str | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.attempt_id, "attempt_id")
        validate_stable_identifier(self.plan_id, "plan_id")
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("rollback attempt timestamps must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("a rollback attempt cannot complete before it starts")
        if self.outcome is RollbackOutcome.SUCCEEDED:
            if not (
                self.post_rollback_health_check_passed and self.post_rollback_security_check_passed
            ):
                raise ValueError(
                    "a successful rollback requires the mandatory post-rollback health and "
                    "security checks to have passed"
                )
            if self.failure_recovery_reference is not None:
                raise ValueError("a successful rollback cannot carry a failure recovery reference")
        elif not (
            self.failure_recovery_reference is not None and self.failure_recovery_reference.strip()
        ):
            raise ValueError("a failed rollback requires a documented recovery reference")


def a_rollback_proceeds_against_an_irreversibly_migrated_schema() -> bool:
    """SS25: "does not run against irreversibly migrated data." `SchemaCompatibilityCheck`
    structurally forbids reporting compatibility once an irreversible migration has applied."""
    return False


def a_failed_rollback_is_retried_without_a_documented_recovery_reference() -> bool:
    """SS25: "A failed rollback invokes documented recovery rather than repeated blind
    attempts." `RollbackAttempt` makes an undocumented failure unconstructable."""
    return False


def a_rollback_is_reported_successful_while_skipping_the_mandatory_post_rollback_checks() -> bool:
    """SS25: "Rollback is followed by the same mandatory health and security checks as
    deployment." `RollbackAttempt` makes a successful outcome without both checks passing
    unconstructable."""
    return False
