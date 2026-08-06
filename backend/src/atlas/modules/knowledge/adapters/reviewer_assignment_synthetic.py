from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256

from atlas.modules.knowledge.application.reviewer_assignment_ports import (
    OperationalKnowledgeReviewerAssignmentAdapter,
    OperationalKnowledgeReviewerAssignmentError,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    ASSIGNED,
    OperationalKnowledgeReviewerAssignmentInstruction,
    OperationalKnowledgeReviewerAssignmentReceipt,
)


def _normalize(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _digest(payload: object) -> str:
    return sha256(
        json.dumps(_normalize(payload), sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


class SyntheticOperationalKnowledgeReviewerAssignmentAdapter:
    adapter_id = "operational-knowledge-reviewer-assignment-adapter.synthetic"
    attestor_id = "subject.operational-knowledge-reviewer-assignment-adapter-attestor"
    receipt_schema = "atlas.operational-knowledge-reviewer-assignment-receipt.v1"

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.call_count = 0

    async def assign_reviewers(
        self, instruction: OperationalKnowledgeReviewerAssignmentInstruction
    ) -> OperationalKnowledgeReviewerAssignmentReceipt:
        self.call_count += 1
        created_at = self._clock()
        seed = _digest(
            [
                instruction.assignment_set_id,
                instruction.review_request_digest,
                instruction.assignment_policy_digest,
            ]
        )
        domain_subject_digest = _digest(
            [instruction.subject_digest_salt_digest, "subject.synthetic-domain-reviewer"]
        )
        security_subject_digest = _digest(
            [instruction.subject_digest_salt_digest, "subject.synthetic-security-reviewer"]
        )
        if domain_subject_digest in instruction.exclusion_subject_digests:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_no_eligible_domain_reviewer"
            )
        if security_subject_digest in instruction.exclusion_subject_digests:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_no_eligible_security_reviewer"
            )
        receipt = OperationalKnowledgeReviewerAssignmentReceipt(
            assignment_set_id=instruction.assignment_set_id,
            schema_version=self.receipt_schema,
            version=1,
            adapter_id=self.adapter_id,
            attested_by=self.attestor_id,
            review_request_id=instruction.review_request_id,
            review_request_digest=instruction.review_request_digest,
            manifest_id=instruction.manifest_id,
            manifest_digest=instruction.manifest_digest,
            domain_assignment_id=f"knowledge-review-assignment.domain.{seed[:24]}",
            security_assignment_id=f"knowledge-review-assignment.security.{seed[:24]}",
            domain_reviewer_subject_digest=domain_subject_digest,
            security_reviewer_subject_digest=security_subject_digest,
            domain_track_code=instruction.domain_track_code,
            security_track_code=instruction.security_track_code,
            domain_queue_id=instruction.domain_queue_id,
            security_queue_id=instruction.security_queue_id,
            domain_status=ASSIGNED,
            security_status=ASSIGNED,
            assignment_digest=_digest([seed, "assignments"]),
            routing_digest=instruction.routing_digest,
            eligibility_digest=_digest(
                [
                    instruction.directory_source_digest,
                    instruction.domain_eligibility_profile_digest,
                    instruction.security_eligibility_profile_digest,
                ]
            ),
            separation_digest=_digest(
                [
                    *instruction.exclusion_subject_digests,
                    domain_subject_digest,
                    security_subject_digest,
                ]
            ),
            artifact_digest=_digest([seed, "encrypted-identity-references"]),
            created_at=created_at,
            expires_at=created_at + timedelta(minutes=instruction.assignment_ttl_minutes),
            directory_snapshot_current=True,
            eligibility_verified=True,
            upstream_actors_excluded=True,
            distinct_reviewers_verified=True,
            immutable_assignments_confirmed=True,
            encrypted_identity_references=True,
            transient_identity_buffers_erased=True,
            directory_channel_closed=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalKnowledgeReviewerAssignmentAdapter(
    OperationalKnowledgeReviewerAssignmentAdapter
):
    async def assign_reviewers(
        self, instruction: OperationalKnowledgeReviewerAssignmentInstruction
    ) -> OperationalKnowledgeReviewerAssignmentReceipt:
        del instruction
        raise OperationalKnowledgeReviewerAssignmentError(
            "operational_knowledge_reviewer_assignment_adapter_unavailable"
        )
