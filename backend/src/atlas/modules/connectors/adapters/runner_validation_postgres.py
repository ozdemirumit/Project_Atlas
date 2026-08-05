from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageRunnerValidationModel
from atlas.modules.connectors.application.runner_validation import PackageRunnerValidationService
from atlas.modules.connectors.domain.runner_validation import (
    ConnectorPackageRunnerValidation,
    RunnerCheck,
    RunnerCheckSeverity,
    RunnerCheckState,
    RunnerValidationOutcome,
)


class PostgreSQLPackageRunnerValidationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageRunnerValidationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageRunnerValidation | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageRunnerValidationModel, validation_id)
            return self._to_domain(row.payload) if row is not None else None

    async def get_by_source_validation(
        self, *, source_contract_validation_id: str
    ) -> ConnectorPackageRunnerValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageRunnerValidationModel).where(
                    ConnectorPackageRunnerValidationModel.source_contract_validation_id
                    == source_contract_validation_id
                )
            )
            return self._to_domain(row.payload) if row is not None else None

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageRunnerValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageRunnerValidationModel).where(
                    ConnectorPackageRunnerValidationModel.validated_by == validated_by,
                    ConnectorPackageRunnerValidationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row is not None else None

    async def add(self, validation: ConnectorPackageRunnerValidation) -> bool:
        payload = PackageRunnerValidationService._normalize(
            PackageRunnerValidationService._payload(validation)
        )
        assert isinstance(payload, dict)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorPackageRunnerValidationModel(
                        validation_id=validation.validation_id,
                        source_contract_validation_id=validation.source_contract_validation_id,
                        validated_by=validation.validated_by,
                        idempotency_key=validation.idempotency_key,
                        organization_id=validation.organization_id,
                        environment_id=validation.environment_id,
                        canonical_digest=validation.canonical_digest,
                        payload=payload,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(raw: dict[str, object]) -> ConnectorPackageRunnerValidation:
        payload = dict(raw)
        payload["validated_at"] = datetime.fromisoformat(str(payload["validated_at"]))
        payload["outcome"] = RunnerValidationOutcome(str(payload["outcome"]))
        checks = payload.pop("checks")
        limitations = payload.pop("limitations")
        assert isinstance(checks, list) and isinstance(limitations, list)
        return ConnectorPackageRunnerValidation(
            **cast(Any, payload),
            checks=tuple(
                RunnerCheck(
                    code=str(item["code"]),
                    state=RunnerCheckState(str(item["state"])),
                    severity=RunnerCheckSeverity(str(item["severity"])),
                    summary=str(item["summary"]),
                    remediation=str(item["remediation"]),
                )
                for item in checks
                if isinstance(item, dict)
            ),
            limitations=tuple(str(item) for item in limitations),
        )
