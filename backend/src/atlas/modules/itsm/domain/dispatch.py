"""ATLAS-036: outbound dispatch authorization.

This is the piece the pass-2 audit found missing: `reports.domain.models.ItsmHandoffDraft` is
structurally forbidden from ever carrying `dispatch_authorized=True` (its own `__post_init__`
raises if it does) since preparing a draft is not itsm's decision to make. Every readiness type
already in this module (`ItsmReadinessAssessment`, `ItsmSandboxOnboardingReadiness`) is equally
forbidden -- `ItsmSandboxOnboardingReadiness.production_ready` can never be True by construction.
None of those objects can authorize a dispatch; they can only prove the environment is onboarded
and trustworthy. `ItsmOutboundDispatchAuthorization` is the one place all of that meets the one
fact none of those objects have access to -- that a human completed review of this specific
draft (SS9's "consequential external submission requires the role and review defined by
policy") -- and only then can compose an actual dispatch decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.itsm.domain.models import (
    ItsmAllowedOperation,
    ItsmIntegrationProfile,
    ItsmProfileLifecycle,
    ItsmSandboxOnboardingReadiness,
    ItsmSandboxOnboardingState,
)
from atlas.modules.itsm.domain.operations import ItsmOperationDirection, operation_direction
from atlas.modules.reports.domain.models import ItsmHandoffDraft


@dataclass(frozen=True, slots=True)
class ItsmOutboundDispatchAuthorization:
    authorization_id: str
    profile_id: str
    operation: ItsmAllowedOperation
    draft_id: str
    draft_idempotency_key: str
    human_reviewer_id: str | None
    human_review_completed_at: datetime | None
    dispatch_authorized: bool
    denial_reason: str | None
    decided_at: datetime

    def __post_init__(self) -> None:
        for value in (
            self.authorization_id,
            self.profile_id,
            self.draft_id,
            self.draft_idempotency_key,
        ):
            validate_stable_identifier(value, "ITSM outbound dispatch authorization identifier")
        if self.human_reviewer_id is not None:
            validate_stable_identifier(self.human_reviewer_id, "ITSM dispatch human reviewer")
        if (
            self.human_review_completed_at is not None
            and self.human_review_completed_at.tzinfo is None
        ):
            raise ValueError("ITSM dispatch human review completion time must be timezone-aware")
        if self.decided_at.tzinfo is None:
            raise ValueError("an ITSM dispatch authorization decision time must be timezone-aware")
        if self.dispatch_authorized == (self.denial_reason is not None):
            raise ValueError(
                "an ITSM dispatch authorization's outcome and denial reason must agree"
            )
        if self.dispatch_authorized and (
            self.human_reviewer_id is None or self.human_review_completed_at is None
        ):
            raise ValueError("an authorized ITSM dispatch requires a completed human review")


def _first_denial_reason(
    *,
    profile: ItsmIntegrationProfile,
    onboarding_readiness: ItsmSandboxOnboardingReadiness,
    operation: ItsmAllowedOperation,
    draft: ItsmHandoffDraft,
    human_reviewer_id: str | None,
    human_review_completed_at: datetime | None,
) -> str | None:
    if profile.lifecycle is not ItsmProfileLifecycle.ACTIVE:
        return "itsm_dispatch_profile_not_active"
    if operation_direction(operation) is not ItsmOperationDirection.OUTBOUND:
        return "itsm_dispatch_operation_not_outbound"
    if operation not in profile.allowed_operations:
        return "itsm_dispatch_operation_not_permitted"
    if onboarding_readiness.profile_id != profile.profile_id:
        return "itsm_dispatch_readiness_profile_mismatch"
    if onboarding_readiness.state is not ItsmSandboxOnboardingState.READY:
        return "itsm_dispatch_onboarding_not_ready"
    if not onboarding_readiness.sandbox_onboarding_ready:
        return "itsm_dispatch_onboarding_not_ready"
    if draft.dispatch_authorized or draft.external_record_mutated:
        return "itsm_dispatch_draft_already_authorized"
    if human_reviewer_id is None or human_review_completed_at is None:
        return "itsm_dispatch_human_review_incomplete"
    return None


def authorize_outbound_dispatch(
    *,
    authorization_id: str,
    profile: ItsmIntegrationProfile,
    onboarding_readiness: ItsmSandboxOnboardingReadiness,
    operation: ItsmAllowedOperation,
    draft: ItsmHandoffDraft,
    human_reviewer_id: str | None,
    human_review_completed_at: datetime | None,
    decided_at: datetime,
) -> ItsmOutboundDispatchAuthorization:
    """Compose independently-verified facts into one dispatch decision. This function cannot
    forge any of its inputs -- it can only deny on the first unmet condition, or authorize once
    every condition already held."""
    denial = _first_denial_reason(
        profile=profile,
        onboarding_readiness=onboarding_readiness,
        operation=operation,
        draft=draft,
        human_reviewer_id=human_reviewer_id,
        human_review_completed_at=human_review_completed_at,
    )
    authorized = denial is None
    return ItsmOutboundDispatchAuthorization(
        authorization_id=authorization_id,
        profile_id=profile.profile_id,
        operation=operation,
        draft_id=draft.draft_id,
        draft_idempotency_key=draft.idempotency_key,
        human_reviewer_id=human_reviewer_id,
        human_review_completed_at=human_review_completed_at,
        dispatch_authorized=authorized,
        denial_reason=denial,
        decided_at=decided_at,
    )
