from __future__ import annotations

from typing import Protocol

from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactClaim,
    ProtectedCandidateImpactInstruction,
    ProtectedCandidateImpactPolicySnapshot,
    ProtectedCandidateImpactReceipt,
    ProtectedCandidateImpactRecord,
    ProtectedCandidateImpactReport,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateSet,
)
from atlas.modules.graph.domain.models import StorageImpactResult
from atlas.modules.identity.domain.models import AuthenticatedSubject


class ProtectedCandidateImpactError(RuntimeError):
    pass


class ProtectedCandidateImpactUncertainError(ProtectedCandidateImpactError):
    pass


class ProtectedCandidateImpactRepository(Protocol):
    async def claim(self, claim: ProtectedCandidateImpactClaim) -> bool: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedCandidateImpactClaim | None: ...

    async def get_claim_by_candidate_set(
        self, *, candidate_set_id: str
    ) -> ProtectedCandidateImpactClaim | None: ...

    async def save(self, record: ProtectedCandidateImpactRecord) -> None: ...

    async def get(self, *, impact_analysis_id: str) -> ProtectedCandidateImpactRecord | None: ...

    async def close(self) -> None: ...


class ProtectedCandidateImpactPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedCandidateImpactPolicySnapshot | None: ...


class ProtectedCandidateImpactPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedProtectedCandidateImpactAnalyzer(Protocol):
    async def analyze(
        self,
        instruction: ProtectedCandidateImpactInstruction,
        candidate_set: ProtectedRecommendationCandidateSet,
        graph_result: StorageImpactResult,
    ) -> tuple[ProtectedCandidateImpactReceipt, ProtectedCandidateImpactReport]: ...

    async def rehydrate(
        self,
        *,
        record: ProtectedCandidateImpactRecord,
        impact_authorization_digest: str,
        candidate_set: ProtectedRecommendationCandidateSet,
        graph_result: StorageImpactResult,
    ) -> tuple[ProtectedCandidateImpactReceipt, ProtectedCandidateImpactReport]: ...
