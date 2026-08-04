from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import UpgradeChangeReviewPacketModel
from atlas.modules.change_review.domain.packet import (
    ChangeReviewState,
    UpgradeChangeReviewPacket,
)


class PostgreSQLChangeReviewPacketRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLChangeReviewPacketRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, actor_id: str, idempotency_key: str) -> UpgradeChangeReviewPacket | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(UpgradeChangeReviewPacketModel).where(
                    UpgradeChangeReviewPacketModel.actor_id == actor_id,
                    UpgradeChangeReviewPacketModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, record: UpgradeChangeReviewPacket) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    UpgradeChangeReviewPacketModel(
                        packet_id=record.packet_id,
                        schema_version=record.schema_version,
                        state=record.state.value,
                        actor_id=record.actor_id,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        site_id=record.site_id,
                        source_run_id=record.source_run_id,
                        source_run_version=record.source_run_version,
                        preview_id=record.preview_id,
                        preview_digest=record.preview_digest,
                        plan_id=record.plan_id,
                        plan_digest=record.plan_digest,
                        simulation_id=record.simulation_id,
                        simulation_digest=record.simulation_digest,
                        backup_id=record.backup_id,
                        restore_validation_id=record.restore_validation_id,
                        risk_class=record.risk_class,
                        change_class=record.change_class,
                        impacted_service_ids=list(record.impacted_service_ids),
                        migration_step_ids=list(record.migration_step_ids),
                        abort_criterion_ids=list(record.abort_criterion_ids),
                        rollback_step_ids=list(record.rollback_step_ids),
                        post_verification_check_ids=list(record.post_verification_check_ids),
                        assumption_ids=list(record.assumption_ids),
                        unknown_ids=list(record.unknown_ids),
                        residual_risk_ids=list(record.residual_risk_ids),
                        owner_role_ids=list(record.owner_role_ids),
                        evidence_digests=list(record.evidence_digests),
                        proposed_window_start=record.proposed_window_start,
                        proposed_window_end=record.proposed_window_end,
                        estimated_downtime_min_minutes=(record.estimated_downtime_min_minutes),
                        estimated_downtime_max_minutes=(record.estimated_downtime_max_minutes),
                        rollback_window_minutes=record.rollback_window_minutes,
                        request_fingerprint=record.request_fingerprint,
                        idempotency_key=record.idempotency_key,
                        itsm_draft_id=record.itsm_draft_id,
                        itsm_draft_title=record.itsm_draft_title,
                        itsm_draft_digest=record.itsm_draft_digest,
                        packet_digest=record.packet_digest,
                        created_at=record.created_at,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(row: UpgradeChangeReviewPacketModel) -> UpgradeChangeReviewPacket:
        return UpgradeChangeReviewPacket(
            packet_id=row.packet_id,
            schema_version=row.schema_version,
            state=ChangeReviewState(row.state),
            actor_id=row.actor_id,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            site_id=row.site_id,
            source_run_id=row.source_run_id,
            source_run_version=row.source_run_version,
            preview_id=row.preview_id,
            preview_digest=row.preview_digest,
            plan_id=row.plan_id,
            plan_digest=row.plan_digest,
            simulation_id=row.simulation_id,
            simulation_digest=row.simulation_digest,
            backup_id=row.backup_id,
            restore_validation_id=row.restore_validation_id,
            risk_class=row.risk_class,
            change_class=row.change_class,
            impacted_service_ids=tuple(row.impacted_service_ids),
            migration_step_ids=tuple(row.migration_step_ids),
            abort_criterion_ids=tuple(row.abort_criterion_ids),
            rollback_step_ids=tuple(row.rollback_step_ids),
            post_verification_check_ids=tuple(row.post_verification_check_ids),
            assumption_ids=tuple(row.assumption_ids),
            unknown_ids=tuple(row.unknown_ids),
            residual_risk_ids=tuple(row.residual_risk_ids),
            owner_role_ids=tuple(row.owner_role_ids),
            evidence_digests=tuple(row.evidence_digests),
            proposed_window_start=row.proposed_window_start,
            proposed_window_end=row.proposed_window_end,
            estimated_downtime_min_minutes=row.estimated_downtime_min_minutes,
            estimated_downtime_max_minutes=row.estimated_downtime_max_minutes,
            rollback_window_minutes=row.rollback_window_minutes,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            itsm_draft_id=row.itsm_draft_id,
            itsm_draft_title=row.itsm_draft_title,
            itsm_draft_digest=row.itsm_draft_digest,
            packet_digest=row.packet_digest,
            created_at=row.created_at,
        )
