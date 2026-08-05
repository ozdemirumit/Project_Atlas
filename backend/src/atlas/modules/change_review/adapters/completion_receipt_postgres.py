from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import HumanReviewCompletionReceiptModel
from atlas.modules.change_review.domain.completion_receipt import (
    CompletionStageEvidence,
    HumanReviewCompletionReceipt,
)
from atlas.modules.change_review.domain.human_review import HumanReviewOutcome


class PostgreSQLCompletionReceiptRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLCompletionReceiptRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, receipt_id: str) -> HumanReviewCompletionReceipt | None:
        async with self._sessions() as session:
            row = await session.get(HumanReviewCompletionReceiptModel, receipt_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_review_id(self, *, review_id: str) -> HumanReviewCompletionReceipt | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(HumanReviewCompletionReceiptModel).where(
                    HumanReviewCompletionReceiptModel.review_id == review_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> HumanReviewCompletionReceipt | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(HumanReviewCompletionReceiptModel).where(
                    HumanReviewCompletionReceiptModel.created_by == created_by,
                    HumanReviewCompletionReceiptModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, record: HumanReviewCompletionReceipt) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(HumanReviewCompletionReceiptModel(**self._values(record)))
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @classmethod
    def _values(cls, record: HumanReviewCompletionReceipt) -> dict[str, Any]:
        return {
            "receipt_id": record.receipt_id,
            "schema_version": record.schema_version,
            "version": record.version,
            "review_id": record.review_id,
            "review_version": record.review_version,
            "review_digest": record.review_digest,
            "review_expires_at": record.review_expires_at,
            "packet_id": record.packet_id,
            "packet_digest": record.packet_digest,
            "requester_id": record.requester_id,
            "created_by": record.created_by,
            "organization_id": record.organization_id,
            "environment_id": record.environment_id,
            "site_id": record.site_id,
            "risk_class": record.risk_class,
            "change_class": record.change_class,
            "impacted_service_ids": list(record.impacted_service_ids),
            "evidence_digests": list(record.evidence_digests),
            "proposed_window_start": record.proposed_window_start,
            "proposed_window_end": record.proposed_window_end,
            "stages": [cls._stage_values(stage) for stage in record.stages],
            "canonical_digest": record.canonical_digest,
            "request_fingerprint": record.request_fingerprint,
            "idempotency_key": record.idempotency_key,
            "created_at": record.created_at,
        }

    @staticmethod
    def _stage_values(stage: CompletionStageEvidence) -> dict[str, Any]:
        return {
            "stage_id": stage.stage_id,
            "sequence": stage.sequence,
            "required_role_id": stage.required_role_id,
            "reviewer_id": stage.reviewer_id,
            "decision_id": stage.decision_id,
            "request_version": stage.request_version,
            "outcome": stage.outcome.value,
            "rationale_digest": stage.rationale_digest,
            "acknowledged_no_authority": stage.acknowledged_no_authority,
            "decided_at": stage.decided_at.isoformat(),
        }

    @classmethod
    def _to_domain(cls, row: HumanReviewCompletionReceiptModel) -> HumanReviewCompletionReceipt:
        return HumanReviewCompletionReceipt(
            receipt_id=row.receipt_id,
            schema_version=row.schema_version,
            version=row.version,
            review_id=row.review_id,
            review_version=row.review_version,
            review_digest=row.review_digest,
            review_expires_at=row.review_expires_at,
            packet_id=row.packet_id,
            packet_digest=row.packet_digest,
            requester_id=row.requester_id,
            created_by=row.created_by,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            site_id=row.site_id,
            risk_class=row.risk_class,
            change_class=row.change_class,
            impacted_service_ids=tuple(row.impacted_service_ids),
            evidence_digests=tuple(row.evidence_digests),
            proposed_window_start=row.proposed_window_start,
            proposed_window_end=row.proposed_window_end,
            stages=tuple(
                CompletionStageEvidence(
                    stage_id=item["stage_id"],
                    sequence=item["sequence"],
                    required_role_id=item["required_role_id"],
                    reviewer_id=item["reviewer_id"],
                    decision_id=item["decision_id"],
                    request_version=item["request_version"],
                    outcome=HumanReviewOutcome(item["outcome"]),
                    rationale_digest=item["rationale_digest"],
                    acknowledged_no_authority=item["acknowledged_no_authority"],
                    decided_at=datetime.fromisoformat(item["decided_at"]),
                )
                for item in row.stages
            ),
            canonical_digest=row.canonical_digest,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            created_at=row.created_at,
        )
