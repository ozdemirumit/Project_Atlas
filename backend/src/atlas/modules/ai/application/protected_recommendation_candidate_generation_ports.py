from __future__ import annotations

from typing import Protocol

from atlas.modules.ai.domain.protected_answer_presentation import ProtectedPresentedAnswer
from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationReport,
)
from atlas.modules.ai.domain.protected_model_invocation import ProtectedModelResponseDraft
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateClaim,
    ProtectedRecommendationCandidateInstruction,
    ProtectedRecommendationCandidatePolicySnapshot,
    ProtectedRecommendationCandidateReceipt,
    ProtectedRecommendationCandidateRecord,
    ProtectedRecommendationCandidateSet,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextPackage


class ProtectedRecommendationCandidateError(RuntimeError):
    pass


class ProtectedRecommendationCandidateUncertainError(ProtectedRecommendationCandidateError):
    pass


class ProtectedRecommendationCandidateRepository(Protocol):
    async def claim(self, claim: ProtectedRecommendationCandidateClaim) -> bool: ...

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedRecommendationCandidateClaim | None: ...

    async def get_claim_by_presentation(
        self, *, presentation_id: str
    ) -> ProtectedRecommendationCandidateClaim | None: ...

    async def save(self, record: ProtectedRecommendationCandidateRecord) -> None: ...

    async def get(
        self, *, candidate_set_id: str
    ) -> ProtectedRecommendationCandidateRecord | None: ...

    async def close(self) -> None: ...


class ProtectedRecommendationCandidatePolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ProtectedRecommendationCandidatePolicySnapshot | None: ...


class ProtectedRecommendationCandidatePermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None: ...


class TrustedProtectedRecommendationCandidateGenerator(Protocol):
    async def generate(
        self,
        instruction: ProtectedRecommendationCandidateInstruction,
        answer: ProtectedPresentedAnswer,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedRecommendationCandidateReceipt, ProtectedRecommendationCandidateSet]: ...

    async def rehydrate(
        self,
        *,
        record: ProtectedRecommendationCandidateRecord,
        generation_authorization_digest: str,
        answer: ProtectedPresentedAnswer,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedRecommendationCandidateReceipt, ProtectedRecommendationCandidateSet]: ...
