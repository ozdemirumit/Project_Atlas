"""ATLAS-059 SS24/SS25: post-deployment verification and rollback/forward recovery."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PostDeploymentCheckKind(StrEnum):
    """SS24's eight post-deployment verification checks."""

    RELEASE_CONFIGURATION_SCHEMA_MODEL_CONNECTOR_AND_POLICY_VERSIONS = (
        "release_configuration_schema_model_connector_and_policy_versions"
    )
    IDENTITY_AUTHORIZATION_POLICY_APPROVAL_AND_AUDIT_HEALTH = (
        "identity_authorization_policy_approval_and_audit_health"
    )
    API_UI_WORKFLOW_CONNECTOR_RETRIEVAL_AND_MODEL_SMOKE_TESTS = (
        "api_ui_workflow_connector_retrieval_and_model_smoke_tests"
    )
    DATA_MIGRATION_AND_PROJECTION_RECONCILIATION = "data_migration_and_projection_reconciliation"
    LOGS_METRICS_TRACES_ALERTS_AND_EXTERNAL_INTEGRATIONS = (
        "logs_metrics_traces_alerts_and_external_integrations"
    )
    BACKUP_AND_ROLLBACK_READINESS = "backup_and_rollback_readiness"
    NO_UNEXPECTED_PUBLIC_EGRESS_OR_SECRET_EXPOSURE = (
        "no_unexpected_public_egress_or_secret_exposure"
    )
    REPRESENTATIVE_USER_JOURNEY_AND_SERVICE_IMPACT = (
        "representative_user_journey_and_service_impact"
    )


class DeploymentOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


def unknown_deployment_outcome_pauses_further_rollout(outcome: DeploymentOutcome) -> bool:
    """SS24: "unknown deployment outcome pauses further rollout.\""""
    return outcome is DeploymentOutcome.UNKNOWN


@dataclass(frozen=True, slots=True)
class PostDeploymentVerificationResult:
    check: PostDeploymentCheckKind
    outcome: DeploymentOutcome
    detail: str

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("a post-deployment verification result requires a detail")


@dataclass(frozen=True, slots=True)
class PostDeploymentVerificationReport:
    release_reference: str
    results: tuple[PostDeploymentVerificationResult, ...]

    def __post_init__(self) -> None:
        if not self.release_reference.strip():
            raise ValueError("a post-deployment verification report requires a release reference")
        checks_covered = {result.check for result in self.results}
        if checks_covered != set(PostDeploymentCheckKind):
            raise ValueError("a post-deployment verification report requires every check kind")

    @property
    def should_pause_rollout(self) -> bool:
        return any(
            result.outcome in (DeploymentOutcome.UNKNOWN, DeploymentOutcome.FAILURE)
            for result in self.results
        )


@dataclass(frozen=True, slots=True)
class RollbackExecution:
    """SS25's declared elements. Every SS25 requirement phrased as an absolute ("is checked",
    "are reconciled", "is preserved", "is mandatory") is a construction-time guarantee here."""

    release_reference: str
    rollback_criteria_reference: str
    prior_signed_artifact_reference: str
    data_and_schema_compatibility_checked: bool
    in_flight_effects_reconciled: bool
    compatibility_preserved: bool
    production_change_authority_reference: str
    post_rollback_verification_reference: str
    incident_review_reference: str

    def __post_init__(self) -> None:
        if not self.release_reference.strip():
            raise ValueError("a rollback execution requires a release reference")
        if not self.rollback_criteria_reference.strip():
            raise ValueError(
                "SS25: rollback criteria are declared before rollout -- a reference is required"
            )
        if not self.prior_signed_artifact_reference.strip():
            raise ValueError("SS25: prior signed artifacts remain available")
        if not self.data_and_schema_compatibility_checked:
            raise ValueError("SS25: data and schema compatibility is checked")
        if not self.in_flight_effects_reconciled:
            raise ValueError(
                "SS25: in-flight workflows, approvals, connectors, and external effects are "
                "reconciled"
            )
        if not self.compatibility_preserved:
            raise ValueError(
                "SS25: model, prompt, agent, policy, runbook, and connector compatibility is "
                "preserved"
            )
        if not self.production_change_authority_reference.strip():
            raise ValueError("SS25: rollback receives required production change authority")
        if not self.post_rollback_verification_reference.strip():
            raise ValueError("SS25: post-rollback verification ... is mandatory")
        if not self.incident_review_reference.strip():
            raise ValueError("SS25: ... incident review is mandatory")
