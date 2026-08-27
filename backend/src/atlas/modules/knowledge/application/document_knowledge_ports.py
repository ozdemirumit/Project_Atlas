from __future__ import annotations

from typing import Protocol

from atlas.core.protected_content import ProtectedContentStore
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.domain.document_knowledge import (
    DocumentKnowledgeDraft,
    DocumentKnowledgeFinalApproval,
    DocumentKnowledgePublicationPreparation,
    DocumentKnowledgeReviewDecision,
)


class DocumentKnowledgeError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


class DocumentKnowledgeRepository(Protocol):
    async def get_draft(
        self, *, draft_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeDraft | None: ...

    async def add_draft(self, draft: DocumentKnowledgeDraft) -> bool: ...

    async def get_review(
        self, *, review_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeReviewDecision | None: ...

    async def get_review_by_draft(
        self, *, draft_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeReviewDecision | None: ...

    async def add_review(self, review: DocumentKnowledgeReviewDecision) -> bool: ...

    async def get_approval(
        self, *, approval_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeFinalApproval | None: ...

    async def get_approval_by_review(
        self, *, review_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeFinalApproval | None: ...

    async def add_approval(self, approval: DocumentKnowledgeFinalApproval) -> bool: ...

    async def get_preparation(
        self, *, preparation_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgePublicationPreparation | None: ...

    async def get_preparation_by_approval(
        self, *, approval_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgePublicationPreparation | None: ...

    async def add_preparation(
        self, preparation: DocumentKnowledgePublicationPreparation
    ) -> bool: ...

    async def close(self) -> None: ...


class DocumentKnowledgePermissionAuthorizer(Protocol):
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        permission_id: str,
        correlation_id: str,
    ) -> None: ...


__all__ = [
    "DocumentKnowledgeError",
    "DocumentKnowledgePermissionAuthorizer",
    "DocumentKnowledgeRepository",
    "ProtectedContentStore",
]
