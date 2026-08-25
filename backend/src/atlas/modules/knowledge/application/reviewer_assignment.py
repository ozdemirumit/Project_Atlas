from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.authorization.application.bootstrap import (
    KNOWLEDGE_REVIEWER_ASSIGNMENT_CREATE,
    KNOWLEDGE_REVIEWER_ASSIGNMENT_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)
from atlas.modules.knowledge.application.reviewer_assignment_ports import (
    OperationalKnowledgeReviewerAssignmentAdapter,
    OperationalKnowledgeReviewerAssignmentError,
    OperationalKnowledgeReviewerAssignmentPermissionAuthorizer,
    OperationalKnowledgeReviewerAssignmentPolicySource,
    OperationalKnowledgeReviewerAssignmentRepository,
    OperationalKnowledgeReviewerAssignmentSource,
    OperationalKnowledgeReviewerAssignmentUncertainError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED,
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.reviewer_assignment import (
    ASSIGNED,
    OPERATIONAL_KNOWLEDGE_REVIEWERS_ASSIGNED,
    OperationalKnowledgeReviewerAssignmentClaim,
    OperationalKnowledgeReviewerAssignmentInstruction,
    OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    OperationalKnowledgeReviewerAssignmentReceipt,
    OperationalKnowledgeReviewerAssignmentRecord,
)

ASSIGNMENT_POLICY_SCHEMA = "atlas.operational-knowledge-reviewer-assignment-policy.v1"
ASSIGNMENT_CLAIM_SCHEMA = "atlas.operational-knowledge-reviewer-assignment-claim.v1"
ASSIGNMENT_RECORD_SCHEMA = "atlas.operational-knowledge-reviewer-assignment.v1"


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewerAssignmentOption:
    assignment_option_id: str
    source_review_request_id: str
    source_review_request_digest: str
    source_draft_id: str
    knowledge_item_id: str
    connector_id: str
    instance_id: str
    capability_id: str
    assignment_policy_id: str
    assignment_policy_digest: str
    assignment_policy_version: str
    assignment_policy_expires_at: datetime
    required_assurance_level: AssuranceLevel
    domain_track_code: str
    security_track_code: str
    assignment_ttl_minutes: int


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewerAssignmentClaimStatus:
    assignment_set_id: str
    schema_version: str
    source_review_request_id: str
    source_review_request_digest: str
    claimed_at: datetime
    claim_state: str
    claim_consumed: bool
    assignment_completed: bool
    automatic_retry_allowed: bool
    content_inspection_opened: bool
    knowledge_approved: bool
    knowledge_published: bool
    workflow_continued: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool


class OperationalKnowledgeReviewerAssignmentService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeReviewerAssignmentRepository,
        source: OperationalKnowledgeReviewerAssignmentSource,
        policy_source: OperationalKnowledgeReviewerAssignmentPolicySource,
        permission_authorizer: OperationalKnowledgeReviewerAssignmentPermissionAuthorizer,
        adapter: OperationalKnowledgeReviewerAssignmentAdapter,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._adapter = adapter
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_review_request_id: str,
        assignment_option_id: str,
        purpose: str,
        assignment_only_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord:
        self._require_human(actor)
        if not assignment_only_acknowledged:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_acknowledgement_required"
            )
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_request_invalid"
            )
        request_binding_digest = self._digest(
            {
                "source_review_request_id": source_review_request_id,
                "assignment_option_id": assignment_option_id,
                "actor_id": actor.subject_id,
                "organization_id": actor.organization_id,
                "environment_id": self._environment_id,
                "purpose": purpose,
            }
        )
        idempotency_digest = self._digest(
            [actor.subject_id, actor.organization_id, self._environment_id, idempotency_key]
        )
        existing = await self._repository.get_claim_by_idempotency_in_scope(
            claimed_by=actor.subject_id,
            idempotency_digest=idempotency_digest,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if existing is not None:
            return await self._reuse(existing, actor, request_binding_digest, idempotency_digest)
        try:
            source, source_actors = await self._source.reviewer_assignment_source(
                review_request_id=source_review_request_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
        except Exception as error:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_source_not_found"
            ) from error
        now = self._clock()
        self._require_scope(actor, source.organization_id, source.environment_id)
        if not self._adapter.available:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_adapter_unavailable"
            )
        policy = await self._resolve_option(
            actor=actor,
            source=source,
            assignment_option_id=assignment_option_id,
            now=now,
            correlation_id=correlation_id,
        )
        seed = self._digest(
            [
                source.organization_id,
                source.environment_id,
                source.review_request_id,
                source.canonical_digest,
                policy.canonical_digest,
            ]
        )
        assignment_set_id = f"operational-knowledge-reviewer-assignment.{seed[:24]}"
        exclusion_subject_digests = tuple(
            sorted(
                self._digest([policy.subject_digest_salt_digest, subject_id])
                for subject_id in source_actors
                | {
                    actor.subject_id,
                    policy.signed_by,
                    policy.required_adapter_attestor_id,
                }
            )
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_reviewer_assignment_requested",
            source.review_request_id,
            (("manifest_id", source.manifest_id),),
        )
        source, policy, now = await self._revalidate_before_claim(
            actor=actor,
            source=source,
            policy=policy,
        )
        claim = OperationalKnowledgeReviewerAssignmentClaim(
            claim_id=f"operational-knowledge-reviewer-assignment-claim.{seed[:24]}",
            schema_version=ASSIGNMENT_CLAIM_SCHEMA,
            version=1,
            source_review_request_id=source.review_request_id,
            source_review_request_digest=source.canonical_digest,
            assignment_set_id=assignment_set_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            claimed_by=actor.subject_id,
            purpose=purpose,
            claimed_at=now,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._claim_payload(claim)))
        if not await self._repository.claim(claim):
            prior_by_idempotency = await self._repository.get_claim_by_idempotency_in_scope(
                claimed_by=actor.subject_id,
                idempotency_digest=idempotency_digest,
                organization_id=source.organization_id,
                environment_id=source.environment_id,
            )
            if prior_by_idempotency is not None:
                return await self._reuse(
                    prior_by_idempotency,
                    actor,
                    request_binding_digest,
                    idempotency_digest,
                )
            prior = await self._repository.get_claim_by_source_in_scope(
                source_review_request_id=source.review_request_id,
                organization_id=source.organization_id,
                environment_id=source.environment_id,
            )
            if prior is None:
                raise OperationalKnowledgeReviewerAssignmentUncertainError(
                    "operational_knowledge_reviewer_assignment_claim_uncertain"
                )
            return await self._reuse(prior, actor, request_binding_digest, idempotency_digest)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_review_request_claimed_for_assignment",
            claim.claim_id,
            (("assignment_set_id", assignment_set_id),),
        )
        instruction = self._instruction(
            assignment_set_id, source, policy, exclusion_subject_digests
        )
        try:
            receipt = await self._adapter.assign_reviewers(instruction)
        except OperationalKnowledgeReviewerAssignmentError as error:
            await self._audit(
                actor,
                correlation_id,
                (
                    "operational_knowledge_reviewer_assignment_uncertain"
                    if isinstance(error, OperationalKnowledgeReviewerAssignmentUncertainError)
                    else "operational_knowledge_reviewer_assignment_failed"
                ),
                assignment_set_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_reviewer_assignment_uncertain",
                assignment_set_id,
                (("claim_persisted", "true"),),
            )
            raise OperationalKnowledgeReviewerAssignmentUncertainError(
                "operational_knowledge_reviewer_assignment_outcome_uncertain"
            ) from error
        try:
            self._verify_receipt(instruction, receipt, policy)
        except OperationalKnowledgeReviewerAssignmentUncertainError:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_reviewer_assignment_uncertain",
                assignment_set_id,
                (("claim_persisted", "true"),),
            )
            raise
        record = self._record(claim, source, policy, receipt, actor, purpose)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_reviewers_assigned",
            record.assignment_set_id,
            (("state", record.instance_state),),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source_in_scope(
                source_review_request_id=source.review_request_id,
                organization_id=source.organization_id,
                environment_id=source.environment_id,
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise OperationalKnowledgeReviewerAssignmentUncertainError(
                    "operational_knowledge_reviewer_assignment_persistence_uncertain"
                )
            return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, assignment_set_id: str, correlation_id: str
    ) -> OperationalKnowledgeReviewerAssignmentRecord:
        self._require_human(actor)
        record = await self._repository.get_in_scope(
            assignment_set_id=assignment_set_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if record is None:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_record_not_found"
            )
        record = await self._current_record(
            record,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_reviewer_assignment_read",
            record.assignment_set_id,
            (),
            permission_id=KNOWLEDGE_REVIEWER_ASSIGNMENT_READ,
        )
        return record

    async def list_assignments(
        self,
        *,
        actor: AuthenticatedSubject,
        source_review_request_id: str | None,
        correlation_id: str,
    ) -> tuple[OperationalKnowledgeReviewerAssignmentRecord, ...]:
        self._require_human(actor)
        if source_review_request_id is None:
            candidates = await self._repository.list_scope(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
        else:
            candidate = await self._repository.get_by_source_in_scope(
                source_review_request_id=source_review_request_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
            candidates = (candidate,) if candidate is not None else ()
        visible = [
            await self._current_record(
                record,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
            for record in candidates
        ]
        visible.sort(key=lambda item: item.assignment_set_id)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_reviewer_assignment_inventory_listed",
            source_review_request_id or self._environment_id,
            (("count", str(len(visible))),),
            permission_id=KNOWLEDGE_REVIEWER_ASSIGNMENT_READ,
        )
        return tuple(visible)

    async def list_inventory(
        self,
        *,
        actor: AuthenticatedSubject,
        source_review_request_id: str,
        correlation_id: str,
    ) -> tuple[
        OperationalKnowledgeReviewerAssignmentRecord
        | OperationalKnowledgeReviewerAssignmentClaimStatus,
        ...,
    ]:
        self._require_human(actor)
        record = await self._repository.get_by_source_in_scope(
            source_review_request_id=source_review_request_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if record is not None:
            entries: tuple[
                OperationalKnowledgeReviewerAssignmentRecord
                | OperationalKnowledgeReviewerAssignmentClaimStatus,
                ...,
            ] = (
                await self._current_record(
                    record,
                    organization_id=actor.organization_id,
                    environment_id=self._environment_id,
                ),
            )
        else:
            claim = await self._repository.get_claim_by_source_in_scope(
                source_review_request_id=source_review_request_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
            if claim is None:
                entries = ()
            else:
                self._verify_claim(claim)
                self._require_scope(actor, claim.organization_id, claim.environment_id)
                if claim.source_review_request_id != source_review_request_id:
                    raise OperationalKnowledgeReviewerAssignmentError(
                        "operational_knowledge_reviewer_assignment_persistence_integrity_failed"
                    )
                entries = (self._claim_status(claim),)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_reviewer_assignment_inventory_listed",
            source_review_request_id,
            (("count", str(len(entries))),),
            permission_id=KNOWLEDGE_REVIEWER_ASSIGNMENT_READ,
        )
        return entries

    async def list_options(
        self,
        *,
        actor: AuthenticatedSubject,
        source_review_request_id: str,
        correlation_id: str,
    ) -> tuple[OperationalKnowledgeReviewerAssignmentOption, ...]:
        self._require_human(actor)
        if not self._adapter.available:
            await self._audit_options(actor, correlation_id, source_review_request_id, 0)
            return ()
        try:
            source, _source_actors = await self._source.reviewer_assignment_source(
                review_request_id=source_review_request_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
        except Exception as error:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_source_not_found"
            ) from error
        self._require_scope(actor, source.organization_id, source.environment_id)
        claim = await self._repository.get_claim_by_source_in_scope(
            source_review_request_id=source.review_request_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
        )
        if claim is not None:
            self._verify_claim(claim)
            completed = await self._repository.get_by_source_in_scope(
                source_review_request_id=source.review_request_id,
                organization_id=source.organization_id,
                environment_id=source.environment_id,
            )
            if completed is not None:
                await self._current_record(
                    completed,
                    organization_id=source.organization_id,
                    environment_id=source.environment_id,
                )
            await self._audit_options(actor, correlation_id, source.review_request_id, 0)
            return ()
        options: list[OperationalKnowledgeReviewerAssignmentOption] = []
        now = self._clock()
        policies = await self._policy_source.list_scope(
            organization_id=source.organization_id,
            environment_id=source.environment_id,
        )
        for policy in policies:
            try:
                self._verify_snapshot(policy)
                self._verify_source(
                    source=source,
                    policy=policy,
                    source_digest=source.canonical_digest,
                    policy_digest=policy.canonical_digest,
                    now=now,
                )
                if not assurance_satisfies_policy(
                    actor.assurance_level, policy.required_assurance_level
                ):
                    continue
                if not self._adapter_matches_policy(policy):
                    continue
                self._require_actor_separation(actor, policy)
                await self._permission_authorizer.authorize(
                    actor=actor,
                    organization_id=source.organization_id,
                    environment_id=source.environment_id,
                    correlation_id=correlation_id,
                )
            except OperationalKnowledgeReviewerAssignmentError:
                continue
            options.append(self._option(source, policy))
        options.sort(key=lambda item: item.assignment_option_id)
        await self._audit_options(actor, correlation_id, source.review_request_id, len(options))
        return tuple(options)

    async def protected_inspection_source(
        self,
        *,
        assignment_set_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[
        OperationalKnowledgeReviewerAssignmentRecord,
        OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    ]:
        record = await self._repository.get_in_scope(
            assignment_set_id=assignment_set_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if record is None:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_record_not_found"
            )
        record, policy = await self._current_record_with_policy(
            record,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        return record, policy

    async def protected_content_lineage(
        self,
        *,
        assignment_set_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[
        OperationalKnowledgeReviewerAssignmentRecord,
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]:
        record, _policy = await self.protected_inspection_source(
            assignment_set_id=assignment_set_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        review_request, draft = await self._source.protected_content_lineage(
            review_request_id=record.source_review_request_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        if (
            review_request.review_request_id != record.source_review_request_id
            or review_request.canonical_digest != record.source_review_request_digest
            or review_request.source_draft_id != record.source_draft_id
            or review_request.source_draft_digest != record.source_draft_digest
        ):
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_lineage_invalid"
            )
        return record, review_request, draft

    async def close(self) -> None:
        await self._repository.close()

    async def _resolve_option(
        self,
        *,
        actor: AuthenticatedSubject,
        source: OperationalKnowledgeReviewRequestRecord,
        assignment_option_id: str,
        now: datetime,
        correlation_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentPolicySnapshot:
        policies = await self._policy_source.list_scope(
            organization_id=source.organization_id,
            environment_id=source.environment_id,
        )
        for policy in policies:
            try:
                self._verify_snapshot(policy)
            except OperationalKnowledgeReviewerAssignmentError:
                continue
            if self._option_id(source, policy) != assignment_option_id:
                continue
            self._verify_source(
                source=source,
                policy=policy,
                source_digest=source.canonical_digest,
                policy_digest=policy.canonical_digest,
                now=now,
            )
            if not assurance_satisfies_policy(
                actor.assurance_level, policy.required_assurance_level
            ):
                raise OperationalKnowledgeReviewerAssignmentError(
                    "operational_knowledge_reviewer_assignment_assurance_required"
                )
            if not self._adapter_matches_policy(policy):
                raise OperationalKnowledgeReviewerAssignmentError(
                    "operational_knowledge_reviewer_assignment_adapter_mismatch"
                )
            self._require_actor_separation(actor, policy)
            await self._permission_authorizer.authorize(
                actor=actor,
                organization_id=source.organization_id,
                environment_id=source.environment_id,
                correlation_id=correlation_id,
            )
            return policy
        raise OperationalKnowledgeReviewerAssignmentError(
            "operational_knowledge_reviewer_assignment_option_invalid"
        )

    async def _current_record(
        self,
        record: OperationalKnowledgeReviewerAssignmentRecord,
        *,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord:
        current, _policy = await self._current_record_with_policy(
            record,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        return current

    async def _current_record_with_policy(
        self,
        record: OperationalKnowledgeReviewerAssignmentRecord,
        *,
        organization_id: str,
        environment_id: str,
    ) -> tuple[
        OperationalKnowledgeReviewerAssignmentRecord,
        OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    ]:
        if record.organization_id != organization_id or record.environment_id != environment_id:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_persistence_integrity_failed"
            )
        self._verify_record(record)
        claim = await self._repository.get_claim_by_source_in_scope(
            source_review_request_id=record.source_review_request_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        if claim is None:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_claim_not_found"
            )
        self._verify_claim(claim)
        try:
            source, _source_actors = await self._source.reviewer_assignment_source(
                review_request_id=record.source_review_request_id,
                organization_id=record.organization_id,
                environment_id=record.environment_id,
            )
        except OperationalKnowledgeReviewerAssignmentError:
            raise
        except Exception as error:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id_in_scope(
            policy_id=record.assignment_policy_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        if policy is None:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_policy_not_found"
            )
        self._verify_snapshot(policy)
        if (
            claim.organization_id != record.organization_id
            or claim.environment_id != record.environment_id
            or claim.claim_id != record.claim_id
            or claim.assignment_set_id != record.assignment_set_id
            or claim.source_review_request_id != record.source_review_request_id
            or claim.source_review_request_digest != record.source_review_request_digest
            or claim.claimed_by != record.requested_by
            or claim.purpose != record.purpose
            or source.organization_id != record.organization_id
            or source.environment_id != record.environment_id
            or source.review_request_id != record.source_review_request_id
            or source.canonical_digest != record.source_review_request_digest
            or source.source_draft_id != record.source_draft_id
            or source.source_draft_digest != record.source_draft_digest
            or source.knowledge_item_id != record.knowledge_item_id
            or source.draft_version_id != record.draft_version_id
            or source.source_ingestion_id != record.source_ingestion_id
            or source.source_invocation_id != record.source_invocation_id
            or source.connector_id != record.connector_id
            or source.instance_id != record.instance_id
            or source.capability_id != record.capability_id
            or source.title != record.title
            or source.classification != record.classification
            or source.access_policy_id != record.access_policy_id
            or source.retention_policy_id != record.retention_policy_id
            or source.encryption_profile_id != record.encryption_profile_id
            or source.manifest_id != record.manifest_id
            or source.manifest_digest != record.manifest_digest
            or source.domain_track_code != record.domain_track_code
            or source.security_track_code != record.security_track_code
            or source.domain_queue_id != record.domain_queue_id
            or source.security_queue_id != record.security_queue_id
            or policy.canonical_digest != record.assignment_policy_digest
            or policy.policy_id != record.assignment_policy_id
            or policy.organization_id != record.organization_id
            or policy.environment_id != record.environment_id
            or policy.policy_version != record.assignment_policy_version
            or policy.required_adapter_id != record.assignment_adapter_id
        ):
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_lineage_invalid"
            )
        return record, policy

    async def _revalidate_before_claim(
        self,
        *,
        actor: AuthenticatedSubject,
        source: OperationalKnowledgeReviewRequestRecord,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    ) -> tuple[
        OperationalKnowledgeReviewRequestRecord,
        OperationalKnowledgeReviewerAssignmentPolicySnapshot,
        datetime,
    ]:
        if not self._adapter.available:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_adapter_unavailable"
            )
        try:
            current_source, _source_actors = await self._source.reviewer_assignment_source(
                review_request_id=source.review_request_id,
                organization_id=source.organization_id,
                environment_id=source.environment_id,
            )
        except OperationalKnowledgeReviewerAssignmentError:
            raise
        except Exception as error:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_source_not_found"
            ) from error
        current_policy = await self._policy_source.get_by_id_in_scope(
            policy_id=policy.policy_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
        )
        if (
            current_source.canonical_digest != source.canonical_digest
            or current_policy is None
            or current_policy.canonical_digest != policy.canonical_digest
        ):
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_option_invalid"
            )
        self._verify_snapshot(current_policy)
        now = self._clock()
        self._verify_source(
            source=current_source,
            policy=current_policy,
            source_digest=source.canonical_digest,
            policy_digest=policy.canonical_digest,
            now=now,
        )
        if not assurance_satisfies_policy(
            actor.assurance_level, current_policy.required_assurance_level
        ):
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_assurance_required"
            )
        self._require_actor_separation(actor, current_policy)
        if not self._adapter_matches_policy(current_policy):
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_adapter_mismatch"
            )
        return current_source, current_policy, now

    def _adapter_matches_policy(
        self, policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot
    ) -> bool:
        return (
            self._adapter.adapter_id == policy.required_adapter_id
            and self._adapter.attestor_id == policy.required_adapter_attestor_id
        )

    @classmethod
    def _option(
        cls,
        source: OperationalKnowledgeReviewRequestRecord,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    ) -> OperationalKnowledgeReviewerAssignmentOption:
        return OperationalKnowledgeReviewerAssignmentOption(
            assignment_option_id=cls._option_id(source, policy),
            source_review_request_id=source.review_request_id,
            source_review_request_digest=source.canonical_digest,
            source_draft_id=source.source_draft_id,
            knowledge_item_id=source.knowledge_item_id,
            connector_id=source.connector_id,
            instance_id=source.instance_id,
            capability_id=source.capability_id,
            assignment_policy_id=policy.policy_id,
            assignment_policy_digest=policy.canonical_digest,
            assignment_policy_version=policy.policy_version,
            assignment_policy_expires_at=policy.expires_at,
            required_assurance_level=policy.required_assurance_level,
            domain_track_code=source.domain_track_code,
            security_track_code=source.security_track_code,
            assignment_ttl_minutes=policy.assignment_ttl_minutes,
        )

    @classmethod
    def _option_id(
        cls,
        source: OperationalKnowledgeReviewRequestRecord,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    ) -> str:
        digest = cls._digest(
            [
                source.organization_id,
                source.environment_id,
                source.review_request_id,
                source.canonical_digest,
                policy.policy_id,
                policy.canonical_digest,
            ]
        )
        return f"operational-knowledge-reviewer-assignment-option.{digest[:24]}"

    @staticmethod
    def _require_actor_separation(
        actor: AuthenticatedSubject,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    ) -> None:
        if actor.subject_id in {policy.signed_by, policy.required_adapter_attestor_id}:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_actor_separation_required"
            )

    async def _audit_options(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        source_review_request_id: str,
        count: int,
    ) -> None:
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_reviewer_assignment_options_listed",
            source_review_request_id,
            (("count", str(count)),),
            permission_id=KNOWLEDGE_REVIEWER_ASSIGNMENT_READ,
        )

    async def _reuse(
        self,
        claim: OperationalKnowledgeReviewerAssignmentClaim,
        actor: AuthenticatedSubject,
        request_binding_digest: str,
        idempotency_digest: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord:
        self._verify_claim(claim)
        if (
            claim.claimed_by != actor.subject_id
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_idempotency_conflict"
            )
        self._require_scope(actor, claim.organization_id, claim.environment_id)
        record = await self._repository.get_in_scope(
            assignment_set_id=claim.assignment_set_id,
            organization_id=claim.organization_id,
            environment_id=claim.environment_id,
        )
        if record is None:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_already_claimed"
            )
        return replace(
            await self._current_record(
                record,
                organization_id=claim.organization_id,
                environment_id=claim.environment_id,
            ),
            reused=True,
        )

    @staticmethod
    def _claim_status(
        claim: OperationalKnowledgeReviewerAssignmentClaim,
    ) -> OperationalKnowledgeReviewerAssignmentClaimStatus:
        return OperationalKnowledgeReviewerAssignmentClaimStatus(
            assignment_set_id=claim.assignment_set_id,
            schema_version="atlas.operational-knowledge-reviewer-assignment-claim-status.v1",
            source_review_request_id=claim.source_review_request_id,
            source_review_request_digest=claim.source_review_request_digest,
            claimed_at=claim.claimed_at,
            claim_state="claim_consumed_unresolved",
            claim_consumed=True,
            assignment_completed=False,
            automatic_retry_allowed=False,
            content_inspection_opened=False,
            knowledge_approved=False,
            knowledge_published=False,
            workflow_continued=False,
            execution_authorized=False,
            deployment_approved=False,
            infrastructure_mutation_performed=False,
        )

    @staticmethod
    def _verify_source(
        *,
        source: OperationalKnowledgeReviewRequestRecord,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
        source_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        later_authority = (
            source.reviewer_assigned,
            source.content_inspection_opened,
            source.domain_review_completed,
            source.security_review_completed,
            source.correction_created,
            source.knowledge_approved,
            source.knowledge_published,
            source.chunks_created,
            source.embeddings_created,
            source.retrieval_published,
            source.model_context_available,
            source.graph_updated,
            source.scheduled,
            source.workflow_continued,
            source.execution_authorized,
            source.deployment_approved,
            source.infrastructure_mutation_performed,
        )
        if (
            source.canonical_digest != source_digest
            or policy.canonical_digest != policy_digest
            or policy.organization_id != source.organization_id
            or policy.environment_id != source.environment_id
            or policy.required_source_schema != source.schema_version
            or policy.required_source_state != source.instance_state
            or source.instance_state != OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED
            or source.knowledge_lifecycle != "review_requested"
            or not all(
                (
                    source.review_requested,
                    source.immutable_manifest_confirmed,
                    source.encrypted_at_rest,
                    source.transient_buffers_erased,
                    source.artifact_channel_closed,
                )
            )
            or any(later_authority)
            or now - source.created_at > timedelta(minutes=policy.maximum_source_age_minutes)
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_source_invalid"
            )

    @staticmethod
    def _instruction(
        assignment_set_id: str,
        source: OperationalKnowledgeReviewRequestRecord,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
        exclusion_subject_digests: tuple[str, ...],
    ) -> OperationalKnowledgeReviewerAssignmentInstruction:
        return OperationalKnowledgeReviewerAssignmentInstruction(
            assignment_set_id=assignment_set_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            review_request_id=source.review_request_id,
            review_request_digest=source.canonical_digest,
            source_draft_id=source.source_draft_id,
            source_draft_digest=source.source_draft_digest,
            knowledge_item_id=source.knowledge_item_id,
            manifest_id=source.manifest_id,
            manifest_digest=source.manifest_digest,
            routing_digest=source.routing_digest,
            governance_digest=source.governance_digest,
            domain_track_code=source.domain_track_code,
            security_track_code=source.security_track_code,
            domain_queue_id=source.domain_queue_id,
            security_queue_id=source.security_queue_id,
            domain_status=source.domain_status,
            security_status=source.security_status,
            directory_source_id=policy.directory_source_id,
            directory_source_digest=policy.directory_source_digest,
            domain_eligibility_profile_id=policy.domain_eligibility_profile_id,
            domain_eligibility_profile_digest=policy.domain_eligibility_profile_digest,
            security_eligibility_profile_id=policy.security_eligibility_profile_id,
            security_eligibility_profile_digest=policy.security_eligibility_profile_digest,
            subject_digest_salt_id=policy.subject_digest_salt_id,
            subject_digest_salt_digest=policy.subject_digest_salt_digest,
            exclusion_subject_digests=exclusion_subject_digests,
            assignment_ttl_minutes=policy.assignment_ttl_minutes,
            assignment_policy_digest=policy.canonical_digest,
        )

    @classmethod
    def _verify_receipt(
        cls,
        instruction: OperationalKnowledgeReviewerAssignmentInstruction,
        receipt: OperationalKnowledgeReviewerAssignmentReceipt,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    ) -> None:
        if (
            cls._receipt_digest(receipt) != receipt.canonical_digest
            or receipt.assignment_set_id != instruction.assignment_set_id
            or receipt.schema_version != policy.required_receipt_schema
            or receipt.adapter_id != policy.required_adapter_id
            or receipt.attested_by != policy.required_adapter_attestor_id
            or receipt.review_request_id != instruction.review_request_id
            or receipt.review_request_digest != instruction.review_request_digest
            or receipt.manifest_id != instruction.manifest_id
            or receipt.manifest_digest != instruction.manifest_digest
            or receipt.domain_track_code != instruction.domain_track_code
            or receipt.security_track_code != instruction.security_track_code
            or receipt.domain_queue_id != instruction.domain_queue_id
            or receipt.security_queue_id != instruction.security_queue_id
            or receipt.domain_status != ASSIGNED
            or receipt.security_status != ASSIGNED
            or receipt.routing_digest != instruction.routing_digest
            or receipt.domain_reviewer_subject_digest in instruction.exclusion_subject_digests
            or receipt.security_reviewer_subject_digest in instruction.exclusion_subject_digests
            or receipt.domain_reviewer_subject_digest == receipt.security_reviewer_subject_digest
            or receipt.expires_at
            != receipt.created_at + timedelta(minutes=policy.assignment_ttl_minutes)
        ):
            raise OperationalKnowledgeReviewerAssignmentUncertainError(
                "operational_knowledge_reviewer_assignment_receipt_invalid"
            )

    @classmethod
    def _record(
        cls,
        claim: OperationalKnowledgeReviewerAssignmentClaim,
        source: OperationalKnowledgeReviewRequestRecord,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
        receipt: OperationalKnowledgeReviewerAssignmentReceipt,
        actor: AuthenticatedSubject,
        purpose: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord:
        record = OperationalKnowledgeReviewerAssignmentRecord(
            assignment_set_id=receipt.assignment_set_id,
            schema_version=ASSIGNMENT_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_review_request_id=source.review_request_id,
            source_review_request_digest=source.canonical_digest,
            source_draft_id=source.source_draft_id,
            source_draft_digest=source.source_draft_digest,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            knowledge_item_id=source.knowledge_item_id,
            draft_version_id=source.draft_version_id,
            source_ingestion_id=source.source_ingestion_id,
            source_invocation_id=source.source_invocation_id,
            connector_id=source.connector_id,
            instance_id=source.instance_id,
            capability_id=source.capability_id,
            title=source.title,
            knowledge_lifecycle="reviewer_assigned",
            classification=source.classification,
            access_policy_id=source.access_policy_id,
            retention_policy_id=source.retention_policy_id,
            encryption_profile_id=source.encryption_profile_id,
            manifest_id=source.manifest_id,
            manifest_digest=source.manifest_digest,
            domain_assignment_id=receipt.domain_assignment_id,
            security_assignment_id=receipt.security_assignment_id,
            domain_reviewer_subject_digest=receipt.domain_reviewer_subject_digest,
            security_reviewer_subject_digest=receipt.security_reviewer_subject_digest,
            domain_track_code=receipt.domain_track_code,
            security_track_code=receipt.security_track_code,
            domain_queue_id=receipt.domain_queue_id,
            security_queue_id=receipt.security_queue_id,
            domain_status=receipt.domain_status,
            security_status=receipt.security_status,
            assignment_digest=receipt.assignment_digest,
            routing_digest=receipt.routing_digest,
            eligibility_digest=receipt.eligibility_digest,
            separation_digest=receipt.separation_digest,
            artifact_digest=receipt.artifact_digest,
            assignment_policy_id=policy.policy_id,
            assignment_policy_digest=policy.canonical_digest,
            assignment_policy_version=policy.policy_version,
            assignment_adapter_id=receipt.adapter_id,
            created_at=receipt.created_at,
            expires_at=receipt.expires_at,
            instance_state=OPERATIONAL_KNOWLEDGE_REVIEWERS_ASSIGNED,
            requested_by=actor.subject_id,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._digest(cls._record_payload(record)))

    @classmethod
    def _verify_snapshot(cls, policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        digest = str(payload.pop("canonical_digest"))
        if cls._digest(cls._normalize(payload)) != digest:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: OperationalKnowledgeReviewerAssignmentClaim) -> None:
        if cls._digest(cls._claim_payload(claim)) != claim.canonical_digest:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: OperationalKnowledgeReviewerAssignmentRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_record_integrity_failed"
            )

    @classmethod
    def _claim_payload(
        cls, claim: OperationalKnowledgeReviewerAssignmentClaim
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(
        cls, record: OperationalKnowledgeReviewerAssignmentRecord
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: OperationalKnowledgeReviewerAssignmentReceipt) -> str:
        payload = cast(dict[str, object], asdict(receipt))
        payload.pop("canonical_digest")
        return cls._digest(cls._normalize(payload))

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        return value

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "ascii"
            )
        ).hexdigest()

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_human_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_record_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = KNOWLEDGE_REVIEWER_ASSIGNMENT_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-reviewer-assignment",
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
                resource_type="resource.knowledge.operational-reviewer-assignments",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def _signed_policy(policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot) -> str:
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return OperationalKnowledgeReviewerAssignmentService._digest(
        OperationalKnowledgeReviewerAssignmentService._normalize(payload)
    )


def build_development_operational_knowledge_reviewer_assignment_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalKnowledgeReviewerAssignmentPolicySnapshot:
    digest = OperationalKnowledgeReviewerAssignmentService._digest
    policy = OperationalKnowledgeReviewerAssignmentPolicySnapshot(
        policy_id="operational-knowledge-reviewer-assignment-policy.development",
        schema_version=ASSIGNMENT_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.operational-knowledge-review-request.v1",
        required_source_state=OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED,
        required_adapter_id="operational-knowledge-reviewer-assignment-adapter.synthetic",
        required_adapter_attestor_id=(
            "subject.operational-knowledge-reviewer-assignment-adapter-attestor"
        ),
        required_receipt_schema="atlas.operational-knowledge-reviewer-assignment-receipt.v1",
        directory_source_id="identity-directory.synthetic-reviewers",
        directory_source_digest=digest(["synthetic-reviewer-directory", "v1"]),
        domain_eligibility_profile_id="reviewer-eligibility.operational-domain",
        domain_eligibility_profile_digest=digest(["domain", "hardware-mfa", "c3", "v1"]),
        security_eligibility_profile_id="reviewer-eligibility.knowledge-security",
        security_eligibility_profile_digest=digest(["security", "hardware-mfa", "c3", "v1"]),
        subject_digest_salt_id="subject-digest-salt.knowledge-review-assignment-v1",
        subject_digest_salt_digest=digest([organization_id, environment_id, "review-salt-v1"]),
        maximum_source_age_minutes=120,
        assignment_ttl_minutes=1440,
        require_distinct_reviewers=True,
        require_upstream_actor_exclusion=True,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        signed_by="subject.operational-knowledge-reviewer-assignment-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(policy, canonical_digest=_signed_policy(policy))
