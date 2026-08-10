from __future__ import annotations

import asyncio

from atlas.modules.recommendations.domain.finding_presentation import (
    RecommendationFindingPresentationClaim,
    RecommendationFindingPresentationPolicySnapshot,
    RecommendationFindingPresentationRecord,
)


class InMemoryRecommendationFindingPresentationPolicySource:
    def __init__(
        self, policies: tuple[RecommendationFindingPresentationPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationFindingPresentationPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryRecommendationFindingPresentationRepository:
    def __init__(self) -> None:
        self._claims_by_finding: dict[str, RecommendationFindingPresentationClaim] = {}
        self._claims_by_idempotency: dict[
            tuple[str, str], RecommendationFindingPresentationClaim
        ] = {}
        self._records: dict[str, RecommendationFindingPresentationRecord] = {}
        self._record_ids_by_finding: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, finding_presentation_id: str
    ) -> RecommendationFindingPresentationRecord | None:
        return self._records.get(finding_presentation_id)

    async def get_by_source_finding(
        self, *, source_finding_packet_id: str
    ) -> RecommendationFindingPresentationRecord | None:
        record_id = self._record_ids_by_finding.get(source_finding_packet_id)
        return self._records.get(record_id) if record_id is not None else None

    async def get_claim_by_source_finding(
        self, *, source_finding_packet_id: str
    ) -> RecommendationFindingPresentationClaim | None:
        return self._claims_by_finding.get(source_finding_packet_id)

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationFindingPresentationClaim | None:
        return self._claims_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))

    async def claim(self, claim: RecommendationFindingPresentationClaim) -> bool:
        async with self._lock:
            idempotency_key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
            if (
                claim.source_finding_packet_id in self._claims_by_finding
                or idempotency_key in self._claims_by_idempotency
            ):
                return False
            self._claims_by_finding[claim.source_finding_packet_id] = claim
            self._claims_by_idempotency[idempotency_key] = claim
            return True

    async def add(self, record: RecommendationFindingPresentationRecord) -> bool:
        async with self._lock:
            if (
                record.finding_presentation_id in self._records
                or record.source_finding_packet_id in self._record_ids_by_finding
            ):
                return False
            self._records[record.finding_presentation_id] = record
            self._record_ids_by_finding[record.source_finding_packet_id] = (
                record.finding_presentation_id
            )
            return True

    async def close(self) -> None:
        return None
