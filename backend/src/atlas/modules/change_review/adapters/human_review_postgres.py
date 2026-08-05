from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import UpgradeChangeHumanReviewModel
from atlas.modules.change_review.domain.human_review import (
    HumanReviewDecision,
    HumanReviewOutcome,
    HumanReviewStage,
    HumanReviewStageState,
    HumanReviewState,
    UpgradeChangeHumanReview,
)


class PostgreSQLHumanReviewRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLHumanReviewRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, review_id: str) -> UpgradeChangeHumanReview | None:
        async with self._sessions() as session:
            row = await session.get(UpgradeChangeHumanReviewModel, review_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, requester_id: str, idempotency_key: str
    ) -> UpgradeChangeHumanReview | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(UpgradeChangeHumanReviewModel).where(
                    UpgradeChangeHumanReviewModel.requester_id == requester_id,
                    UpgradeChangeHumanReviewModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        site_id: str,
        limit: int,
    ) -> tuple[UpgradeChangeHumanReview, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(UpgradeChangeHumanReviewModel)
                    .where(
                        UpgradeChangeHumanReviewModel.organization_id == organization_id,
                        UpgradeChangeHumanReviewModel.environment_id == environment_id,
                        UpgradeChangeHumanReviewModel.site_id == site_id,
                        UpgradeChangeHumanReviewModel.state == HumanReviewState.PENDING.value,
                    )
                    .order_by(
                        UpgradeChangeHumanReviewModel.expires_at,
                        UpgradeChangeHumanReviewModel.review_id,
                    )
                    .limit(limit)
                )
            ).all()
            return tuple(self._to_domain(row) for row in rows)

    async def add(self, record: UpgradeChangeHumanReview) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(UpgradeChangeHumanReviewModel(**self._values(record)))
        except IntegrityError:
            return False
        return True

    async def update(self, record: UpgradeChangeHumanReview, *, expected_version: int) -> bool:
        values = self._values(record)
        values.pop("review_id")
        async with self._sessions.begin() as session:
            result = await session.execute(
                update(UpgradeChangeHumanReviewModel)
                .where(
                    UpgradeChangeHumanReviewModel.review_id == record.review_id,
                    UpgradeChangeHumanReviewModel.version == expected_version,
                )
                .values(**values)
            )
            return cast(CursorResult[Any], result).rowcount == 1

    async def close(self) -> None:
        await self._engine.dispose()

    @classmethod
    def _values(cls, record: UpgradeChangeHumanReview) -> dict[str, Any]:
        return {
            "review_id": record.review_id,
            "schema_version": record.schema_version,
            "version": record.version,
            "state": record.state.value,
            "packet_id": record.packet_id,
            "packet_digest": record.packet_digest,
            "requester_id": record.requester_id,
            "organization_id": record.organization_id,
            "environment_id": record.environment_id,
            "site_id": record.site_id,
            "risk_class": record.risk_class,
            "change_class": record.change_class,
            "impacted_service_ids": list(record.impacted_service_ids),
            "evidence_digests": list(record.evidence_digests),
            "proposed_window_start": record.proposed_window_start,
            "proposed_window_end": record.proposed_window_end,
            "justification": record.justification,
            "required_role_ids": list(record.required_role_ids),
            "stages": [cls._stage_values(stage) for stage in record.stages],
            "decisions": [cls._decision_values(decision) for decision in record.decisions],
            "canonical_digest": record.canonical_digest,
            "request_fingerprint": record.request_fingerprint,
            "idempotency_key": record.idempotency_key,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "expires_at": record.expires_at,
        }

    @staticmethod
    def _stage_values(stage: HumanReviewStage) -> dict[str, Any]:
        return {
            "stage_id": stage.stage_id,
            "sequence": stage.sequence,
            "required_role_id": stage.required_role_id,
            "quorum": stage.quorum,
            "state": stage.state.value,
            "packet_digest": stage.packet_digest,
            "reviewer_id": stage.reviewer_id,
            "decision_id": stage.decision_id,
            "decided_at": stage.decided_at.isoformat() if stage.decided_at else None,
            "rationale": stage.rationale,
        }

    @staticmethod
    def _decision_values(decision: HumanReviewDecision) -> dict[str, Any]:
        return {
            "decision_id": decision.decision_id,
            "stage_id": decision.stage_id,
            "request_version": decision.request_version,
            "outcome": decision.outcome.value,
            "reviewer_id": decision.reviewer_id,
            "reviewer_role_id": decision.reviewer_role_id,
            "rationale": decision.rationale,
            "acknowledged_no_authority": decision.acknowledged_no_authority,
            "idempotency_key": decision.idempotency_key,
            "request_fingerprint": decision.request_fingerprint,
            "decided_at": decision.decided_at.isoformat(),
        }

    @classmethod
    def _to_domain(cls, row: UpgradeChangeHumanReviewModel) -> UpgradeChangeHumanReview:
        stages = tuple(
            HumanReviewStage(
                stage_id=item["stage_id"],
                sequence=item["sequence"],
                required_role_id=item["required_role_id"],
                quorum=item["quorum"],
                state=HumanReviewStageState(item["state"]),
                packet_digest=item["packet_digest"],
                reviewer_id=item.get("reviewer_id"),
                decision_id=item.get("decision_id"),
                decided_at=(
                    datetime.fromisoformat(item["decided_at"]) if item.get("decided_at") else None
                ),
                rationale=item.get("rationale"),
            )
            for item in row.stages
        )
        decisions = tuple(
            HumanReviewDecision(
                decision_id=item["decision_id"],
                stage_id=item["stage_id"],
                request_version=item["request_version"],
                outcome=HumanReviewOutcome(item["outcome"]),
                reviewer_id=item["reviewer_id"],
                reviewer_role_id=item["reviewer_role_id"],
                rationale=item["rationale"],
                acknowledged_no_authority=item.get("acknowledged_no_authority", False),
                idempotency_key=item["idempotency_key"],
                request_fingerprint=item["request_fingerprint"],
                decided_at=datetime.fromisoformat(item["decided_at"]),
            )
            for item in row.decisions
        )
        state = HumanReviewState(row.state)
        return UpgradeChangeHumanReview(
            review_id=row.review_id,
            schema_version=row.schema_version,
            version=row.version,
            state=state,
            packet_id=row.packet_id,
            packet_digest=row.packet_digest,
            requester_id=row.requester_id,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            site_id=row.site_id,
            risk_class=row.risk_class,
            change_class=row.change_class,
            impacted_service_ids=tuple(row.impacted_service_ids),
            evidence_digests=tuple(row.evidence_digests),
            proposed_window_start=row.proposed_window_start,
            proposed_window_end=row.proposed_window_end,
            justification=row.justification,
            required_role_ids=tuple(row.required_role_ids),
            stages=stages,
            decisions=decisions,
            canonical_digest=row.canonical_digest,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            created_at=row.created_at,
            updated_at=row.updated_at,
            expires_at=row.expires_at,
            human_review_completed=state is HumanReviewState.COMPLETED,
        )
