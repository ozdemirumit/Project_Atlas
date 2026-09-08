"""ATLAS-036 SS9: the application service that makes `dispatch.authorize_outbound_dispatch`
reachable.

The domain function is real and fully tested but was never wired to anything -- no application
service composed an `ItsmIntegrationProfile` + `ItsmSandboxOnboardingReadiness` + an accepted
`ItsmHandoffHumanReview` into a call to it. This service is exactly that composition, following
the same idempotency-key/fingerprint-replay/version-conflict/audit conventions established by
`ItsmIntegrationService` and `ItsmHandoffReviewService`. It does not perform, or authorize
anything downstream from, the actual dispatch -- SS9 draws a hard line between deciding and
acting, and nothing acts on this decision anywhere in this codebase yet.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.itsm.application.dispatch_audit import (
    ItsmAuditEventKind,
    record_itsm_integration_event,
)
from atlas.modules.itsm.application.dispatch_authorization_ports import (
    ItsmDispatchAuthorizationRepository,
    StoredItsmDispatchAuthorization,
)
from atlas.modules.itsm.application.service import ItsmIntegrationError, ItsmIntegrationService
from atlas.modules.itsm.domain.dispatch import (
    ItsmOutboundDispatchAuthorization,
    authorize_outbound_dispatch,
)
from atlas.modules.itsm.domain.models import ItsmAllowedOperation
from atlas.modules.reports.application.handoff_review_service import (
    ItsmHandoffReviewError,
    ItsmHandoffReviewService,
)
from atlas.modules.reports.domain.handoff_review import ItsmHandoffReviewOutcome

ITSM_DISPATCH_AUTHORIZATION_SCHEMA = "atlas.itsm-outbound-dispatch-authorization.v1"


class ItsmDispatchAuthorizationError(ItsmIntegrationError):
    """Deliberately a subtype of `ItsmIntegrationError` so the existing itsm-integrations route's
    error-code-to-HTTP-status mapper handles it without needing a parallel mapper."""


@dataclass(frozen=True, slots=True)
class ItsmDispatchAuthorizationResult:
    authorization: ItsmOutboundDispatchAuthorization
    reused: bool


class ItsmDispatchAuthorizationService:
    def __init__(
        self,
        *,
        integration_service: ItsmIntegrationService,
        handoff_review_service: ItsmHandoffReviewService,
        repository: ItsmDispatchAuthorizationRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._integration_service = integration_service
        self._handoff_review_service = handoff_review_service
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()

    @property
    def repository(self) -> ItsmDispatchAuthorizationRepository:
        return self._repository

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        profile_id: str,
        expected_profile_version: int,
        report_id: str,
        handoff_draft_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ItsmDispatchAuthorizationResult:
        try:
            return await self._authorize(
                actor=actor,
                profile_id=profile_id,
                expected_profile_version=expected_profile_version,
                report_id=report_id,
                handoff_draft_id=handoff_draft_id,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
        except ItsmIntegrationError as error:
            await self._audit_denied(
                actor,
                profile_id=profile_id,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                result_code=str(error),
            )
            raise

    async def _authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        profile_id: str,
        expected_profile_version: int,
        report_id: str,
        handoff_draft_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ItsmDispatchAuthorizationResult:
        self._require_human(actor)
        if not 8 <= len(idempotency_key) <= 128:
            raise ItsmDispatchAuthorizationError("itsm_dispatch_authorization_request_invalid")
        if expected_profile_version < 1:
            raise ItsmDispatchAuthorizationError("itsm_dispatch_authorization_request_invalid")

        fingerprint = self._digest(
            {
                "requested_by": actor.subject_id,
                "profile_id": profile_id,
                "expected_profile_version": expected_profile_version,
                "report_id": report_id,
                "handoff_draft_id": handoff_draft_id,
            }
        )
        replay = await self._repository.get_by_idempotency_key(
            requested_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            if replay.request_fingerprint != fingerprint:
                raise ItsmDispatchAuthorizationError(
                    "itsm_dispatch_authorization_idempotency_conflict"
                )
            return ItsmDispatchAuthorizationResult(authorization=replay.authorization, reused=True)

        profile = await self._integration_service.get(
            actor=actor, profile_id=profile_id, correlation_id=correlation_id
        )
        if profile.version != expected_profile_version:
            raise ItsmDispatchAuthorizationError(
                "itsm_dispatch_authorization_profile_version_conflict"
            )
        readiness = await self._integration_service.sandbox_onboarding_readiness(
            actor=actor, profile_id=profile_id, correlation_id=correlation_id
        )

        try:
            report, review = await self._handoff_review_service.get_handoff_and_review(
                actor=actor,
                report_id=report_id,
                handoff_draft_id=handoff_draft_id,
                correlation_id=correlation_id,
            )
        except ItsmHandoffReviewError as error:
            raise ItsmDispatchAuthorizationError(error.code) from error

        if (
            report.organization_id != profile.organization_id
            or report.environment_id != profile.environment_id
            or report.site_id != profile.site_id
        ):
            raise ItsmDispatchAuthorizationError("itsm_dispatch_authorization_scope_mismatch")

        handoff = report.itsm_handoff
        if handoff is None or handoff.draft_id != handoff_draft_id:
            raise ItsmDispatchAuthorizationError("itsm_dispatch_authorization_not_found")

        if (
            review is None
            or not review.review_complete
            or review.outcome is not ItsmHandoffReviewOutcome.ACCEPT
        ):
            raise ItsmDispatchAuthorizationError("itsm_dispatch_review_not_accepted")

        try:
            operation = ItsmAllowedOperation(handoff.operation)
        except ValueError as error:
            raise ItsmDispatchAuthorizationError(
                "itsm_dispatch_authorization_operation_unsupported"
            ) from error

        decided_at = self._clock()
        digest = self._digest(
            {
                "schema_version": ITSM_DISPATCH_AUTHORIZATION_SCHEMA,
                "requested_by": actor.subject_id,
                "profile_id": profile.profile_id,
                "profile_version": profile.version,
                "profile_digest": profile.canonical_digest,
                "report_id": report.report_id,
                "report_version": report.version,
                "handoff_draft_id": handoff.draft_id,
                "handoff_idempotency_key": handoff.idempotency_key,
                "operation": operation.value,
                "review_id": review.review_id,
                "decided_at": decided_at.isoformat(),
            }
        )
        try:
            authorization = authorize_outbound_dispatch(
                authorization_id=f"itsm-dispatch-authorization.{digest[:24]}",
                profile=profile,
                onboarding_readiness=readiness,
                operation=operation,
                draft=handoff,
                human_reviewer_id=review.reviewer_id,
                human_review_completed_at=review.decided_at,
                decided_at=decided_at,
            )
        except ValueError as error:
            raise ItsmDispatchAuthorizationError(
                "itsm_dispatch_authorization_request_invalid"
            ) from error

        stored = StoredItsmDispatchAuthorization(
            authorization=authorization,
            requested_by=actor.subject_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        async with self._lock:
            raced = await self._repository.get_by_idempotency_key(
                requested_by=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is not None:
                if raced.request_fingerprint != fingerprint:
                    raise ItsmDispatchAuthorizationError(
                        "itsm_dispatch_authorization_idempotency_conflict"
                    )
                result = ItsmDispatchAuthorizationResult(
                    authorization=raced.authorization, reused=True
                )
            elif not await self._repository.add(stored):
                raced_again = await self._repository.get_by_idempotency_key(
                    requested_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced_again is None or raced_again.request_fingerprint != fingerprint:
                    raise ItsmDispatchAuthorizationError(
                        "itsm_dispatch_authorization_state_conflict"
                    )
                result = ItsmDispatchAuthorizationResult(
                    authorization=raced_again.authorization, reused=True
                )
            else:
                result = ItsmDispatchAuthorizationResult(authorization=authorization, reused=False)

        await record_itsm_integration_event(
            self._audit_sink,
            event_kind=ItsmAuditEventKind.STATE_TRANSITION,
            profile_reference=profile.profile_id,
            actor_identity=actor.subject_id,
            is_automation=actor.kind is not SubjectKind.HUMAN,
            outcome="succeeded" if authorization.dispatch_authorized else "denied",
            external_record_id=None,
            external_source_version=None,
            idempotency_key=idempotency_key,
            detail_references=(authorization.authorization_id, report.report_id, handoff.draft_id),
            occurred_at=decided_at,
            correlation_id=correlation_id,
            event_id=f"evt_{uuid4().hex}",
            producer="project-atlas-api",
            producer_version=__version__,
        )
        return result

    async def close(self) -> None:
        await self._repository.close()

    async def _audit_denied(
        self,
        actor: AuthenticatedSubject,
        *,
        profile_id: str,
        correlation_id: str,
        idempotency_key: str,
        result_code: str,
    ) -> None:
        await record_itsm_integration_event(
            self._audit_sink,
            event_kind=ItsmAuditEventKind.STATE_TRANSITION,
            profile_reference=profile_id,
            actor_identity=actor.subject_id,
            is_automation=actor.kind is not SubjectKind.HUMAN,
            outcome="denied",
            external_record_id=None,
            external_source_version=None,
            idempotency_key=idempotency_key,
            detail_references=(result_code,),
            occurred_at=self._clock(),
            correlation_id=correlation_id,
            event_id=f"evt_{uuid4().hex}",
            producer="project-atlas-api",
            producer_version=__version__,
        )

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ItsmDispatchAuthorizationError("itsm_dispatch_authorization_human_required")

    @staticmethod
    def _digest(value: object) -> str:
        return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
