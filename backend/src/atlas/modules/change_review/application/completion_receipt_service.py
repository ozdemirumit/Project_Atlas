from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.change_review.application.completion_receipt_ports import (
    CompletionReceiptRepository,
)
from atlas.modules.change_review.application.human_review_ports import HumanReviewRepository
from atlas.modules.change_review.application.ports import (
    ChangeReviewError,
    ChangeReviewPacketRepository,
)
from atlas.modules.change_review.domain.completion_receipt import (
    CompletionStageEvidence,
    HumanReviewCompletionReceipt,
)
from atlas.modules.change_review.domain.human_review import (
    HumanReviewOutcome,
    HumanReviewStageState,
    HumanReviewState,
    UpgradeChangeHumanReview,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
)

RECEIPT_SCHEMA = "atlas.upgrade-human-review-completion-receipt.v1"
ELIGIBLE_ASSURANCE = frozenset(
    {
        AssuranceLevel.DEVELOPMENT,
        AssuranceLevel.SINGLE_FACTOR,
        AssuranceLevel.MULTI_FACTOR,
        AssuranceLevel.HARDWARE_BACKED,
    }
)


class CompletionReceiptService:
    def __init__(
        self,
        *,
        packet_repository: ChangeReviewPacketRepository,
        review_repository: HumanReviewRepository,
        receipt_repository: CompletionReceiptRepository,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._packet_repository = packet_repository
        self._review_repository = review_repository
        self._receipt_repository = receipt_repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._site_id = site_id
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> CompletionReceiptRepository:
        return self._receipt_repository

    async def close(self) -> None:
        await self._receipt_repository.close()

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        review_id: str,
        expected_review_version: int,
        acknowledged_evidence_only: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> HumanReviewCompletionReceipt:
        if not acknowledged_evidence_only:
            raise ChangeReviewError("completion_receipt_confirmation_required")
        self._validate_reader(actor)
        review = await self._load_review(actor, review_id)
        fingerprint = self._digest(
            {
                "review_id": review_id,
                "expected_review_version": expected_review_version,
                "created_by": actor.subject_id,
                "acknowledged_evidence_only": acknowledged_evidence_only,
            }
        )
        replay = await self._receipt_repository.get_by_create_key(
            created_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            if replay.request_fingerprint != fingerprint:
                raise ChangeReviewError("completion_receipt_idempotency_conflict")
            await self._revalidate_receipt(replay)
            await self._audit(
                actor,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                result_code="upgrade_completion_receipt_replayed",
                permission_id="platform.upgrade-human-review-receipt.create",
                metadata=(("receipt_id", replay.receipt_id), ("review_id", review_id)),
            )
            return replace(replay, reused=True)
        self._validate_creator(actor, review, expected_review_version)
        await self._revalidate_review(review)
        stage_evidence = self._stage_evidence(review)
        now = self._clock()
        canonical_digest = self._digest(
            {
                "schema_version": RECEIPT_SCHEMA,
                "review": (
                    review.review_id,
                    review.version,
                    review.canonical_digest,
                    review.expires_at.isoformat(),
                ),
                "packet": (review.packet_id, review.packet_digest),
                "scope": (review.organization_id, review.environment_id, review.site_id),
                "requester_id": review.requester_id,
                "created_by": actor.subject_id,
                "risk_class": review.risk_class,
                "change_class": review.change_class,
                "services": review.impacted_service_ids,
                "evidence": review.evidence_digests,
                "window": (
                    review.proposed_window_start.isoformat(),
                    review.proposed_window_end.isoformat(),
                ),
                "stages": tuple(
                    (
                        item.stage_id,
                        item.sequence,
                        item.required_role_id,
                        item.reviewer_id,
                        item.decision_id,
                        item.request_version,
                        item.outcome.value,
                        item.rationale_digest,
                        item.acknowledged_no_authority,
                        item.decided_at.isoformat(),
                    )
                    for item in stage_evidence
                ),
                "approval_granted": False,
                "handoff_issued": False,
                "execution_authorized": False,
            }
        )
        receipt = HumanReviewCompletionReceipt(
            receipt_id=f"human-review-completion-receipt.{canonical_digest[:24]}",
            schema_version=RECEIPT_SCHEMA,
            version=1,
            review_id=review.review_id,
            review_version=review.version,
            review_digest=review.canonical_digest,
            review_expires_at=review.expires_at,
            packet_id=review.packet_id,
            packet_digest=review.packet_digest,
            requester_id=review.requester_id,
            created_by=actor.subject_id,
            organization_id=review.organization_id,
            environment_id=review.environment_id,
            site_id=review.site_id,
            risk_class=review.risk_class,
            change_class=review.change_class,
            impacted_service_ids=review.impacted_service_ids,
            evidence_digests=review.evidence_digests,
            proposed_window_start=review.proposed_window_start,
            proposed_window_end=review.proposed_window_end,
            stages=stage_evidence,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            created_at=now,
        )
        await self._audit(
            actor,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            result_code="upgrade_completion_receipt_created",
            permission_id="platform.upgrade-human-review-receipt.create",
            metadata=(("receipt_id", receipt.receipt_id), ("review_id", review.review_id)),
        )
        if not await self._receipt_repository.add(receipt):
            raced = await self._receipt_repository.get_by_review_id(review_id=review.review_id)
            if raced is None or raced.canonical_digest != receipt.canonical_digest:
                raise ChangeReviewError("completion_receipt_state_conflict")
            return replace(raced, reused=True)
        return receipt

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        receipt_id: str,
        correlation_id: str,
    ) -> HumanReviewCompletionReceipt:
        self._validate_reader(actor)
        receipt = await self._receipt_repository.get_by_id(receipt_id=receipt_id)
        if (
            receipt is None
            or receipt.organization_id != actor.organization_id
            or receipt.environment_id != self._environment_id
            or receipt.site_id != self._site_id
        ):
            raise ChangeReviewError("completion_receipt_not_found")
        await self._revalidate_receipt(receipt)
        await self._audit(
            actor,
            correlation_id=correlation_id,
            idempotency_key=None,
            result_code="upgrade_completion_receipt_read",
            permission_id="platform.upgrade-human-review-receipt.read",
            metadata=(("receipt_id", receipt.receipt_id),),
        )
        return receipt

    def _validate_creator(
        self,
        actor: AuthenticatedSubject,
        review: UpgradeChangeHumanReview,
        expected_review_version: int,
    ) -> None:
        self._validate_reader(actor)
        if review.version != expected_review_version:
            raise ChangeReviewError("completion_receipt_state_conflict")
        if (
            review.state is not HumanReviewState.COMPLETED
            or not review.human_review_completed
            or self._clock() >= review.expires_at
            or len(review.decisions) != 4
            or any(
                decision.outcome is not HumanReviewOutcome.APPROVE for decision in review.decisions
            )
            or any(not decision.acknowledged_no_authority for decision in review.decisions)
            or len({decision.reviewer_id for decision in review.decisions}) != 4
            or any(stage.state is not HumanReviewStageState.APPROVED for stage in review.stages)
        ):
            raise ChangeReviewError("completion_receipt_review_ineligible")
        final_stage = review.stages[-1]
        final_decision = review.decisions[-1]
        if (
            actor.subject_id == review.requester_id
            or actor.subject_id != final_decision.reviewer_id
            or final_decision.stage_id != final_stage.stage_id
            or final_stage.required_role_id not in actor.role_ids
        ):
            raise ChangeReviewError("completion_receipt_creator_ineligible")
        if any(
            (
                review.approval_granted,
                review.itsm_dispatched,
                review.handoff_issued,
                review.workflow_executed,
                review.execution_authorized,
                review.infrastructure_mutation_performed,
            )
        ):
            raise ChangeReviewError("completion_receipt_review_ineligible")

    @staticmethod
    def _validate_reader(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ChangeReviewError("completion_receipt_human_required")
        if actor.assurance_level not in ELIGIBLE_ASSURANCE:
            raise ChangeReviewError("completion_receipt_assurance_insufficient")

    async def _load_review(
        self, actor: AuthenticatedSubject, review_id: str
    ) -> UpgradeChangeHumanReview:
        review = await self._review_repository.get_by_id(review_id=review_id)
        if (
            review is None
            or review.organization_id != actor.organization_id
            or review.environment_id != self._environment_id
            or review.site_id != self._site_id
        ):
            raise ChangeReviewError("completion_receipt_review_not_found")
        return review

    async def _revalidate_review(self, review: UpgradeChangeHumanReview) -> None:
        current = await self._review_repository.get_by_id(review_id=review.review_id)
        packet = await self._packet_repository.get_by_id(packet_id=review.packet_id)
        if (
            current is None
            or current.version != review.version
            or current.canonical_digest != review.canonical_digest
            or current.state is not HumanReviewState.COMPLETED
            or current.decisions != review.decisions
            or packet is None
            or packet.packet_digest != review.packet_digest
            or packet.organization_id != review.organization_id
            or packet.environment_id != review.environment_id
            or packet.site_id != review.site_id
            or packet.owner_role_ids != review.required_role_ids
            or packet.evidence_digests != review.evidence_digests
            or packet.impacted_service_ids != review.impacted_service_ids
            or packet.proposed_window_start != review.proposed_window_start
            or packet.proposed_window_end != review.proposed_window_end
            or any(
                (
                    review.approval_granted,
                    review.itsm_dispatched,
                    review.handoff_issued,
                    review.workflow_executed,
                    review.execution_authorized,
                    review.infrastructure_mutation_performed,
                    packet.approval_granted,
                    packet.execution_authorized,
                    packet.itsm_dispatched,
                    packet.notification_sent,
                    packet.workflow_executed,
                    packet.infrastructure_mutation_performed,
                )
            )
        ):
            raise ChangeReviewError("completion_receipt_source_changed")

    async def _revalidate_receipt(self, receipt: HumanReviewCompletionReceipt) -> None:
        review = await self._review_repository.get_by_id(review_id=receipt.review_id)
        if (
            review is None
            or review.version != receipt.review_version
            or review.canonical_digest != receipt.review_digest
            or review.expires_at != receipt.review_expires_at
            or review.packet_id != receipt.packet_id
            or review.packet_digest != receipt.packet_digest
            or review.requester_id != receipt.requester_id
            or review.organization_id != receipt.organization_id
            or review.environment_id != receipt.environment_id
            or review.site_id != receipt.site_id
            or review.risk_class != receipt.risk_class
            or review.change_class != receipt.change_class
            or review.impacted_service_ids != receipt.impacted_service_ids
            or review.evidence_digests != receipt.evidence_digests
            or review.proposed_window_start != receipt.proposed_window_start
            or review.proposed_window_end != receipt.proposed_window_end
            or self._stage_evidence(review) != receipt.stages
            or self._receipt_digest(receipt) != receipt.canonical_digest
            or self._digest(
                {
                    "review_id": receipt.review_id,
                    "expected_review_version": receipt.review_version,
                    "created_by": receipt.created_by,
                    "acknowledged_evidence_only": True,
                }
            )
            != receipt.request_fingerprint
        ):
            raise ChangeReviewError("completion_receipt_source_changed")
        await self._revalidate_review(review)

    @classmethod
    def _stage_evidence(
        cls, review: UpgradeChangeHumanReview
    ) -> tuple[CompletionStageEvidence, ...]:
        decisions = {decision.decision_id: decision for decision in review.decisions}
        items: list[CompletionStageEvidence] = []
        for stage in review.stages:
            if stage.decision_id is None or stage.decision_id not in decisions:
                raise ChangeReviewError("completion_receipt_review_ineligible")
            decision = decisions[stage.decision_id]
            if (
                decision.stage_id != stage.stage_id
                or decision.reviewer_id != stage.reviewer_id
                or decision.reviewer_role_id != stage.required_role_id
                or decision.outcome is not HumanReviewOutcome.APPROVE
                or not decision.acknowledged_no_authority
            ):
                raise ChangeReviewError("completion_receipt_review_ineligible")
            items.append(
                CompletionStageEvidence(
                    stage_id=stage.stage_id,
                    sequence=stage.sequence,
                    required_role_id=stage.required_role_id,
                    reviewer_id=decision.reviewer_id,
                    decision_id=decision.decision_id,
                    request_version=decision.request_version,
                    outcome=decision.outcome,
                    rationale_digest=cls._digest(decision.rationale),
                    acknowledged_no_authority=decision.acknowledged_no_authority,
                    decided_at=decision.decided_at,
                )
            )
        return tuple(items)

    @classmethod
    def _receipt_digest(cls, receipt: HumanReviewCompletionReceipt) -> str:
        return cls._digest(
            {
                "schema_version": receipt.schema_version,
                "review": (
                    receipt.review_id,
                    receipt.review_version,
                    receipt.review_digest,
                    receipt.review_expires_at.isoformat(),
                ),
                "packet": (receipt.packet_id, receipt.packet_digest),
                "scope": (
                    receipt.organization_id,
                    receipt.environment_id,
                    receipt.site_id,
                ),
                "requester_id": receipt.requester_id,
                "created_by": receipt.created_by,
                "risk_class": receipt.risk_class,
                "change_class": receipt.change_class,
                "services": receipt.impacted_service_ids,
                "evidence": receipt.evidence_digests,
                "window": (
                    receipt.proposed_window_start.isoformat(),
                    receipt.proposed_window_end.isoformat(),
                ),
                "stages": tuple(
                    (
                        item.stage_id,
                        item.sequence,
                        item.required_role_id,
                        item.reviewer_id,
                        item.decision_id,
                        item.request_version,
                        item.outcome.value,
                        item.rationale_digest,
                        item.acknowledged_no_authority,
                        item.decided_at.isoformat(),
                    )
                    for item in receipt.stages
                ),
                "approval_granted": False,
                "handoff_issued": False,
                "execution_authorized": False,
            }
        )

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
        capability = "C1" if permission_id.endswith(".read") else "C2"
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{sha256(f'{correlation_id}:{result_code}:{self._clock()}'.encode()).hexdigest()[:24]}",
                event_type="atlas.upgrade.human-review-completion-receipt",
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
                resource_type="resource.platform.upgrade-human-review-receipt",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/{self._site_id}/"
                    "domain.platform/resource.platform.upgrade-human-review-receipt/"
                    f"{capability}"
                ),
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )
