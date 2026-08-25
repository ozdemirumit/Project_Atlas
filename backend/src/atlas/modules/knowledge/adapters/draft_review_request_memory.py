from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestClaim,
    OperationalKnowledgeReviewRequestPolicySnapshot,
    OperationalKnowledgeReviewRequestRecord,
)


class InMemoryOperationalKnowledgeReviewRequestPolicySource:
    def __init__(
        self, policies: tuple[OperationalKnowledgeReviewRequestPolicySnapshot, ...]
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
    ) -> OperationalKnowledgeReviewRequestPolicySnapshot | None:
        return self._policies.get((organization_id, environment_id, policy_id))

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[OperationalKnowledgeReviewRequestPolicySnapshot, ...]:
        return tuple(
            policy
            for (policy_organization, policy_environment, _), policy in self._policies.items()
            if policy_organization == organization_id and policy_environment == environment_id
        )


class InMemoryOperationalKnowledgeReviewRequestRepository:
    def __init__(self) -> None:
        self._claims: dict[tuple[str, str, str], OperationalKnowledgeReviewRequestClaim] = {}
        self._claims_by_source: dict[
            tuple[str, str, str], OperationalKnowledgeReviewRequestClaim
        ] = {}
        self._claims_by_idempotency: dict[
            tuple[str, str, str, str], OperationalKnowledgeReviewRequestClaim
        ] = {}
        self._records: dict[tuple[str, str, str], OperationalKnowledgeReviewRequestRecord] = {}
        self._records_by_source: dict[
            tuple[str, str, str], OperationalKnowledgeReviewRequestRecord
        ] = {}
        self._records_by_claim: dict[
            tuple[str, str, str], OperationalKnowledgeReviewRequestRecord
        ] = {}
        self._lock = asyncio.Lock()

    async def get_in_scope(
        self,
        *,
        review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewRequestRecord | None:
        return self._records.get((organization_id, environment_id, review_request_id))

    async def get_by_source_in_scope(
        self,
        *,
        source_draft_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewRequestRecord | None:
        return self._records_by_source.get((organization_id, environment_id, source_draft_id))

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_draft_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewRequestClaim | None:
        return self._claims_by_source.get((organization_id, environment_id, source_draft_id))

    async def get_claim_by_idempotency_in_scope(
        self,
        *,
        claimed_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewRequestClaim | None:
        return self._claims_by_idempotency.get(
            (organization_id, environment_id, claimed_by, idempotency_digest)
        )

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[OperationalKnowledgeReviewRequestRecord, ...]:
        return tuple(
            record
            for (record_organization, record_environment, _), record in self._records.items()
            if record_organization == organization_id and record_environment == environment_id
        )

    async def claim(self, claim: OperationalKnowledgeReviewRequestClaim) -> bool:
        async with self._lock:
            claim_key = (claim.organization_id, claim.environment_id, claim.claim_id)
            source_key = (claim.organization_id, claim.environment_id, claim.source_draft_id)
            idempotency_key = (
                claim.organization_id,
                claim.environment_id,
                claim.claimed_by,
                claim.idempotency_digest,
            )
            if (
                claim_key in self._claims
                or source_key in self._claims_by_source
                or idempotency_key in self._claims_by_idempotency
            ):
                return False
            self._claims[claim_key] = claim
            self._claims_by_source[source_key] = claim
            self._claims_by_idempotency[idempotency_key] = claim
            return True

    async def add(self, record: OperationalKnowledgeReviewRequestRecord) -> bool:
        async with self._lock:
            record_key = (
                record.organization_id,
                record.environment_id,
                record.review_request_id,
            )
            source_key = (
                record.organization_id,
                record.environment_id,
                record.source_draft_id,
            )
            claim_key = (record.organization_id, record.environment_id, record.claim_id)
            claim = self._claims.get(claim_key)
            if (
                claim is None
                or claim.review_request_id != record.review_request_id
                or claim.source_draft_id != record.source_draft_id
                or record_key in self._records
                or source_key in self._records_by_source
                or claim_key in self._records_by_claim
            ):
                return False
            self._records[record_key] = record
            self._records_by_source[source_key] = record
            self._records_by_claim[claim_key] = record
            return True

    async def close(self) -> None:
        return None
