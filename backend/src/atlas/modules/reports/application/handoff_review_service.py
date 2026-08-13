from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.reports.application.handoff_review_ports import (
    ItsmHandoffReviewRepository,
    TechnicalReportSource,
)
from atlas.modules.reports.domain.handoff_review import (
    ItsmHandoffHumanReview,
    ItsmHandoffReviewOutcome,
    canonical_handoff_digest,
)
from atlas.modules.reports.domain.models import TechnicalReport

ITSM_REVIEWER_ROLE_ID = "role.itsm-reviewer"
ITSM_HANDOFF_REVIEW_SCHEMA = "atlas.itsm-handoff-human-review.v1"


class ItsmHandoffReviewError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ItsmHandoffReviewService:
    def __init__(
        self,
        *,
        report_source: TechnicalReportSource,
        repository: ItsmHandoffReviewRepository,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str = "site.local",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._report_source = report_source
        self._repository = repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._site_id = site_id
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> ItsmHandoffReviewRepository:
        return self._repository

    async def decide(
        self,
        *,
        actor: AuthenticatedSubject,
        report_id: str,
        report_version: int,
        report_digest: str,
        handoff_draft_id: str,
        outcome: ItsmHandoffReviewOutcome,
        rationale: str,
        acknowledged_review_only: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ItsmHandoffHumanReview:
        try:
            return await self._decide(
                actor=actor,
                report_id=report_id,
                report_version=report_version,
                report_digest=report_digest,
                handoff_draft_id=handoff_draft_id,
                outcome=outcome,
                rationale=rationale,
                acknowledged_review_only=acknowledged_review_only,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
        except ItsmHandoffReviewError as error:
            await self._audit(
                actor,
                correlation_id=correlation_id,
                result_code=error.code,
                idempotency_key=idempotency_key,
                review_id=None,
                outcome="denied",
            )
            raise

    async def _decide(
        self,
        *,
        actor: AuthenticatedSubject,
        report_id: str,
        report_version: int,
        report_digest: str,
        handoff_draft_id: str,
        outcome: ItsmHandoffReviewOutcome,
        rationale: str,
        acknowledged_review_only: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ItsmHandoffHumanReview:
        reason = rationale.strip()
        self._validate_actor(actor)
        if not acknowledged_review_only:
            raise ItsmHandoffReviewError("itsm_handoff_review_confirmation_required")
        if not 5 <= len(reason) <= 1000:
            raise ItsmHandoffReviewError("itsm_handoff_review_rationale_invalid")
        if not 8 <= len(idempotency_key) <= 128:
            raise ItsmHandoffReviewError("itsm_handoff_review_idempotency_invalid")
        fingerprint = self._digest(
            {
                "report_id": report_id,
                "report_version": report_version,
                "report_digest": report_digest,
                "handoff_draft_id": handoff_draft_id,
                "outcome": outcome.value,
                "rationale": reason,
                "acknowledged_review_only": acknowledged_review_only,
                "reviewer_id": actor.subject_id,
            }
        )
        report = await self._load_report(actor, report_id)
        handoff = report.itsm_handoff
        resolved_handoff_digest = canonical_handoff_digest(handoff) if handoff else ""
        if (
            report.version != report_version
            or report.content_digest != report_digest
            or handoff is None
            or handoff.draft_id != handoff_draft_id
            or report.expires_at <= self._clock()
        ):
            raise ItsmHandoffReviewError("itsm_handoff_review_source_changed")
        if actor.subject_id == report.requested_by:
            raise ItsmHandoffReviewError("itsm_handoff_review_separation_required")
        if any(
            (
                report.execution_authorized,
                report.external_mutation_authorized,
                handoff.dispatch_authorized,
                handoff.external_record_mutated,
            )
        ):
            raise ItsmHandoffReviewError("itsm_handoff_review_authority_denied")
        replay = await self._repository.get_by_create_key(
            reviewer_id=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            if replay.request_fingerprint != fingerprint:
                raise ItsmHandoffReviewError("itsm_handoff_review_idempotency_conflict")
            self._validate_review_source(replay, report)
            await self._audit(
                actor,
                correlation_id=correlation_id,
                result_code="itsm_handoff_review_replayed",
                idempotency_key=idempotency_key,
                review_id=replay.review_id,
            )
            return replace(replay, reused=True)
        existing = await self._repository.get_by_handoff(handoff_draft_id=handoff.draft_id)
        if existing is not None:
            raise ItsmHandoffReviewError("itsm_handoff_review_state_conflict")

        decided_at = self._clock()
        canonical_digest = self._digest(
            {
                "schema_version": ITSM_HANDOFF_REVIEW_SCHEMA,
                "report": (report.report_id, report.version, report.content_digest),
                "handoff": (
                    handoff.draft_id,
                    resolved_handoff_digest,
                    handoff.idempotency_key,
                    handoff.incident_reference,
                    handoff.operation,
                ),
                "scope": (
                    report.organization_id,
                    report.environment_id,
                    report.site_id,
                ),
                "requester_id": report.requested_by,
                "reviewer": (actor.subject_id, ITSM_REVIEWER_ROLE_ID),
                "outcome": outcome.value,
                "rationale": reason,
                "decided_at": decided_at.isoformat(),
                "expires_at": report.expires_at.isoformat(),
                "authority": False,
            }
        )
        review = ItsmHandoffHumanReview(
            review_id=f"itsm-handoff-review.{canonical_digest[:24]}",
            schema_version=ITSM_HANDOFF_REVIEW_SCHEMA,
            version=1,
            outcome=outcome,
            report_id=report.report_id,
            report_version=report.version,
            report_digest=report.content_digest,
            handoff_draft_id=handoff.draft_id,
            handoff_digest=resolved_handoff_digest,
            handoff_idempotency_key=handoff.idempotency_key,
            incident_reference=handoff.incident_reference,
            operation=handoff.operation,
            requester_id=report.requested_by,
            reviewer_id=actor.subject_id,
            reviewer_role_id=ITSM_REVIEWER_ROLE_ID,
            organization_id=report.organization_id,
            environment_id=report.environment_id,
            site_id=report.site_id,
            rationale=reason,
            acknowledged_review_only=acknowledged_review_only,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            canonical_digest=canonical_digest,
            decided_at=decided_at,
            expires_at=report.expires_at,
            review_complete=outcome is ItsmHandoffReviewOutcome.ACCEPT,
        )
        if not await self._repository.add(review):
            raced = await self._repository.get_by_create_key(
                reviewer_id=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise ItsmHandoffReviewError("itsm_handoff_review_state_conflict")
            return replace(raced, reused=True)
        await self._audit(
            actor,
            correlation_id=correlation_id,
            result_code=f"itsm_handoff_review_{outcome.value}",
            idempotency_key=idempotency_key,
            review_id=review.review_id,
        )
        return review

    async def get_for_handoff(
        self,
        *,
        actor: AuthenticatedSubject,
        report_id: str,
        handoff_draft_id: str,
        correlation_id: str,
    ) -> ItsmHandoffHumanReview | None:
        report = await self._load_report(actor, report_id)
        if report.expires_at <= self._clock():
            raise ItsmHandoffReviewError("itsm_handoff_review_source_changed")
        handoff = report.itsm_handoff
        if handoff is None or handoff.draft_id != handoff_draft_id:
            raise ItsmHandoffReviewError("itsm_handoff_review_not_found")
        review = await self._repository.get_by_handoff(handoff_draft_id=handoff_draft_id)
        if review is not None:
            self._validate_review_source(review, report)
        await self._audit(
            actor,
            correlation_id=correlation_id,
            result_code="itsm_handoff_review_read",
            idempotency_key=None,
            review_id=review.review_id if review else None,
            permission_id="report.itsm-handoff-review.read",
            capability_class="C1",
        )
        return review

    async def close(self) -> None:
        await self._repository.close()

    def _validate_actor(self, actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ItsmHandoffReviewError("itsm_handoff_review_human_required")
        if ITSM_REVIEWER_ROLE_ID not in actor.role_ids:
            raise ItsmHandoffReviewError("itsm_handoff_review_role_required")

    async def _load_report(self, actor: AuthenticatedSubject, report_id: str) -> TechnicalReport:
        report = await self._report_source.get(report_id=report_id)
        if (
            report is None
            or report.organization_id != actor.organization_id
            or report.environment_id != self._environment_id
            or report.site_id != self._site_id
        ):
            raise ItsmHandoffReviewError("itsm_handoff_review_not_found")
        return report

    @staticmethod
    def _validate_review_source(review: ItsmHandoffHumanReview, report: TechnicalReport) -> None:
        handoff = report.itsm_handoff
        if (
            handoff is None
            or review.report_version != report.version
            or review.report_digest != report.content_digest
            or review.handoff_draft_id != handoff.draft_id
            or review.handoff_digest != canonical_handoff_digest(handoff)
        ):
            raise ItsmHandoffReviewError("itsm_handoff_review_source_changed")

    @staticmethod
    def _digest(value: object) -> str:
        return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        *,
        correlation_id: str,
        result_code: str,
        idempotency_key: str | None,
        review_id: str | None,
        outcome: str = "succeeded",
        permission_id: str = "report.itsm-handoff-review.decide",
        capability_class: str = "C2",
    ) -> None:
        now = self._clock()
        await self._audit_sink.record(
            AuditRecord(
                event_id=(
                    "evt_"
                    + sha256(f"{correlation_id}:{result_code}:{now}".encode()).hexdigest()[:24]
                ),
                event_type="atlas.report.itsm-handoff-human-review",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=now,
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.report.itsm-handoff-review",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/{self._site_id}/"
                    f"domain.report/resource.report.itsm-handoff-review/{capability_class}"
                ),
                decision_id=None,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(("review_id", review_id or "pending"),),
            )
        )
