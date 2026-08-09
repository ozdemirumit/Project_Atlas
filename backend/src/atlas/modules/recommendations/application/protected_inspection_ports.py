from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.domain.protected_inspection import (
    RecommendationProtectedInspectionBrokerGrant,
    RecommendationProtectedInspectionClaim,
    RecommendationProtectedInspectionInstruction,
    RecommendationProtectedInspectionPolicySnapshot,
    RecommendationProtectedInspectionRecord,
)
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentPolicySnapshot,
    RecommendationReviewerAssignmentRecord,
)


class RecommendationProtectedInspectionError(RuntimeError):
    pass


class RecommendationProtectedInspectionUncertainError(RecommendationProtectedInspectionError):
    pass


class RecommendationProtectedInspectionSource(Protocol):
    async def protected_inspection_source(
        self, *, assignment_set_id: str
    ) -> tuple[
        RecommendationReviewerAssignmentRecord,
        RecommendationReviewerAssignmentPolicySnapshot,
    ]: ...


class RecommendationProtectedInspectionPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> RecommendationProtectedInspectionPolicySnapshot | None: ...


class RecommendationProtectedInspectionBroker(Protocol):
    async def issue(
        self, instruction: RecommendationProtectedInspectionInstruction
    ) -> RecommendationProtectedInspectionBrokerGrant: ...


class RecommendationProtectedInspectionRepository(Protocol):
    async def get(self, *, lease_id: str) -> RecommendationProtectedInspectionRecord | None: ...
    async def get_by_source_track(
        self, *, source_assignment_set_id: str, track_code: str
    ) -> RecommendationProtectedInspectionRecord | None: ...
    async def get_claim_by_source_track(
        self, *, source_assignment_set_id: str, track_code: str
    ) -> RecommendationProtectedInspectionClaim | None: ...
    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationProtectedInspectionClaim | None: ...
    async def claim(self, claim: RecommendationProtectedInspectionClaim) -> bool: ...
    async def add(self, record: RecommendationProtectedInspectionRecord) -> bool: ...
    async def close(self) -> None: ...


class RecommendationProtectedInspectionPermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...
