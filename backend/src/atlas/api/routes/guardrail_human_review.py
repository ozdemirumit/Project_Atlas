from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.errors import AtlasError
from atlas.api.guardrail_human_review_schemas import (
    DetectedElementInput,
    GuardrailHumanReviewEnqueueInput,
    GuardrailHumanReviewEntryData,
    GuardrailHumanReviewEntryResponse,
    GuardrailHumanReviewResolutionData,
    GuardrailHumanReviewResolutionResponse,
    GuardrailHumanReviewResolveInput,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_guardrail_human_review_enqueue,
    authorize_guardrail_human_review_resolve,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.guardrails.application.human_review import (
    GuardrailReviewError,
    GuardrailReviewService,
)
from atlas.modules.guardrails.domain.human_review import (
    DetectedElement,
    HumanReviewQueueEntry,
    ReviewerDecision,
)
from atlas.modules.guardrails.domain.models import GuardrailClass
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/guardrails/human-review", tags=["guardrails"])
ENTRY_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(exc: GuardrailReviewError) -> NoReturn:
    status_by_code = {
        "guardrail_review_entry_unavailable": 404,
        "guardrail_review_already_resolved": 409,
        "guardrail_review_decision_not_allowed": 409,
        "guardrail_review_invariant_cannot_be_overturned": 409,
        "guardrail_review_resolution_invalid": 422,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 409),
        code=exc.code,
        title="Guardrail human review unavailable",
        detail="The requested human review operation could not be completed.",
    ) from exc


def _detected_element(item: DetectedElementInput) -> DetectedElement:
    return DetectedElement(kind=item.kind, description=item.description, redacted=item.redacted)


@router.post(
    "/entries/{entry_id}", response_model=GuardrailHumanReviewEntryResponse, status_code=201
)
async def enqueue_human_review_entry(
    entry_id: Annotated[str, ENTRY_ID],
    payload: GuardrailHumanReviewEnqueueInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_guardrail_human_review_enqueue)],
) -> GuardrailHumanReviewEntryResponse:
    now = datetime.now(UTC)
    service: GuardrailReviewService = request.app.state.guardrail_review_service
    try:
        allowed_decisions = tuple(ReviewerDecision(value) for value in payload.allowed_decisions)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="guardrail_review_decision_invalid",
            title="Guardrail human review unavailable",
            detail="One or more allowed decisions are not recognized.",
        ) from error
    try:
        entry = HumanReviewQueueEntry(
            entry_id=entry_id,
            triggered_rule_id=payload.triggered_rule_id,
            safe_rationale=payload.safe_rationale,
            request_reference=payload.request_reference,
            bounded_context_reference=payload.bounded_context_reference,
            detected_elements=tuple(_detected_element(item) for item in payload.detected_elements),
            proposed_disposition=payload.proposed_disposition,
            proposed_impact=payload.proposed_impact,
            related_policy_reference=payload.related_policy_reference,
            related_approval_reference=payload.related_approval_reference,
            related_connector_reference=payload.related_connector_reference,
            related_audit_reference=payload.related_audit_reference,
            allowed_decisions=allowed_decisions,
            created_at=now,
        )
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="guardrail_review_entry_invalid",
            title="Guardrail human review unavailable",
            detail="The human review queue entry is not valid.",
        ) from error
    try:
        saved = await service.enqueue(entry, correlation_id=str(request.state.correlation_id))
    except GuardrailReviewError as error:
        _raise(error)
    return GuardrailHumanReviewEntryResponse(
        data=GuardrailHumanReviewEntryData.from_domain(saved),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post(
    "/entries/{entry_id}/resolutions",
    response_model=GuardrailHumanReviewResolutionResponse,
    status_code=201,
)
async def resolve_human_review_entry(
    entry_id: Annotated[str, ENTRY_ID],
    payload: GuardrailHumanReviewResolveInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_guardrail_human_review_resolve)],
) -> GuardrailHumanReviewResolutionResponse:
    now = datetime.now(UTC)
    service: GuardrailReviewService = request.app.state.guardrail_review_service
    try:
        decision = ReviewerDecision(payload.decision)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="guardrail_review_decision_invalid",
            title="Guardrail human review unavailable",
            detail="The decision is not recognized.",
        ) from error
    try:
        guardrail_class = GuardrailClass(payload.triggering_guardrail_class)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="guardrail_review_guardrail_class_invalid",
            title="Guardrail human review unavailable",
            detail="The triggering guardrail class is not recognized.",
        ) from error
    try:
        resolution = await service.resolve(
            entry_id=entry_id,
            decision=decision,
            reviewed_by=subject.subject_id,
            rationale=payload.rationale,
            triggering_guardrail_class=guardrail_class,
            correlation_id=str(request.state.correlation_id),
        )
    except GuardrailReviewError as error:
        _raise(error)
    return GuardrailHumanReviewResolutionResponse(
        data=GuardrailHumanReviewResolutionData.from_domain(resolution),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
