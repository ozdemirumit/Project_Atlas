from __future__ import annotations

from atlas.modules.knowledge.domain.document_knowledge import (
    DocumentKnowledgeDraft,
    DocumentKnowledgeFinalApproval,
    DocumentKnowledgePublicationPreparation,
    DocumentKnowledgeReviewDecision,
)


class InMemoryDocumentKnowledgeRepository:
    def __init__(self) -> None:
        self._drafts: dict[str, DocumentKnowledgeDraft] = {}
        self._reviews: dict[str, DocumentKnowledgeReviewDecision] = {}
        self._reviews_by_draft: dict[str, str] = {}
        self._approvals: dict[str, DocumentKnowledgeFinalApproval] = {}
        self._approvals_by_review: dict[str, str] = {}
        self._preparations: dict[str, DocumentKnowledgePublicationPreparation] = {}
        self._preparations_by_approval: dict[str, str] = {}

    async def get_draft(
        self, *, draft_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeDraft | None:
        draft = self._drafts.get(draft_id)
        if (
            draft is None
            or draft.organization_id != organization_id
            or draft.environment_id != environment_id
        ):
            return None
        return draft

    async def add_draft(self, draft: DocumentKnowledgeDraft) -> bool:
        if draft.draft_id in self._drafts:
            return False
        self._drafts[draft.draft_id] = draft
        return True

    async def get_review(
        self, *, review_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeReviewDecision | None:
        review = self._reviews.get(review_id)
        if (
            review is None
            or review.organization_id != organization_id
            or review.environment_id != environment_id
        ):
            return None
        return review

    async def get_review_by_draft(
        self, *, draft_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeReviewDecision | None:
        review_id = self._reviews_by_draft.get(draft_id)
        if review_id is None:
            return None
        return await self.get_review(
            review_id=review_id, organization_id=organization_id, environment_id=environment_id
        )

    async def add_review(self, review: DocumentKnowledgeReviewDecision) -> bool:
        if review.review_id in self._reviews or review.draft_id in self._reviews_by_draft:
            return False
        self._reviews[review.review_id] = review
        self._reviews_by_draft[review.draft_id] = review.review_id
        return True

    async def get_approval(
        self, *, approval_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeFinalApproval | None:
        approval = self._approvals.get(approval_id)
        if (
            approval is None
            or approval.organization_id != organization_id
            or approval.environment_id != environment_id
        ):
            return None
        return approval

    async def get_approval_by_review(
        self, *, review_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeFinalApproval | None:
        approval_id = self._approvals_by_review.get(review_id)
        if approval_id is None:
            return None
        return await self.get_approval(
            approval_id=approval_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )

    async def add_approval(self, approval: DocumentKnowledgeFinalApproval) -> bool:
        if (
            approval.approval_id in self._approvals
            or approval.review_id in self._approvals_by_review
        ):
            return False
        self._approvals[approval.approval_id] = approval
        self._approvals_by_review[approval.review_id] = approval.approval_id
        return True

    async def get_preparation(
        self, *, preparation_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgePublicationPreparation | None:
        preparation = self._preparations.get(preparation_id)
        if (
            preparation is None
            or preparation.organization_id != organization_id
            or preparation.environment_id != environment_id
        ):
            return None
        return preparation

    async def get_preparation_by_approval(
        self, *, approval_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgePublicationPreparation | None:
        preparation_id = self._preparations_by_approval.get(approval_id)
        if preparation_id is None:
            return None
        return await self.get_preparation(
            preparation_id=preparation_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )

    async def add_preparation(self, preparation: DocumentKnowledgePublicationPreparation) -> bool:
        if (
            preparation.preparation_id in self._preparations
            or preparation.approval_id in self._preparations_by_approval
        ):
            return False
        self._preparations[preparation.preparation_id] = preparation
        self._preparations_by_approval[preparation.approval_id] = preparation.preparation_id
        return True

    async def close(self) -> None:
        return None
