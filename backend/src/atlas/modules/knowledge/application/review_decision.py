from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.authorization.application.bootstrap import (
    KNOWLEDGE_TRACK_REVIEW_DECISION_CREATE,
    KNOWLEDGE_TRACK_REVIEW_DECISION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.application.review_decision_ports import (
    OperationalKnowledgeTrackReviewDecisionAttestor,
    OperationalKnowledgeTrackReviewDecisionError,
    OperationalKnowledgeTrackReviewDecisionPermissionAuthorizer,
    OperationalKnowledgeTrackReviewDecisionPolicySource,
    OperationalKnowledgeTrackReviewDecisionRepository,
    OperationalKnowledgeTrackReviewDecisionSource,
    OperationalKnowledgeTrackReviewDecisionUncertainError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.finding_presentation import (
    OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_PRESENTED,
    OperationalKnowledgeFindingPresentationPolicySnapshot,
    OperationalKnowledgeFindingPresentationRecord,
)
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentRecord,
)
from atlas.modules.knowledge.domain.protected_inspection import (
    OPERATIONAL_KNOWLEDGE_PROTECTED_INSPECTION_LEASED,
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
    OperationalKnowledgeProtectedInspectionRecord,
)
from atlas.modules.knowledge.domain.review_decision import (
    DISPOSITIONS,
    OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED,
    OperationalKnowledgeTrackDecisionBinding,
    OperationalKnowledgeTrackReviewDecisionClaim,
    OperationalKnowledgeTrackReviewDecisionGrant,
    OperationalKnowledgeTrackReviewDecisionInstruction,
    OperationalKnowledgeTrackReviewDecisionPolicySnapshot,
    OperationalKnowledgeTrackReviewDecisionReceipt,
    OperationalKnowledgeTrackReviewDecisionRecord,
)
from atlas.modules.knowledge.domain.review_finding import (
    OperationalKnowledgeReviewFindingPolicySnapshot,
    OperationalKnowledgeReviewFindingRecord,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentRecord,
)

DECISION_POLICY_SCHEMA = "atlas.operational-knowledge-track-review-decision-policy.v1"
DECISION_CLAIM_SCHEMA = "atlas.operational-knowledge-track-review-decision-claim.v1"
DECISION_RECORD_SCHEMA = "atlas.operational-knowledge-track-review-decision.v1"

ReviewDecisionSourceBundle = tuple[
    OperationalKnowledgeFindingPresentationRecord,
    OperationalKnowledgeReviewFindingRecord,
    OperationalKnowledgeProtectedContentRecord,
    OperationalKnowledgeProtectedInspectionRecord,
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
    OperationalKnowledgeReviewerAssignmentRecord,
    OperationalKnowledgeReviewRequestRecord,
    OperationalEvidenceKnowledgeDraftRecord,
    OperationalKnowledgeReviewFindingPolicySnapshot,
    OperationalKnowledgeFindingPresentationPolicySnapshot,
]


class OperationalKnowledgeTrackReviewDecisionService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeTrackReviewDecisionRepository,
        source: OperationalKnowledgeTrackReviewDecisionSource,
        policy_source: OperationalKnowledgeTrackReviewDecisionPolicySource,
        permission_authorizer: OperationalKnowledgeTrackReviewDecisionPermissionAuthorizer,
        attestor: OperationalKnowledgeTrackReviewDecisionAttestor,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._attestor = attestor
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_lease_id: str,
        source_content_presentation_id: str,
        source_finding_packet_id: str,
        source_finding_presentation_id: str,
        source_finding_presentation_digest: str,
        decision_policy_id: str,
        decision_policy_digest: str,
        disposition_code: str,
        basis_codes: tuple[str, ...],
        purpose: str,
        exact_findings_reviewed_acknowledged: bool,
        human_track_decision_acknowledged: bool,
        no_approval_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeTrackReviewDecisionGrant:
        purpose = purpose.strip()
        basis_codes = tuple(sorted(set(basis_codes)))
        if (
            not exact_findings_reviewed_acknowledged
            or not human_track_decision_acknowledged
            or not no_approval_or_operational_authority_acknowledged
            or disposition_code not in DISPOSITIONS
            or not basis_codes
            or not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_request_invalid"
            )
        source, policy = await self._authorize(
            actor=actor,
            source_lease_id=source_lease_id,
            source_content_presentation_id=source_content_presentation_id,
            source_finding_packet_id=source_finding_packet_id,
            source_finding_presentation_id=source_finding_presentation_id,
            source_finding_presentation_digest=source_finding_presentation_digest,
            decision_policy_id=decision_policy_id,
            decision_policy_digest=decision_policy_digest,
            browser_session_id=browser_session_id,
            lease_secrets=lease_secrets,
            correlation_id=correlation_id,
        )
        presentation, _finding, _content, _lease, inspection_policy, *_ = source
        allowed_basis = (
            frozenset(policy.domain_basis_codes)
            if presentation.track_code == "review-track.domain"
            else frozenset(policy.security_basis_codes)
        )
        if len(basis_codes) > policy.maximum_basis_codes or any(
            code not in allowed_basis for code in basis_codes
        ):
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_basis_invalid"
            )
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest(
            [inspection_policy.browser_binding_key_digest, browser_session_id]
        )
        basis_digest = self._digest(basis_codes)
        purpose_digest = self._digest(purpose)
        request_digest = self._digest(
            {
                "source_finding_presentation_id": presentation.finding_presentation_id,
                "source_finding_presentation_digest": presentation.canonical_digest,
                "decision_policy_id": policy.policy_id,
                "decision_policy_digest": policy.canonical_digest,
                "track_code": presentation.track_code,
                "disposition_code": disposition_code,
                "basis_digest": basis_digest,
                "purpose_digest": purpose_digest,
                "browser_session_binding_digest": browser_digest,
            }
        )
        idempotency_digest = self._digest([subject_digest, browser_digest, idempotency_key])
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=subject_digest,
            idempotency_digest=idempotency_digest,
        )
        if existing is not None:
            return await self._reuse(
                existing,
                source=source,
                policy=policy,
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_digest=request_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        seed = self._digest(
            [
                presentation.finding_presentation_id,
                presentation.canonical_digest,
                policy.canonical_digest,
            ]
        )
        decision_id = f"operational-knowledge-track-review-decision.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_track_review_decision_requested",
            presentation.finding_presentation_id,
            (("track_code", presentation.track_code), ("disposition_code", disposition_code)),
        )
        claim = OperationalKnowledgeTrackReviewDecisionClaim(
            claim_id=f"operational-knowledge-track-review-decision-claim.{seed[:24]}",
            schema_version=DECISION_CLAIM_SCHEMA,
            version=1,
            source_finding_presentation_id=presentation.finding_presentation_id,
            source_finding_presentation_digest=presentation.canonical_digest,
            decision_id=decision_id,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            track_code=presentation.track_code,
            disposition_code=disposition_code,
            basis_digest=basis_digest,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            purpose_digest=purpose_digest,
            claimed_at=self._clock(),
            request_binding_digest=request_digest,
            idempotency_digest=idempotency_digest,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._claim_payload(claim)))
        if not await self._repository.claim(claim):
            prior = await self._repository.get_claim_by_source_presentation(
                source_finding_presentation_id=presentation.finding_presentation_id
            )
            if prior is None:
                raise OperationalKnowledgeTrackReviewDecisionUncertainError(
                    "operational_knowledge_track_review_decision_claim_uncertain"
                )
            return await self._reuse(
                prior,
                source=source,
                policy=policy,
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_digest=request_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_track_review_decision_claimed",
            claim.claim_id,
            (("decision_id", decision_id),),
        )
        instruction = self._instruction(claim, presentation, policy, basis_codes)
        try:
            receipt = await self._attestor.attest(instruction)
            self._verify_receipt(instruction, receipt, policy)
        except OperationalKnowledgeTrackReviewDecisionError:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_track_review_decision_failed",
                decision_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_track_review_decision_uncertain",
                decision_id,
                (("claim_persisted", "true"),),
            )
            raise OperationalKnowledgeTrackReviewDecisionUncertainError(
                "operational_knowledge_track_review_decision_outcome_uncertain"
            ) from error
        record = self._record(claim, presentation, source[6], policy, receipt, basis_codes, purpose)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_track_review_decided",
            decision_id,
            (("track_code", record.track_code), ("disposition_code", record.disposition_code)),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source_presentation(
                source_finding_presentation_id=presentation.finding_presentation_id
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise OperationalKnowledgeTrackReviewDecisionUncertainError(
                    "operational_knowledge_track_review_decision_persistence_uncertain"
                )
            record = replace(raced, reused=True)
        return await self._grant(record)

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        source_lease_id: str,
        source_content_presentation_id: str,
        source_finding_packet_id: str,
        source_finding_presentation_id: str,
        decision_id: str,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        correlation_id: str,
    ) -> OperationalKnowledgeTrackReviewDecisionGrant:
        record = await self._repository.get(decision_id=decision_id)
        if (
            record is None
            or record.source_lease_id != source_lease_id
            or record.source_content_presentation_id != source_content_presentation_id
            or record.source_finding_packet_id != source_finding_packet_id
            or record.source_finding_presentation_id != source_finding_presentation_id
        ):
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_not_found"
            )
        self._verify_record(record)
        await self._authorize(
            actor=actor,
            source_lease_id=source_lease_id,
            source_content_presentation_id=source_content_presentation_id,
            source_finding_packet_id=source_finding_packet_id,
            source_finding_presentation_id=source_finding_presentation_id,
            source_finding_presentation_digest=record.source_finding_presentation_digest,
            decision_policy_id=record.decision_policy_id,
            decision_policy_digest=record.decision_policy_digest,
            browser_session_id=browser_session_id,
            lease_secrets=lease_secrets,
            correlation_id=correlation_id,
            allow_existing_decision=True,
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_track_review_decision_read",
            record.decision_id,
            (("track_code", record.track_code),),
            permission_id=KNOWLEDGE_TRACK_REVIEW_DECISION_READ,
        )
        return await self._grant(replace(record, reused=True))

    async def close(self) -> None:
        await self._repository.close()

    async def correction_resubmission_source(
        self, *, review_request_id: str
    ) -> tuple[
        tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]:
        decisions = await self._repository.list_by_review_request(
            review_request_id=review_request_id
        )
        if not decisions:
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_not_found"
            )
        request: OperationalKnowledgeReviewRequestRecord | None = None
        draft: OperationalEvidenceKnowledgeDraftRecord | None = None
        for decision in decisions:
            self._verify_record(decision)
            source = await self._source.review_decision_source(
                finding_presentation_id=decision.source_finding_presentation_id
            )
            source_request = source[6]
            source_draft = source[7]
            if request is None:
                request, draft = source_request, source_draft
            elif (
                source_request.canonical_digest != request.canonical_digest
                or draft is None
                or source_draft.canonical_digest != draft.canonical_digest
            ):
                raise OperationalKnowledgeTrackReviewDecisionError(
                    "operational_knowledge_track_review_decision_lineage_invalid"
                )
        assert request is not None and draft is not None
        return decisions, request, draft

    async def _authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        source_lease_id: str,
        source_content_presentation_id: str,
        source_finding_packet_id: str,
        source_finding_presentation_id: str,
        source_finding_presentation_digest: str,
        decision_policy_id: str,
        decision_policy_digest: str,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        correlation_id: str,
        allow_existing_decision: bool = False,
    ) -> tuple[ReviewDecisionSourceBundle, OperationalKnowledgeTrackReviewDecisionPolicySnapshot]:
        self._require_enterprise_human(actor)
        try:
            source = await self._source.review_decision_source(
                finding_presentation_id=source_finding_presentation_id
            )
        except Exception as error:
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_source_not_found"
            ) from error
        presentation, finding, content, lease, inspection_policy, assignment, *_ = source
        policy = await self._policy_source.get_by_id(policy_id=decision_policy_id)
        if policy is None:
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_policy_not_found"
            )
        self._verify_policy(policy)
        now = self._clock()
        later_authority = (
            presentation.correction_created,
            presentation.knowledge_approved,
            presentation.knowledge_published,
            presentation.retrieval_published,
            presentation.model_context_available,
            presentation.workflow_continued,
            presentation.execution_authorized,
            presentation.deployment_approved,
            presentation.infrastructure_mutation_performed,
        )
        if (
            presentation.finding_presentation_id != source_finding_presentation_id
            or presentation.canonical_digest != source_finding_presentation_digest
            or presentation.source_lease_id != source_lease_id
            or presentation.source_content_presentation_id != source_content_presentation_id
            or presentation.source_finding_packet_id != source_finding_packet_id
            or presentation.instance_state != OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_PRESENTED
            or not presentation.finding_presented
            or any(later_authority)
            or (
                not allow_existing_decision
                and (presentation.domain_review_completed or presentation.security_review_completed)
            )
            or lease.instance_state != OPERATIONAL_KNOWLEDGE_PROTECTED_INSPECTION_LEASED
            or now >= lease.expires_at
            or now >= content.expires_at
            or now >= finding.expires_at
            or now >= presentation.expires_at
            or policy.canonical_digest != decision_policy_digest
            or policy.organization_id != presentation.organization_id
            or policy.environment_id != presentation.environment_id
            or policy.required_source_schema != presentation.schema_version
            or policy.required_source_state != presentation.instance_state
            or policy.subject_digest_salt_digest != inspection_policy.subject_digest_salt_digest
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_source_invalid"
            )
        self._require_scope(actor, presentation.organization_id, presentation.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        expected_assignee = (
            assignment.domain_reviewer_subject_digest
            if presentation.track_code == "review-track.domain"
            else assignment.security_reviewer_subject_digest
        )
        browser_digest = self._digest(
            [inspection_policy.browser_binding_key_digest, browser_session_id]
        )
        secret = lease_secrets.get(presentation.track_code)
        secret_digest = (
            self._digest([lease.inspection_policy_digest, "lease-secret", secret])
            if secret
            else None
        )
        if (
            subject_digest != lease.lease_holder_subject_digest
            or subject_digest != presentation.lease_holder_subject_digest
            or subject_digest != expected_assignee
            or browser_digest != lease.browser_session_binding_digest
            or browser_digest != presentation.browser_session_binding_digest
            or secret_digest != lease.lease_secret_digest
        ):
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_source_not_found"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            correlation_id=correlation_id,
        )
        return source, policy

    async def _reuse(
        self,
        claim: OperationalKnowledgeTrackReviewDecisionClaim,
        *,
        source: ReviewDecisionSourceBundle,
        policy: OperationalKnowledgeTrackReviewDecisionPolicySnapshot,
        subject_digest: str,
        browser_digest: str,
        request_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> OperationalKnowledgeTrackReviewDecisionGrant:
        del source, policy
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_idempotency_conflict"
            )
        self._verify_claim(claim)
        record = await self._repository.get(decision_id=claim.decision_id)
        if record is None:
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_already_claimed"
            )
        self._verify_record(record)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_track_review_decision_read",
            record.decision_id,
            (("track_code", record.track_code),),
            permission_id=KNOWLEDGE_TRACK_REVIEW_DECISION_READ,
        )
        return await self._grant(replace(record, reused=True))

    async def _grant(
        self, record: OperationalKnowledgeTrackReviewDecisionRecord
    ) -> OperationalKnowledgeTrackReviewDecisionGrant:
        records = await self._repository.list_by_review_request(
            review_request_id=record.review_request_id
        )
        tracks: dict[str, OperationalKnowledgeTrackReviewDecisionRecord] = {}
        for candidate in records:
            self._verify_record(candidate)
            if (
                candidate.source_assignment_set_id != record.source_assignment_set_id
                or candidate.source_draft_id != record.source_draft_id
                or candidate.source_draft_digest != record.source_draft_digest
            ):
                raise OperationalKnowledgeTrackReviewDecisionError(
                    "operational_knowledge_track_review_decision_aggregate_integrity_failed"
                )
            prior = tracks.get(candidate.track_code)
            if prior is not None and prior.decision_id != candidate.decision_id:
                raise OperationalKnowledgeTrackReviewDecisionError(
                    "operational_knowledge_track_review_decision_aggregate_integrity_failed"
                )
            tracks[candidate.track_code] = candidate
        all_decided = set(tracks) == {"review-track.domain", "review-track.security"}
        any_correction = any(item.correction_required for item in tracks.values())
        all_passed = (
            all_decided
            and not any_correction
            and all(
                item.disposition_code == "review-disposition.passed" for item in tracks.values()
            )
        )
        return OperationalKnowledgeTrackReviewDecisionGrant(
            record=record,
            all_tracks_decided=all_decided,
            all_tracks_passed=all_passed,
            any_correction_required=any_correction,
            track_decisions=tuple(
                OperationalKnowledgeTrackDecisionBinding(
                    track_code=item.track_code,
                    decision_id=item.decision_id,
                    canonical_digest=item.canonical_digest,
                    disposition_code=item.disposition_code,
                )
                for item in sorted(tracks.values(), key=lambda value: value.track_code)
            ),
        )

    def _instruction(
        self,
        claim: OperationalKnowledgeTrackReviewDecisionClaim,
        presentation: OperationalKnowledgeFindingPresentationRecord,
        policy: OperationalKnowledgeTrackReviewDecisionPolicySnapshot,
        basis_codes: tuple[str, ...],
    ) -> OperationalKnowledgeTrackReviewDecisionInstruction:
        return OperationalKnowledgeTrackReviewDecisionInstruction(
            decision_id=claim.decision_id,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            source_finding_presentation_id=presentation.finding_presentation_id,
            source_finding_presentation_digest=presentation.canonical_digest,
            source_finding_packet_id=presentation.source_finding_packet_id,
            source_finding_digest=presentation.source_finding_digest,
            source_lease_id=presentation.source_lease_id,
            source_assignment_set_id=presentation.source_assignment_set_id,
            review_request_id=presentation.review_request_id,
            source_draft_id=presentation.source_draft_id,
            source_draft_digest=presentation.source_draft_digest,
            knowledge_item_id=presentation.knowledge_item_id,
            draft_version_id=presentation.draft_version_id,
            track_code=presentation.track_code,
            disposition_code=claim.disposition_code,
            basis_codes=basis_codes,
            decision_policy_digest=policy.canonical_digest,
            decided_by_subject_digest=claim.claimed_by_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            purpose_digest=claim.purpose_digest,
            decided_at=claim.claimed_at,
            expires_at=presentation.expires_at,
        )

    def _record(
        self,
        claim: OperationalKnowledgeTrackReviewDecisionClaim,
        presentation: OperationalKnowledgeFindingPresentationRecord,
        review_request: OperationalKnowledgeReviewRequestRecord,
        policy: OperationalKnowledgeTrackReviewDecisionPolicySnapshot,
        receipt: OperationalKnowledgeTrackReviewDecisionReceipt,
        basis_codes: tuple[str, ...],
        purpose: str,
    ) -> OperationalKnowledgeTrackReviewDecisionRecord:
        domain = presentation.track_code == "review-track.domain"
        passed = claim.disposition_code == "review-disposition.passed"
        record = OperationalKnowledgeTrackReviewDecisionRecord(
            decision_id=claim.decision_id,
            schema_version=DECISION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_finding_presentation_id=presentation.finding_presentation_id,
            source_finding_presentation_digest=presentation.canonical_digest,
            source_finding_packet_id=presentation.source_finding_packet_id,
            source_finding_digest=presentation.source_finding_digest,
            source_lease_id=presentation.source_lease_id,
            source_lease_digest=presentation.source_lease_digest,
            source_content_presentation_id=presentation.source_content_presentation_id,
            source_assignment_set_id=presentation.source_assignment_set_id,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            review_request_id=presentation.review_request_id,
            source_review_request_digest=review_request.canonical_digest,
            source_draft_id=presentation.source_draft_id,
            source_draft_digest=presentation.source_draft_digest,
            knowledge_item_id=presentation.knowledge_item_id,
            draft_version_id=presentation.draft_version_id,
            title=presentation.title,
            classification=presentation.classification,
            access_policy_id=presentation.access_policy_id,
            retention_policy_id=presentation.retention_policy_id,
            track_code=presentation.track_code,
            disposition_code=claim.disposition_code,
            basis_codes=basis_codes,
            basis_digest=claim.basis_digest,
            decided_by_subject_digest=claim.claimed_by_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            decision_policy_id=policy.policy_id,
            decision_policy_digest=policy.canonical_digest,
            decision_policy_version=policy.policy_version,
            attestor_id=receipt.attestor_id,
            attestation_digest=receipt.canonical_digest,
            decided_at=receipt.attested_at,
            expires_at=presentation.expires_at,
            instance_state=OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED,
            purpose=purpose,
            canonical_digest="0" * 64,
            domain_review_completed=domain,
            security_review_completed=not domain,
            domain_review_passed=domain and passed,
            security_review_passed=(not domain) and passed,
            correction_required=not passed,
        )
        return replace(record, canonical_digest=self._digest(self._record_payload(record)))

    def _verify_receipt(
        self,
        instruction: OperationalKnowledgeTrackReviewDecisionInstruction,
        receipt: OperationalKnowledgeTrackReviewDecisionReceipt,
        policy: OperationalKnowledgeTrackReviewDecisionPolicySnapshot,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.attestor_id != policy.required_attestor_id
            or receipt.attested_by != policy.required_attestor_subject_id
            or receipt.decision_id != instruction.decision_id
            or receipt.source_finding_presentation_id != instruction.source_finding_presentation_id
            or receipt.source_finding_presentation_digest
            != instruction.source_finding_presentation_digest
            or receipt.track_code != instruction.track_code
            or receipt.disposition_code != instruction.disposition_code
            or receipt.basis_digest != self._digest(instruction.basis_codes)
            or receipt.instruction_digest != self._digest(asdict(instruction))
            or not instruction.decided_at <= receipt.attested_at < instruction.expires_at
            or receipt.canonical_digest != self._receipt_digest(receipt)
        ):
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_attestation_invalid"
            )

    @classmethod
    def _verify_policy(cls, policy: OperationalKnowledgeTrackReviewDecisionPolicySnapshot) -> None:
        if policy.canonical_digest != cls._digest(cls._policy_payload(policy)):
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: OperationalKnowledgeTrackReviewDecisionClaim) -> None:
        if claim.canonical_digest != cls._digest(cls._claim_payload(claim)):
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: OperationalKnowledgeTrackReviewDecisionRecord) -> None:
        if record.canonical_digest != cls._digest(cls._record_payload(record)):
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_record_integrity_failed"
            )

    @classmethod
    def _policy_payload(
        cls, policy: OperationalKnowledgeTrackReviewDecisionPolicySnapshot
    ) -> dict[str, object]:
        payload = asdict(policy)
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _claim_payload(
        cls, claim: OperationalKnowledgeTrackReviewDecisionClaim
    ) -> dict[str, object]:
        payload = asdict(claim)
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(
        cls, record: OperationalKnowledgeTrackReviewDecisionRecord
    ) -> dict[str, object]:
        payload = asdict(record)
        payload.pop("canonical_digest")
        payload.pop("reused")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: OperationalKnowledgeTrackReviewDecisionReceipt) -> str:
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return cls._digest(payload)

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in sorted(value.items())}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        return value

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(
                OperationalKnowledgeTrackReviewDecisionService._normalize(payload),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii")
        ).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = KNOWLEDGE_TRACK_REVIEW_DECISION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-track-review-decision",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.knowledge.operational-track-review-decisions",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def build_development_operational_knowledge_track_review_decision_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalKnowledgeTrackReviewDecisionPolicySnapshot:
    digest = OperationalKnowledgeTrackReviewDecisionService._digest
    policy = OperationalKnowledgeTrackReviewDecisionPolicySnapshot(
        policy_id="operational-knowledge-track-review-decision-policy.development",
        schema_version=DECISION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.operational-knowledge-finding-presentation.v1",
        required_source_state=OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_PRESENTED,
        required_attestor_id="operational-knowledge-track-review-decision-attestor.synthetic",
        required_attestor_subject_id=(
            "subject.operational-knowledge-track-review-decision-attestor"
        ),
        required_receipt_schema=("atlas.operational-knowledge-track-review-decision-receipt.v1"),
        subject_digest_salt_digest=digest([organization_id, environment_id, "review-salt-v1"]),
        maximum_authentication_age_minutes=15,
        allowed_dispositions=tuple(sorted(DISPOSITIONS)),
        domain_basis_codes=(
            "review-basis.technical-accuracy",
            "review-basis.applicability",
            "review-basis.operational-safety",
            "review-basis.evidence-quality",
        ),
        security_basis_codes=(
            "review-basis.access-control",
            "review-basis.sensitive-data",
            "review-basis.unsafe-instruction",
            "review-basis.policy-compliance",
        ),
        maximum_basis_codes=4,
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        signed_by="subject.operational-knowledge-track-review-decision-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(
            OperationalKnowledgeTrackReviewDecisionService._policy_payload(policy)
        ),
    )
