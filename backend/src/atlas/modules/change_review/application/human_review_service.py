from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.change_review.application.human_review_ports import HumanReviewRepository
from atlas.modules.change_review.application.ports import (
    ChangeReviewError,
    ChangeReviewPacketRepository,
)
from atlas.modules.change_review.domain.human_review import (
    HumanReviewDecision,
    HumanReviewOutcome,
    HumanReviewStage,
    HumanReviewStageState,
    HumanReviewState,
    UpgradeChangeHumanReview,
)
from atlas.modules.change_review.domain.packet import UpgradeChangeReviewPacket
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
)

REVIEW_SCHEMA = "atlas.upgrade-change-human-review.v1"
STAGE_IDS = (
    "stage.platform-technical",
    "stage.service-owner",
    "stage.security-review",
    "stage.change-authority",
)
ELIGIBLE_ASSURANCE = frozenset(
    {
        AssuranceLevel.DEVELOPMENT,
        AssuranceLevel.SINGLE_FACTOR,
        AssuranceLevel.MULTI_FACTOR,
        AssuranceLevel.HARDWARE_BACKED,
    }
)
MAX_INBOX_SCAN = 500


@dataclass(frozen=True, slots=True)
class HumanReviewInboxPage:
    items: tuple[UpgradeChangeHumanReview, ...]
    next_cursor: str | None
    limit: int


class HumanReviewService:
    def __init__(
        self,
        *,
        packet_repository: ChangeReviewPacketRepository,
        review_repository: HumanReviewRepository,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._packet_repository = packet_repository
        self._review_repository = review_repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._site_id = site_id
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> HumanReviewRepository:
        return self._review_repository

    async def close(self) -> None:
        await self._review_repository.close()

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        packet_id: str,
        packet_digest: str,
        justification: str,
        confirmed: bool,
        acknowledged_no_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> UpgradeChangeHumanReview:
        rationale = justification.strip()
        if (
            actor.kind is not SubjectKind.HUMAN
            or not confirmed
            or not acknowledged_no_authority
            or not 12 <= len(rationale) <= 500
        ):
            raise ChangeReviewError("human_review_confirmation_required")
        packet = await self._load_packet(packet_id, packet_digest)
        self._validate_requester_packet(actor, packet)
        fingerprint = self._digest(
            {
                "packet_id": packet.packet_id,
                "packet_digest": packet.packet_digest,
                "requester_id": actor.subject_id,
                "justification": rationale,
                "acknowledged_no_authority": acknowledged_no_authority,
            }
        )
        prior = await self._review_repository.get_by_create_key(
            requester_id=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                raise ChangeReviewError("human_review_idempotency_conflict")
            await self._revalidate_source(prior)
            return replace(prior, reused=True)
        now = self._clock()
        expires_at = min(now + timedelta(hours=4), packet.proposed_window_start)
        if expires_at <= now + timedelta(minutes=5):
            raise ChangeReviewError("human_review_window_unavailable")
        stages = tuple(
            HumanReviewStage(
                stage_id=stage_id,
                sequence=index,
                required_role_id=role_id,
                quorum=1,
                state=(
                    HumanReviewStageState.PENDING if index == 1 else HumanReviewStageState.WAITING
                ),
                packet_digest=packet.packet_digest,
            )
            for index, (stage_id, role_id) in enumerate(
                zip(STAGE_IDS, packet.owner_role_ids, strict=True), start=1
            )
        )
        canonical_digest = self._digest(
            {
                "schema_version": REVIEW_SCHEMA,
                "packet": (packet.packet_id, packet.packet_digest),
                "scope": (packet.organization_id, packet.environment_id, packet.site_id),
                "requester_id": actor.subject_id,
                "risk_class": packet.risk_class,
                "change_class": packet.change_class,
                "services": packet.impacted_service_ids,
                "evidence": packet.evidence_digests,
                "window": (
                    packet.proposed_window_start.isoformat(),
                    packet.proposed_window_end.isoformat(),
                ),
                "stages": tuple(
                    (stage.stage_id, stage.sequence, stage.required_role_id, stage.quorum)
                    for stage in stages
                ),
                "expires_at": expires_at.isoformat(),
                "justification": rationale,
                "execution_authorized": False,
            }
        )
        review_id = f"change-human-review.{canonical_digest[:24]}"
        record = UpgradeChangeHumanReview(
            review_id=review_id,
            schema_version=REVIEW_SCHEMA,
            version=1,
            state=HumanReviewState.PENDING,
            packet_id=packet.packet_id,
            packet_digest=packet.packet_digest,
            requester_id=actor.subject_id,
            organization_id=packet.organization_id,
            environment_id=packet.environment_id,
            site_id=packet.site_id,
            risk_class=packet.risk_class,
            change_class=packet.change_class,
            impacted_service_ids=packet.impacted_service_ids,
            evidence_digests=packet.evidence_digests,
            proposed_window_start=packet.proposed_window_start,
            proposed_window_end=packet.proposed_window_end,
            justification=rationale,
            required_role_ids=packet.owner_role_ids,
            stages=stages,
            decisions=(),
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        await self._audit(
            actor,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            result_code="upgrade_human_review_created",
            permission_id="platform.upgrade-change-human-review.create",
            metadata=(("review_id", review_id), ("packet_digest", packet.packet_digest)),
        )
        if not await self._review_repository.add(record):
            raced = await self._review_repository.get_by_create_key(
                requester_id=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is None or raced.request_fingerprint != fingerprint:
                raise ChangeReviewError("human_review_idempotency_conflict")
            return replace(raced, reused=True)
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        review_id: str,
        correlation_id: str,
    ) -> UpgradeChangeHumanReview:
        record = await self._load_visible(actor, review_id)
        record = await self._expire(record, actor, correlation_id)
        await self._revalidate_source(record)
        await self._audit(
            actor,
            correlation_id=correlation_id,
            idempotency_key=None,
            result_code="upgrade_human_review_read",
            permission_id="platform.upgrade-change-human-review.read",
            metadata=(("review_id", review_id),),
        )
        return record

    async def inbox(
        self,
        *,
        actor: AuthenticatedSubject,
        role_id: str | None,
        cursor: str | None,
        limit: int,
        correlation_id: str,
    ) -> HumanReviewInboxPage:
        if not 1 <= limit <= 50:
            raise ChangeReviewError("human_review_inbox_limit_invalid")
        candidates = await self._review_repository.list_scope(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            limit=MAX_INBOX_SCAN + 1,
        )
        if len(candidates) > MAX_INBOX_SCAN:
            raise ChangeReviewError("human_review_inbox_capacity_exceeded")
        selected_roles = set(actor.role_ids)
        if role_id is not None:
            selected_roles &= {role_id}
        now = self._clock()
        visible: list[UpgradeChangeHumanReview] = []
        for record in candidates:
            stage = self._current_stage(record)
            if (
                stage is None
                or record.state is not HumanReviewState.PENDING
                or now >= record.expires_at
                or stage.required_role_id not in selected_roles
                or not self._reviewer_is_eligible(actor, record, stage)
            ):
                continue
            try:
                await self._revalidate_source(record)
            except ChangeReviewError:
                continue
            visible.append(record)

        start = 0
        if cursor is not None:
            cursor_index = next(
                (index for index, record in enumerate(visible) if record.review_id == cursor),
                None,
            )
            if cursor_index is None:
                raise ChangeReviewError("human_review_inbox_cursor_invalid")
            start = cursor_index + 1
        page_items = tuple(visible[start : start + limit])
        has_more = start + limit < len(visible)
        next_cursor = page_items[-1].review_id if has_more and page_items else None
        await self._audit(
            actor,
            correlation_id=correlation_id,
            idempotency_key=None,
            result_code="upgrade_human_review_inbox_read",
            permission_id="platform.upgrade-change-human-review.read",
            metadata=(
                ("visible_count", str(len(page_items))),
                ("role_filter", role_id or "actor.roles"),
            ),
        )
        return HumanReviewInboxPage(items=page_items, next_cursor=next_cursor, limit=limit)

    async def decide(
        self,
        *,
        actor: AuthenticatedSubject,
        review_id: str,
        stage_id: str,
        outcome: HumanReviewOutcome,
        rationale: str,
        acknowledged_no_authority: bool,
        expected_version: int,
        idempotency_key: str,
        correlation_id: str,
    ) -> UpgradeChangeHumanReview:
        reason = rationale.strip()
        if not acknowledged_no_authority:
            raise ChangeReviewError("human_review_decision_confirmation_required")
        if not 5 <= len(reason) <= 1000:
            raise ChangeReviewError("human_review_rationale_invalid")
        record = await self._load_visible(actor, review_id)
        await self._revalidate_source(record)
        fingerprint = self._digest(
            {
                "review_id": review_id,
                "stage_id": stage_id,
                "outcome": outcome.value,
                "rationale": reason,
                "acknowledged_no_authority": acknowledged_no_authority,
                "expected_version": expected_version,
                "reviewer_id": actor.subject_id,
            }
        )
        replay = next(
            (
                decision
                for decision in record.decisions
                if decision.reviewer_id == actor.subject_id
                and decision.idempotency_key == idempotency_key
            ),
            None,
        )
        if replay is not None:
            if replay.request_fingerprint != fingerprint:
                raise ChangeReviewError("human_review_idempotency_conflict")
            await self._audit(
                actor,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                result_code="upgrade_human_review_decision_replayed",
                permission_id="platform.upgrade-change-human-review.decide",
                metadata=(("review_id", review_id), ("stage_id", stage_id)),
            )
            return replace(record, reused=True)
        record = await self._expire(record, actor, correlation_id)
        if record.state is HumanReviewState.EXPIRED:
            raise ChangeReviewError("human_review_expired")
        if record.version != expected_version or record.state is not HumanReviewState.PENDING:
            raise ChangeReviewError("human_review_state_conflict")
        stage_index = next(
            (index for index, stage in enumerate(record.stages) if stage.stage_id == stage_id),
            None,
        )
        if stage_index is None:
            raise ChangeReviewError("human_review_stage_invalid")
        stage = record.stages[stage_index]
        self._validate_reviewer(actor, record, stage)
        decision = HumanReviewDecision(
            decision_id=f"human-review-decision.{fingerprint[:24]}",
            stage_id=stage.stage_id,
            request_version=record.version,
            outcome=outcome,
            reviewer_id=actor.subject_id,
            reviewer_role_id=stage.required_role_id,
            rationale=reason,
            acknowledged_no_authority=acknowledged_no_authority,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            decided_at=self._clock(),
        )
        next_stage_state = {
            HumanReviewOutcome.APPROVE: HumanReviewStageState.APPROVED,
            HumanReviewOutcome.REJECT: HumanReviewStageState.REJECTED,
            HumanReviewOutcome.NEEDS_EVIDENCE: HumanReviewStageState.NEEDS_EVIDENCE,
            HumanReviewOutcome.DEFER: HumanReviewStageState.DEFERRED,
        }[outcome]
        updated_stages = list(record.stages)
        updated_stages[stage_index] = replace(
            stage,
            state=next_stage_state,
            reviewer_id=actor.subject_id,
            decision_id=decision.decision_id,
            decided_at=decision.decided_at,
            rationale=reason,
        )
        if outcome is HumanReviewOutcome.APPROVE and stage_index + 1 < len(updated_stages):
            updated_stages[stage_index + 1] = replace(
                updated_stages[stage_index + 1], state=HumanReviewStageState.PENDING
            )
            next_state = HumanReviewState.PENDING
        elif outcome is HumanReviewOutcome.APPROVE:
            next_state = HumanReviewState.COMPLETED
        else:
            next_state = {
                HumanReviewOutcome.REJECT: HumanReviewState.REJECTED,
                HumanReviewOutcome.NEEDS_EVIDENCE: HumanReviewState.NEEDS_EVIDENCE,
                HumanReviewOutcome.DEFER: HumanReviewState.DEFERRED,
            }[outcome]
        updated = replace(
            record,
            version=record.version + 1,
            state=next_state,
            stages=tuple(updated_stages),
            decisions=(*record.decisions, decision),
            updated_at=decision.decided_at,
            reused=False,
            human_review_completed=next_state is HumanReviewState.COMPLETED,
        )
        await self._audit(
            actor,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            result_code=f"upgrade_human_review_{outcome.value}",
            permission_id="platform.upgrade-change-human-review.decide",
            metadata=(("review_id", review_id), ("stage_id", stage_id)),
        )
        if not await self._review_repository.update(updated, expected_version=record.version):
            raise ChangeReviewError("human_review_state_conflict")
        return updated

    async def _load_packet(self, packet_id: str, packet_digest: str) -> UpgradeChangeReviewPacket:
        packet = await self._packet_repository.get_by_id(packet_id=packet_id)
        if packet is None or packet.packet_digest != packet_digest:
            raise ChangeReviewError("human_review_source_unavailable")
        return packet

    async def _load_visible(
        self, actor: AuthenticatedSubject, review_id: str
    ) -> UpgradeChangeHumanReview:
        record = await self._review_repository.get_by_id(review_id=review_id)
        if (
            record is None
            or record.organization_id != actor.organization_id
            or record.environment_id != self._environment_id
            or record.site_id != self._site_id
        ):
            raise ChangeReviewError("human_review_not_found")
        return record

    def _validate_requester_packet(
        self, actor: AuthenticatedSubject, packet: UpgradeChangeReviewPacket
    ) -> None:
        if (
            packet.actor_id != actor.subject_id
            or packet.organization_id != actor.organization_id
            or packet.environment_id != self._environment_id
            or packet.site_id != self._site_id
            or any(
                (
                    packet.approval_granted,
                    packet.execution_authorized,
                    packet.itsm_dispatched,
                    packet.notification_sent,
                    packet.workflow_executed,
                    packet.infrastructure_mutation_performed,
                )
            )
        ):
            raise ChangeReviewError("human_review_source_unavailable")

    async def _revalidate_source(self, record: UpgradeChangeHumanReview) -> None:
        packet = await self._load_packet(record.packet_id, record.packet_digest)
        if (
            packet.organization_id != record.organization_id
            or packet.environment_id != record.environment_id
            or packet.site_id != record.site_id
            or packet.proposed_window_start != record.proposed_window_start
            or packet.proposed_window_end != record.proposed_window_end
            or packet.owner_role_ids != record.required_role_ids
            or packet.evidence_digests != record.evidence_digests
        ):
            raise ChangeReviewError("human_review_source_changed")

    @staticmethod
    def _validate_reviewer(
        actor: AuthenticatedSubject,
        record: UpgradeChangeHumanReview,
        stage: HumanReviewStage,
    ) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ChangeReviewError("human_review_human_reviewer_required")
        if actor.assurance_level not in ELIGIBLE_ASSURANCE:
            raise ChangeReviewError("human_review_assurance_insufficient")
        if actor.subject_id == record.requester_id:
            raise ChangeReviewError("human_review_separation_required")
        if actor.subject_id in {decision.reviewer_id for decision in record.decisions}:
            raise ChangeReviewError("human_review_distinct_reviewer_required")
        if any(not decision.acknowledged_no_authority for decision in record.decisions):
            raise ChangeReviewError("human_review_prior_decision_evidence_incomplete")
        if stage.state is not HumanReviewStageState.PENDING:
            raise ChangeReviewError("human_review_stage_not_pending")
        if stage.required_role_id not in actor.role_ids:
            raise ChangeReviewError("human_review_role_required")

    @staticmethod
    def _reviewer_is_eligible(
        actor: AuthenticatedSubject,
        record: UpgradeChangeHumanReview,
        stage: HumanReviewStage,
    ) -> bool:
        return (
            actor.kind is SubjectKind.HUMAN
            and actor.assurance_level in ELIGIBLE_ASSURANCE
            and actor.subject_id != record.requester_id
            and actor.subject_id not in {decision.reviewer_id for decision in record.decisions}
            and all(decision.acknowledged_no_authority for decision in record.decisions)
            and stage.state is HumanReviewStageState.PENDING
            and stage.required_role_id in actor.role_ids
        )

    @staticmethod
    def _current_stage(record: UpgradeChangeHumanReview) -> HumanReviewStage | None:
        return next(
            (stage for stage in record.stages if stage.state is HumanReviewStageState.PENDING),
            None,
        )

    async def _expire(
        self,
        record: UpgradeChangeHumanReview,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> UpgradeChangeHumanReview:
        if record.state is not HumanReviewState.PENDING or self._clock() < record.expires_at:
            return record
        expired = replace(
            record,
            version=record.version + 1,
            state=HumanReviewState.EXPIRED,
            updated_at=self._clock(),
        )
        await self._audit(
            actor,
            correlation_id=correlation_id,
            idempotency_key=None,
            result_code="upgrade_human_review_expired",
            permission_id="platform.upgrade-change-human-review.read",
            metadata=(("review_id", record.review_id),),
        )
        if not await self._review_repository.update(expired, expected_version=record.version):
            current = await self._review_repository.get_by_id(review_id=record.review_id)
            if current is None:
                raise ChangeReviewError("human_review_not_found")
            return current
        return expired

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        *,
        correlation_id: str,
        idempotency_key: str | None,
        result_code: str,
        permission_id: str,
        metadata: tuple[tuple[str, str], ...],
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{sha256(f'{correlation_id}:{result_code}:{self._clock()}'.encode()).hexdigest()[:24]}",
                event_type="atlas.upgrade.change-human-review",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.platform.upgrade-change-human-review",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/{self._site_id}/"
                    "domain.platform/resource.platform.upgrade-change-human-review/C2"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )
