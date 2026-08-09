from __future__ import annotations

import asyncio

from atlas.modules.recommendations.domain.protected_inspection import (
    RecommendationProtectedInspectionClaim,
    RecommendationProtectedInspectionPolicySnapshot,
    RecommendationProtectedInspectionRecord,
)


class InMemoryRecommendationProtectedInspectionPolicySource:
    def __init__(
        self, policies: tuple[RecommendationProtectedInspectionPolicySnapshot, ...]
    ) -> None:
        self._policies = {policy.policy_id: policy for policy in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationProtectedInspectionPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryRecommendationProtectedInspectionRepository:
    def __init__(self) -> None:
        self._claims_by_source_track: dict[
            tuple[str, str], RecommendationProtectedInspectionClaim
        ] = {}
        self._claims_by_idempotency: dict[
            tuple[str, str], RecommendationProtectedInspectionClaim
        ] = {}
        self._records: dict[str, RecommendationProtectedInspectionRecord] = {}
        self._record_ids_by_source_track: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, lease_id: str) -> RecommendationProtectedInspectionRecord | None:
        return self._records.get(lease_id)

    async def get_by_source_track(
        self, *, source_assignment_set_id: str, track_code: str
    ) -> RecommendationProtectedInspectionRecord | None:
        record_id = self._record_ids_by_source_track.get((source_assignment_set_id, track_code))
        return self._records.get(record_id) if record_id is not None else None

    async def get_claim_by_source_track(
        self, *, source_assignment_set_id: str, track_code: str
    ) -> RecommendationProtectedInspectionClaim | None:
        return self._claims_by_source_track.get((source_assignment_set_id, track_code))

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationProtectedInspectionClaim | None:
        return self._claims_by_idempotency.get((claimed_by_subject_digest, idempotency_digest))

    async def claim(self, claim: RecommendationProtectedInspectionClaim) -> bool:
        async with self._lock:
            source_key = (claim.source_assignment_set_id, claim.track_code)
            idempotency_key = (claim.claimed_by_subject_digest, claim.idempotency_digest)
            if (
                source_key in self._claims_by_source_track
                or idempotency_key in self._claims_by_idempotency
            ):
                return False
            self._claims_by_source_track[source_key] = claim
            self._claims_by_idempotency[idempotency_key] = claim
            return True

    async def add(self, record: RecommendationProtectedInspectionRecord) -> bool:
        async with self._lock:
            source_key = (record.source_assignment_set_id, record.track_code)
            if record.lease_id in self._records or source_key in self._record_ids_by_source_track:
                return False
            self._records[record.lease_id] = record
            self._record_ids_by_source_track[source_key] = record.lease_id
            return True

    async def close(self) -> None:
        return None
