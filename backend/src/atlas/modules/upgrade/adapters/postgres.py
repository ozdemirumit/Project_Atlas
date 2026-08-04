from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import UpgradeSimulationModel
from atlas.modules.upgrade.domain.upgrade import (
    SimulationStep,
    SimulationStepState,
    UpgradeSimulation,
    UpgradeSimulationState,
)


class PostgreSQLUpgradeSimulationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLUpgradeSimulationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, actor_id: str, idempotency_key: str) -> UpgradeSimulation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(UpgradeSimulationModel).where(
                    UpgradeSimulationModel.actor_id == actor_id,
                    UpgradeSimulationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, record: UpgradeSimulation) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    UpgradeSimulationModel(
                        simulation_id=record.simulation_id,
                        schema_version=record.schema_version,
                        state=record.state.value,
                        actor_id=record.actor_id,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        site_id=record.site_id,
                        source_run_id=record.source_run_id,
                        source_run_version=record.source_run_version,
                        plan_id=record.plan_id,
                        plan_digest=record.plan_digest,
                        backup_id=record.backup_id,
                        restore_validation_id=record.restore_validation_id,
                        request_fingerprint=record.request_fingerprint,
                        idempotency_key=record.idempotency_key,
                        steps=[
                            {
                                "step_id": item.step_id,
                                "sequence": item.sequence,
                                "state": item.state.value,
                                "result_code": item.result_code,
                                "rollback_applicable": item.rollback_applicable,
                                "simulated_minutes": item.simulated_minutes,
                            }
                            for item in record.steps
                        ],
                        impacted_service_ids=list(record.impacted_service_ids),
                        post_verification_check_ids=list(record.post_verification_check_ids),
                        abort_injected_at_step_id=record.abort_injected_at_step_id,
                        rollback_decision=record.rollback_decision,
                        estimated_downtime_minutes=record.estimated_downtime_minutes,
                        simulation_digest=record.simulation_digest,
                        created_at=record.created_at,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(row: UpgradeSimulationModel) -> UpgradeSimulation:
        return UpgradeSimulation(
            simulation_id=row.simulation_id,
            schema_version=row.schema_version,
            state=UpgradeSimulationState(row.state),
            actor_id=row.actor_id,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            site_id=row.site_id,
            source_run_id=row.source_run_id,
            source_run_version=row.source_run_version,
            plan_id=row.plan_id,
            plan_digest=row.plan_digest,
            backup_id=row.backup_id,
            restore_validation_id=row.restore_validation_id,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            steps=tuple(
                SimulationStep(
                    step_id=item["step_id"],
                    sequence=item["sequence"],
                    state=SimulationStepState(item["state"]),
                    result_code=item["result_code"],
                    rollback_applicable=item["rollback_applicable"],
                    simulated_minutes=item["simulated_minutes"],
                )
                for item in row.steps
            ),
            impacted_service_ids=tuple(row.impacted_service_ids),
            post_verification_check_ids=tuple(row.post_verification_check_ids),
            abort_injected_at_step_id=row.abort_injected_at_step_id,
            rollback_decision=row.rollback_decision,
            estimated_downtime_minutes=row.estimated_downtime_minutes,
            simulation_digest=row.simulation_digest,
            created_at=row.created_at,
        )
