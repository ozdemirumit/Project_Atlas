from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import (
    OperationalKnowledgeReviewerAssignmentClaimModel,
    OperationalKnowledgeReviewerAssignmentModel,
)
from atlas.modules.knowledge.application.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentService,
)
from atlas.modules.knowledge.application.reviewer_assignment_ports import (
    OperationalKnowledgeReviewerAssignmentError,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentClaim,
    OperationalKnowledgeReviewerAssignmentRecord,
)


class PostgreSQLOperationalKnowledgeReviewerAssignmentRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(
        cls, database_url: str
    ) -> PostgreSQLOperationalKnowledgeReviewerAssignmentRepository:
        return cls(create_async_engine(database_url))

    async def get_in_scope(
        self,
        *,
        assignment_set_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeReviewerAssignmentModel).where(
                    OperationalKnowledgeReviewerAssignmentModel.assignment_set_id
                    == assignment_set_id,
                    OperationalKnowledgeReviewerAssignmentModel.organization_id == organization_id,
                    OperationalKnowledgeReviewerAssignmentModel.environment_id == environment_id,
                )
            )
            return self._record_from_row(row) if row else None

    async def get_by_source_in_scope(
        self,
        *,
        source_review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeReviewerAssignmentModel).where(
                    OperationalKnowledgeReviewerAssignmentModel.source_review_request_id
                    == source_review_request_id,
                    OperationalKnowledgeReviewerAssignmentModel.organization_id == organization_id,
                    OperationalKnowledgeReviewerAssignmentModel.environment_id == environment_id,
                )
            )
            return self._record_from_row(row) if row else None

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeReviewerAssignmentClaimModel).where(
                    OperationalKnowledgeReviewerAssignmentClaimModel.source_review_request_id
                    == source_review_request_id,
                    OperationalKnowledgeReviewerAssignmentClaimModel.organization_id
                    == organization_id,
                    OperationalKnowledgeReviewerAssignmentClaimModel.environment_id
                    == environment_id,
                )
            )
            return self._claim_from_row(row) if row else None

    async def get_claim_by_idempotency_in_scope(
        self,
        *,
        claimed_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeReviewerAssignmentClaimModel).where(
                    OperationalKnowledgeReviewerAssignmentClaimModel.claimed_by == claimed_by,
                    OperationalKnowledgeReviewerAssignmentClaimModel.idempotency_digest
                    == idempotency_digest,
                    OperationalKnowledgeReviewerAssignmentClaimModel.organization_id
                    == organization_id,
                    OperationalKnowledgeReviewerAssignmentClaimModel.environment_id
                    == environment_id,
                )
            )
            return self._claim_from_row(row) if row else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[OperationalKnowledgeReviewerAssignmentRecord, ...]:
        async with self._sessions() as session:
            rows = tuple(
                (
                    await session.scalars(
                        select(OperationalKnowledgeReviewerAssignmentModel)
                        .where(
                            OperationalKnowledgeReviewerAssignmentModel.organization_id
                            == organization_id,
                            OperationalKnowledgeReviewerAssignmentModel.environment_id
                            == environment_id,
                        )
                        .order_by(OperationalKnowledgeReviewerAssignmentModel.assignment_set_id)
                    )
                ).all()
            )
        return tuple(self._record_from_row(row) for row in rows)

    async def claim(self, claim: OperationalKnowledgeReviewerAssignmentClaim) -> bool:
        payload = OperationalKnowledgeReviewerAssignmentService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeReviewerAssignmentClaimModel(
                        claim_id=claim.claim_id,
                        source_review_request_id=claim.source_review_request_id,
                        assignment_set_id=claim.assignment_set_id,
                        claimed_by=claim.claimed_by,
                        idempotency_digest=claim.idempotency_digest,
                        organization_id=claim.organization_id,
                        environment_id=claim.environment_id,
                        canonical_digest=claim.canonical_digest,
                        payload=cast(dict[str, Any], payload),
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def add(self, record: OperationalKnowledgeReviewerAssignmentRecord) -> bool:
        payload = OperationalKnowledgeReviewerAssignmentService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeReviewerAssignmentModel(
                        assignment_set_id=record.assignment_set_id,
                        claim_id=record.claim_id,
                        source_review_request_id=record.source_review_request_id,
                        knowledge_item_id=record.knowledge_item_id,
                        requested_by=record.requested_by,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        canonical_digest=record.canonical_digest,
                        payload=cast(dict[str, Any], payload),
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def close(self) -> None:
        await self._engine.dispose()

    @classmethod
    def _claim_from_row(
        cls, row: OperationalKnowledgeReviewerAssignmentClaimModel
    ) -> OperationalKnowledgeReviewerAssignmentClaim:
        claim = cls._claim_to_domain(row.payload)
        if (
            claim.claim_id != row.claim_id
            or claim.source_review_request_id != row.source_review_request_id
            or claim.assignment_set_id != row.assignment_set_id
            or claim.claimed_by != row.claimed_by
            or claim.idempotency_digest != row.idempotency_digest
            or claim.organization_id != row.organization_id
            or claim.environment_id != row.environment_id
            or claim.canonical_digest != row.canonical_digest
        ):
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_persistence_integrity_failed"
            )
        return claim

    @classmethod
    def _record_from_row(
        cls, row: OperationalKnowledgeReviewerAssignmentModel
    ) -> OperationalKnowledgeReviewerAssignmentRecord:
        record = cls._record_to_domain(row.payload)
        if (
            record.assignment_set_id != row.assignment_set_id
            or record.claim_id != row.claim_id
            or record.source_review_request_id != row.source_review_request_id
            or record.knowledge_item_id != row.knowledge_item_id
            or record.requested_by != row.requested_by
            or record.organization_id != row.organization_id
            or record.environment_id != row.environment_id
            or record.canonical_digest != row.canonical_digest
        ):
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_persistence_integrity_failed"
            )
        return record

    @staticmethod
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeReviewerAssignmentClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeReviewerAssignmentClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeReviewerAssignmentRecord:
        payload = dict(raw)
        for field in ("created_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return OperationalKnowledgeReviewerAssignmentRecord(**cast(Any, payload))
