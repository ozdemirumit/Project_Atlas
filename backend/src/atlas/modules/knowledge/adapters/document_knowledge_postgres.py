from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import (
    DocumentKnowledgeApprovalModel,
    DocumentKnowledgeDraftModel,
    DocumentKnowledgePreparationModel,
    DocumentKnowledgeReviewModel,
)
from atlas.modules.knowledge.domain.document_knowledge import (
    DocumentKnowledgeDraft,
    DocumentKnowledgeFinalApproval,
    DocumentKnowledgePublicationPreparation,
    DocumentKnowledgeReviewDecision,
)

_DATETIME_FIELDS = {
    "created_at",
    "decided_at",
    "prepared_at",
}


def _normalize(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _restore(payload: dict[str, Any]) -> dict[str, Any]:
    restored = dict(payload)
    for field in _DATETIME_FIELDS:
        if field in restored:
            restored[field] = datetime.fromisoformat(str(restored[field]))
    if "findings" in restored:
        restored["findings"] = tuple(restored["findings"])
    return restored


class PostgreSQLDocumentKnowledgeRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLDocumentKnowledgeRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get_draft(
        self, *, draft_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeDraft | None:
        async with self._sessions() as session:
            row = await session.get(DocumentKnowledgeDraftModel, draft_id)
        if (
            row is None
            or row.organization_id != organization_id
            or row.environment_id != environment_id
        ):
            return None
        return DocumentKnowledgeDraft(**cast(Any, _restore(row.payload)))

    async def add_draft(self, draft: DocumentKnowledgeDraft) -> bool:
        try:
            async with self._sessions() as session:
                session.add(
                    DocumentKnowledgeDraftModel(
                        draft_id=draft.draft_id,
                        organization_id=draft.organization_id,
                        environment_id=draft.environment_id,
                        protected_material_digest=draft.protected_material_digest,
                        canonical_digest=draft.canonical_digest,
                        payload=cast(Any, _normalize(asdict(draft))),
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def get_review(
        self, *, review_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeReviewDecision | None:
        async with self._sessions() as session:
            row = await session.get(DocumentKnowledgeReviewModel, review_id)
        if (
            row is None
            or row.organization_id != organization_id
            or row.environment_id != environment_id
        ):
            return None
        return DocumentKnowledgeReviewDecision(**cast(Any, _restore(row.payload)))

    async def get_review_by_draft(
        self, *, draft_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeReviewDecision | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(DocumentKnowledgeReviewModel).where(
                    DocumentKnowledgeReviewModel.draft_id == draft_id,
                    DocumentKnowledgeReviewModel.organization_id == organization_id,
                    DocumentKnowledgeReviewModel.environment_id == environment_id,
                )
            )
        return DocumentKnowledgeReviewDecision(**cast(Any, _restore(row.payload))) if row else None

    async def add_review(self, review: DocumentKnowledgeReviewDecision) -> bool:
        try:
            async with self._sessions() as session:
                session.add(
                    DocumentKnowledgeReviewModel(
                        review_id=review.review_id,
                        draft_id=review.draft_id,
                        organization_id=review.organization_id,
                        environment_id=review.environment_id,
                        canonical_digest=review.canonical_digest,
                        payload=cast(Any, _normalize(asdict(review))),
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def get_approval(
        self, *, approval_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeFinalApproval | None:
        async with self._sessions() as session:
            row = await session.get(DocumentKnowledgeApprovalModel, approval_id)
        if (
            row is None
            or row.organization_id != organization_id
            or row.environment_id != environment_id
        ):
            return None
        return DocumentKnowledgeFinalApproval(**cast(Any, _restore(row.payload)))

    async def get_approval_by_review(
        self, *, review_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeFinalApproval | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(DocumentKnowledgeApprovalModel).where(
                    DocumentKnowledgeApprovalModel.review_id == review_id,
                    DocumentKnowledgeApprovalModel.organization_id == organization_id,
                    DocumentKnowledgeApprovalModel.environment_id == environment_id,
                )
            )
        return DocumentKnowledgeFinalApproval(**cast(Any, _restore(row.payload))) if row else None

    async def add_approval(self, approval: DocumentKnowledgeFinalApproval) -> bool:
        try:
            async with self._sessions() as session:
                session.add(
                    DocumentKnowledgeApprovalModel(
                        approval_id=approval.approval_id,
                        review_id=approval.review_id,
                        organization_id=approval.organization_id,
                        environment_id=approval.environment_id,
                        canonical_digest=approval.canonical_digest,
                        payload=cast(Any, _normalize(asdict(approval))),
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def get_preparation(
        self, *, preparation_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgePublicationPreparation | None:
        async with self._sessions() as session:
            row = await session.get(DocumentKnowledgePreparationModel, preparation_id)
        if (
            row is None
            or row.organization_id != organization_id
            or row.environment_id != environment_id
        ):
            return None
        return DocumentKnowledgePublicationPreparation(**cast(Any, _restore(row.payload)))

    async def get_preparation_by_approval(
        self, *, approval_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgePublicationPreparation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(DocumentKnowledgePreparationModel).where(
                    DocumentKnowledgePreparationModel.approval_id == approval_id,
                    DocumentKnowledgePreparationModel.organization_id == organization_id,
                    DocumentKnowledgePreparationModel.environment_id == environment_id,
                )
            )
        return (
            DocumentKnowledgePublicationPreparation(**cast(Any, _restore(row.payload)))
            if row
            else None
        )

    async def add_preparation(self, preparation: DocumentKnowledgePublicationPreparation) -> bool:
        try:
            async with self._sessions() as session:
                session.add(
                    DocumentKnowledgePreparationModel(
                        preparation_id=preparation.preparation_id,
                        approval_id=preparation.approval_id,
                        organization_id=preparation.organization_id,
                        environment_id=preparation.environment_id,
                        canonical_digest=preparation.canonical_digest,
                        payload=cast(Any, _normalize(asdict(preparation))),
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def close(self) -> None:
        await self._engine.dispose()
