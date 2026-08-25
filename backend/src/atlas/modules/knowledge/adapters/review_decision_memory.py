from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionClaim,
    OperationalKnowledgeTrackReviewDecisionPolicySnapshot,
    OperationalKnowledgeTrackReviewDecisionRecord,
)


class InMemoryOperationalKnowledgeTrackReviewDecisionPolicySource:
    def __init__(
        self, policies: tuple[OperationalKnowledgeTrackReviewDecisionPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> OperationalKnowledgeTrackReviewDecisionPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryOperationalKnowledgeTrackReviewDecisionRepository:
    def __init__(self) -> None:
        self._claims: dict[str, OperationalKnowledgeTrackReviewDecisionClaim] = {}
        self._claim_sources: dict[str, str] = {}
        self._claim_idempotency: dict[tuple[str, str], str] = {}
        self._records: dict[str, OperationalKnowledgeTrackReviewDecisionRecord] = {}
        self._record_sources: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, decision_id: str
    ) -> OperationalKnowledgeTrackReviewDecisionRecord | None:
        return self._records.get(decision_id)

    async def get_by_source_presentation(
        self, *, source_finding_presentation_id: str
    ) -> OperationalKnowledgeTrackReviewDecisionRecord | None:
        decision_id = self._record_sources.get(source_finding_presentation_id)
        return self._records.get(decision_id) if decision_id else None

    async def get_claim_by_source_presentation(
        self, *, source_finding_presentation_id: str
    ) -> OperationalKnowledgeTrackReviewDecisionClaim | None:
        claim_id = self._claim_sources.get(source_finding_presentation_id)
        return self._claims.get(claim_id) if claim_id else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeTrackReviewDecisionClaim | None:
        claim_id = self._claim_idempotency.get((claimed_by_subject_digest, idempotency_digest))
        return self._claims.get(claim_id) if claim_id else None

    async def list_by_review_request(
        self,
        *,
        review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...]:
        return tuple(
            record
            for record in self._records.values()
            if record.review_request_id == review_request_id
            and record.organization_id == organization_id
            and record.environment_id == environment_id
        )

    async def claim(self, claim: OperationalKnowledgeTrackReviewDecisionClaim) -> bool:
        key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
        async with self._lock:
            if (
                claim.source_finding_presentation_id in self._claim_sources
                or key in self._claim_idempotency
                or claim.claim_id in self._claims
            ):
                return False
            self._claims[claim.claim_id] = claim
            self._claim_sources[claim.source_finding_presentation_id] = claim.claim_id
            self._claim_idempotency[key] = claim.claim_id
            return True

    async def add(self, record: OperationalKnowledgeTrackReviewDecisionRecord) -> bool:
        async with self._lock:
            if (
                record.decision_id in self._records
                or record.source_finding_presentation_id in self._record_sources
            ):
                return False
            self._records[record.decision_id] = record
            self._record_sources[record.source_finding_presentation_id] = record.decision_id
            return True

    async def close(self) -> None:
        return None
