from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.platform.domain.bootstrap_rollback import (
    ComponentVersionCompatibility,
    RollbackAttempt,
    RollbackOutcome,
    RollbackPlan,
    RollbackSupportDeclaration,
    SchemaCompatibilityCheck,
    a_failed_rollback_is_retried_without_a_documented_recovery_reference,
    a_rollback_is_reported_successful_while_skipping_the_mandatory_post_rollback_checks,
    a_rollback_proceeds_against_an_irreversibly_migrated_schema,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _support(**overrides: object) -> RollbackSupportDeclaration:
    values: dict[str, object] = {
        "release_id": "release.atlas.2026.9.0",
        "application_rollback_supported": True,
        "data_rollback_supported": True,
        "unsupported_rationale": None,
    }
    values.update(overrides)
    return RollbackSupportDeclaration(**values)  # type: ignore[arg-type]


def _schema_check(**overrides: object) -> SchemaCompatibilityCheck:
    values: dict[str, object] = {
        "current_schema_revision": "20260907_0170",
        "target_schema_revision": "20260827_0169",
        "irreversible_migrations_applied": (),
        "compatible": True,
    }
    values.update(overrides)
    return SchemaCompatibilityCheck(**values)  # type: ignore[arg-type]


def _component(**overrides: object) -> ComponentVersionCompatibility:
    values: dict[str, object] = {
        "component": "workflows",
        "current_version": "1.2.0",
        "target_version": "1.1.0",
        "compatible": True,
        "incompatibility_reason": None,
    }
    values.update(overrides)
    return ComponentVersionCompatibility(**values)  # type: ignore[arg-type]


def _plan(**overrides: object) -> RollbackPlan:
    values: dict[str, object] = {
        "plan_id": "plan.rollback.primary",
        "release_id": "release.atlas.2026.9.0",
        "target_release_id": "release.atlas.2026.8.0",
        "support": _support(),
        "schema_check": _schema_check(),
        "component_compatibility": (_component(),),
        "configuration_rollback_independent": True,
        "secret_rollback_independent": True,
        "artifacts_available_until": NOW + timedelta(days=7),
        "generated_at": NOW,
    }
    values.update(overrides)
    return RollbackPlan(**values)  # type: ignore[arg-type]


def test_absolute_rules_are_false() -> None:
    assert a_rollback_proceeds_against_an_irreversibly_migrated_schema() is False
    assert a_failed_rollback_is_retried_without_a_documented_recovery_reference() is False
    assert (
        a_rollback_is_reported_successful_while_skipping_the_mandatory_post_rollback_checks()
        is False
    )


def test_unsupported_rollback_requires_a_rationale() -> None:
    with pytest.raises(ValueError, match="documented rationale"):
        _support(application_rollback_supported=False, unsupported_rationale=None)
    declaration = _support(
        application_rollback_supported=False,
        unsupported_rationale="No compatible downgrade path for the storage connector schema.",
    )
    assert declaration.application_rollback_supported is False


def test_irreversible_migration_forbids_reported_compatibility() -> None:
    with pytest.raises(ValueError, match="irreversibly migrated database"):
        _schema_check(irreversible_migrations_applied=("20260907_0170",), compatible=True)
    check = _schema_check(irreversible_migrations_applied=("20260907_0170",), compatible=False)
    assert check.compatible is False


def test_incompatible_component_requires_a_reason() -> None:
    with pytest.raises(ValueError, match="documented reason"):
        _component(compatible=False, incompatibility_reason=None)


def test_unrecognized_component_is_rejected() -> None:
    with pytest.raises(ValueError, match="unrecognized rollback"):
        _component(component="unknown_component")


def test_plan_requires_matching_support_release() -> None:
    with pytest.raises(ValueError, match="must match the plan's release"):
        _plan(support=_support(release_id="release.other"))


def test_plan_requires_the_window_to_extend_beyond_generation() -> None:
    with pytest.raises(ValueError, match="rollback window"):
        _plan(artifacts_available_until=NOW)


def test_plan_forbids_duplicate_components() -> None:
    with pytest.raises(ValueError, match="cannot declare the same component twice"):
        _plan(component_compatibility=(_component(), _component()))


def test_is_permitted_reflects_full_compatibility() -> None:
    assert _plan().is_permitted is True
    assert _plan(schema_check=_schema_check(compatible=False)).is_permitted is False
    assert (
        _plan(
            component_compatibility=(
                _component(compatible=False, incompatibility_reason="Policy schema diverged."),
            )
        ).is_permitted
        is False
    )
    assert (
        _plan(support=_support(data_rollback_supported=False)).is_permitted is True
    )  # application rollback alone still permits the plan; data rollback is tracked separately


def test_successful_attempt_requires_both_mandatory_checks() -> None:
    with pytest.raises(ValueError, match="mandatory post-rollback"):
        RollbackAttempt(
            attempt_id="attempt.rollback.primary",
            plan_id="plan.rollback.primary",
            started_at=NOW,
            completed_at=NOW + timedelta(minutes=10),
            outcome=RollbackOutcome.SUCCEEDED,
            post_rollback_health_check_passed=True,
            post_rollback_security_check_passed=False,
        )


def test_successful_attempt_forbids_a_recovery_reference() -> None:
    with pytest.raises(ValueError, match="cannot carry a failure recovery reference"):
        RollbackAttempt(
            attempt_id="attempt.rollback.primary",
            plan_id="plan.rollback.primary",
            started_at=NOW,
            completed_at=NOW + timedelta(minutes=10),
            outcome=RollbackOutcome.SUCCEEDED,
            post_rollback_health_check_passed=True,
            post_rollback_security_check_passed=True,
            failure_recovery_reference="doc.recovery.001",
        )


def test_failed_attempt_requires_a_recovery_reference() -> None:
    with pytest.raises(ValueError, match="requires a documented recovery reference"):
        RollbackAttempt(
            attempt_id="attempt.rollback.primary",
            plan_id="plan.rollback.primary",
            started_at=NOW,
            completed_at=NOW + timedelta(minutes=10),
            outcome=RollbackOutcome.FAILED,
            post_rollback_health_check_passed=False,
            post_rollback_security_check_passed=False,
        )


def test_attempt_cannot_complete_before_it_starts() -> None:
    with pytest.raises(ValueError, match="cannot complete before it starts"):
        RollbackAttempt(
            attempt_id="attempt.rollback.primary",
            plan_id="plan.rollback.primary",
            started_at=NOW,
            completed_at=NOW - timedelta(minutes=1),
            outcome=RollbackOutcome.FAILED,
            post_rollback_health_check_passed=False,
            post_rollback_security_check_passed=False,
            failure_recovery_reference="doc.recovery.001",
        )
