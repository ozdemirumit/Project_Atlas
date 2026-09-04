from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.guardrails.domain.models import GuardrailInvariant, GuardrailOutcome
from atlas.modules.guardrails.domain.safe_failure import (
    GuardrailException,
    SafeFailureCondition,
    required_outcome_for,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def exception(**overrides: object) -> GuardrailException:
    defaults: dict[str, object] = {
        "exception_id": "guardrail-exception.example",
        "rule_id": "guardrail-rule.example-platform-minimum",
        "requested_change": "Raise the input size limit for this connector.",
        "business_justification": "Large diagnostic bundles exceed the current limit.",
        "technical_justification": "The bundle format is inherently large but bounded.",
        "risk_description": "Slightly larger attack surface for oversized-payload abuse.",
        "compensating_controls": ("Additional rate limiting on this endpoint.",),
        "requester_identity_id": "subject.requester",
        "security_reviewer_identity_id": "subject.security-reviewer",
        "approver_identity_id": "subject.approver",
        "target_id": "target.example",
        "environment_id": "environment.production",
        "starts_at": NOW,
        "expires_at": NOW + timedelta(days=30),
        "automatic_rollback": True,
        "monitoring_plan": "Alert if the new limit is exceeded more than once per day.",
    }
    defaults.update(overrides)
    return GuardrailException(**defaults)  # type: ignore[arg-type]


def test_every_condition_has_a_required_outcome() -> None:
    for condition in SafeFailureCondition:
        assert required_outcome_for(condition) in GuardrailOutcome


@pytest.mark.parametrize(
    "condition",
    [
        SafeFailureCondition.IDENTITY_OR_AUTHORIZATION_UNCERTAIN,
        SafeFailureCondition.POLICY_OR_GUARDRAIL_SERVICE_UNAVAILABLE,
        SafeFailureCondition.AUDIT_DURABILITY_UNAVAILABLE,
        SafeFailureCondition.TARGET_AMBIGUOUS_OR_SCOPE_MISMATCH,
        SafeFailureCondition.MODEL_UNAVAILABLE_OR_INVALID_OUTPUT,
        SafeFailureCondition.APPROVAL_EXPIRED_OR_MISMATCHED,
        SafeFailureCondition.GENERATED_ARTIFACT_UNAPPROVED,
        SafeFailureCondition.CROSS_BOUNDARY_ACCESS_SIGNAL,
    ],
)
def test_the_most_severe_conditions_require_block(condition: SafeFailureCondition) -> None:
    assert required_outcome_for(condition) is GuardrailOutcome.BLOCK


def test_prompt_injection_requires_quarantine() -> None:
    assert (
        required_outcome_for(SafeFailureCondition.PROMPT_INJECTION_SUSPECTED)
        is GuardrailOutcome.QUARANTINE
    )


def test_secret_detected_requires_redact() -> None:
    assert required_outcome_for(SafeFailureCondition.SECRET_DETECTED) is GuardrailOutcome.REDACT


def test_a_well_formed_exception_constructs_cleanly() -> None:
    example = exception()
    assert example.is_active_at(NOW) is True


@pytest.mark.parametrize("invariant", list(GuardrailInvariant))
def test_an_exception_can_never_target_any_invariant(invariant: GuardrailInvariant) -> None:
    with pytest.raises(ValueError, match="non-overridable invariant"):
        exception(rule_id=invariant.value)


def test_requester_and_approver_must_differ() -> None:
    with pytest.raises(ValueError, match="different identities"):
        exception(requester_identity_id="subject.same", approver_identity_id="subject.same")


def test_expires_at_must_be_after_starts_at() -> None:
    with pytest.raises(ValueError, match="later than starts_at"):
        exception(starts_at=NOW, expires_at=NOW - timedelta(days=1))


def test_automatic_rollback_is_required() -> None:
    with pytest.raises(ValueError, match="automatic rollback"):
        exception(automatic_rollback=False)


def test_requires_at_least_one_compensating_control() -> None:
    with pytest.raises(ValueError, match="compensating control"):
        exception(compensating_controls=())


def test_rejects_blank_justifications_and_plans() -> None:
    with pytest.raises(ValueError, match="business justification"):
        exception(business_justification="   ")
    with pytest.raises(ValueError, match="technical justification"):
        exception(technical_justification="   ")
    with pytest.raises(ValueError, match="risk description"):
        exception(risk_description="   ")
    with pytest.raises(ValueError, match="monitoring plan"):
        exception(monitoring_plan="   ")


def test_is_active_at_respects_the_time_window() -> None:
    example = exception(starts_at=NOW, expires_at=NOW + timedelta(days=1))
    assert example.is_active_at(NOW - timedelta(minutes=1)) is False
    assert example.is_active_at(NOW) is True
    assert example.is_active_at(NOW + timedelta(days=1)) is False
