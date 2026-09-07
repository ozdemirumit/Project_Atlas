from __future__ import annotations

import pytest

from atlas.modules.release.domain.verification_rollback import (
    DeploymentOutcome,
    PostDeploymentCheckKind,
    PostDeploymentVerificationReport,
    PostDeploymentVerificationResult,
    RollbackExecution,
    unknown_deployment_outcome_pauses_further_rollout,
)


def full_results(
    outcome: DeploymentOutcome = DeploymentOutcome.SUCCESS,
) -> tuple[PostDeploymentVerificationResult, ...]:
    return tuple(
        PostDeploymentVerificationResult(check=check, outcome=outcome, detail="checked")
        for check in PostDeploymentCheckKind
    )


def test_unknown_outcome_pauses_rollout() -> None:
    assert unknown_deployment_outcome_pauses_further_rollout(DeploymentOutcome.UNKNOWN) is True


def test_success_outcome_does_not_pause_rollout() -> None:
    assert unknown_deployment_outcome_pauses_further_rollout(DeploymentOutcome.SUCCESS) is False


def test_verification_report_requires_every_check_kind() -> None:
    with pytest.raises(ValueError, match="every check kind"):
        PostDeploymentVerificationReport(
            release_reference="release.1.5.0",
            results=(
                PostDeploymentVerificationResult(
                    check=PostDeploymentCheckKind.BACKUP_AND_ROLLBACK_READINESS,
                    outcome=DeploymentOutcome.SUCCESS,
                    detail="checked",
                ),
            ),
        )


def test_should_pause_rollout_true_when_any_unknown() -> None:
    report = PostDeploymentVerificationReport(
        release_reference="release.1.5.0", results=full_results(DeploymentOutcome.UNKNOWN)
    )
    assert report.should_pause_rollout is True


def test_should_pause_rollout_false_when_all_success() -> None:
    report = PostDeploymentVerificationReport(
        release_reference="release.1.5.0", results=full_results(DeploymentOutcome.SUCCESS)
    )
    assert report.should_pause_rollout is False


def rollback(**overrides: object) -> RollbackExecution:
    defaults: dict[str, object] = {
        "release_reference": "release.1.5.0",
        "rollback_criteria_reference": "rollout-plan.1.5.0#rollback-criteria",
        "prior_signed_artifact_reference": "manifest.release.1.4.2",
        "data_and_schema_compatibility_checked": True,
        "in_flight_effects_reconciled": True,
        "compatibility_preserved": True,
        "production_change_authority_reference": "production-change.rollback.1.5.0",
        "post_rollback_verification_reference": "verification.rollback.1.5.0",
        "incident_review_reference": "incident-review.1.5.0",
    }
    defaults.update(overrides)
    return RollbackExecution(**defaults)  # type: ignore[arg-type]


def test_rollback_accepts_valid_state() -> None:
    assert rollback().release_reference == "release.1.5.0"


def test_rollback_requires_compatibility_checked() -> None:
    with pytest.raises(ValueError, match="data and schema compatibility is checked"):
        rollback(data_and_schema_compatibility_checked=False)


def test_rollback_requires_post_rollback_verification() -> None:
    with pytest.raises(ValueError, match="post-rollback verification"):
        rollback(post_rollback_verification_reference="")


def test_rollback_requires_incident_review() -> None:
    with pytest.raises(ValueError, match="incident review is mandatory"):
        rollback(incident_review_reference="")
