from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentClaim,
    OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    OperationalKnowledgeReviewerAssignmentRecord,
)


class InMemoryOperationalKnowledgeReviewerAssignmentPolicySource:
    def __init__(
        self, policies: tuple[OperationalKnowledgeReviewerAssignmentPolicySnapshot, ...]
    ) -> None:
        self._policies = {
            (policy.organization_id, policy.environment_id, policy.policy_id): policy
            for policy in policies
        }

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentPolicySnapshot | None:
        return self._policies.get((organization_id, environment_id, policy_id))

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[OperationalKnowledgeReviewerAssignmentPolicySnapshot, ...]:
        return tuple(
            policy
            for (candidate_organization, candidate_environment, _policy_id), policy in sorted(
                self._policies.items()
            )
            if candidate_organization == organization_id and candidate_environment == environment_id
        )


class InMemoryOperationalKnowledgeReviewerAssignmentRepository:
    def __init__(self) -> None:
        self._claims_by_source: dict[
            tuple[str, str, str], OperationalKnowledgeReviewerAssignmentClaim
        ] = {}
        self._claims_by_idempotency: dict[
            tuple[str, str, str, str], OperationalKnowledgeReviewerAssignmentClaim
        ] = {}
        self._records: dict[tuple[str, str, str], OperationalKnowledgeReviewerAssignmentRecord] = {}
        self._record_ids_by_source: dict[tuple[str, str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get_in_scope(
        self,
        *,
        assignment_set_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord | None:
        return self._records.get((organization_id, environment_id, assignment_set_id))

    async def get_by_source_in_scope(
        self,
        *,
        source_review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord | None:
        source_key = (organization_id, environment_id, source_review_request_id)
        record_id = self._record_ids_by_source.get(source_key)
        return (
            self._records.get((organization_id, environment_id, record_id))
            if record_id is not None
            else None
        )

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentClaim | None:
        return self._claims_by_source.get(
            (organization_id, environment_id, source_review_request_id)
        )

    async def get_claim_by_idempotency_in_scope(
        self,
        *,
        claimed_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentClaim | None:
        return self._claims_by_idempotency.get(
            (organization_id, environment_id, claimed_by, idempotency_digest)
        )

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[OperationalKnowledgeReviewerAssignmentRecord, ...]:
        return tuple(
            record
            for (candidate_organization, candidate_environment, _record_id), record in sorted(
                self._records.items()
            )
            if candidate_organization == organization_id and candidate_environment == environment_id
        )

    async def claim(self, claim: OperationalKnowledgeReviewerAssignmentClaim) -> bool:
        async with self._lock:
            source_key = (
                claim.organization_id,
                claim.environment_id,
                claim.source_review_request_id,
            )
            idempotency_key = (
                claim.organization_id,
                claim.environment_id,
                claim.claimed_by,
                claim.idempotency_digest,
            )
            if (
                source_key in self._claims_by_source
                or idempotency_key in self._claims_by_idempotency
            ):
                return False
            self._claims_by_source[source_key] = claim
            self._claims_by_idempotency[idempotency_key] = claim
            return True

    async def add(self, record: OperationalKnowledgeReviewerAssignmentRecord) -> bool:
        async with self._lock:
            record_key = (
                record.organization_id,
                record.environment_id,
                record.assignment_set_id,
            )
            source_key = (
                record.organization_id,
                record.environment_id,
                record.source_review_request_id,
            )
            if record_key in self._records or source_key in self._record_ids_by_source:
                return False
            self._records[record_key] = record
            self._record_ids_by_source[source_key] = record.assignment_set_id
            return True

    async def close(self) -> None:
        return None
