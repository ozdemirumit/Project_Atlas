from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageLabSelfTestModel
from atlas.modules.connectors.application.lab_self_test import PackageLabSelfTestService
from atlas.modules.connectors.domain.lab_self_test import (
    ConnectorPackageLabSelfTest,
    LabCheck,
    LabCheckSeverity,
    LabCheckState,
    LabSelfTestOutcome,
)


class PostgreSQLPackageLabSelfTestRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageLabSelfTestRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, self_test_id: str) -> ConnectorPackageLabSelfTest | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageLabSelfTestModel, self_test_id)
            return self._to_domain(row.payload) if row is not None else None

    async def get_by_source_validation(
        self, *, source_runner_validation_id: str
    ) -> ConnectorPackageLabSelfTest | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageLabSelfTestModel).where(
                    ConnectorPackageLabSelfTestModel.source_runner_validation_id
                    == source_runner_validation_id
                )
            )
            return self._to_domain(row.payload) if row is not None else None

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageLabSelfTest | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageLabSelfTestModel).where(
                    ConnectorPackageLabSelfTestModel.validated_by == validated_by,
                    ConnectorPackageLabSelfTestModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row is not None else None

    async def add(self, self_test: ConnectorPackageLabSelfTest) -> bool:
        payload = PackageLabSelfTestService._normalize(
            PackageLabSelfTestService._payload(self_test)
        )
        assert isinstance(payload, dict)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorPackageLabSelfTestModel(
                        self_test_id=self_test.self_test_id,
                        source_runner_validation_id=self_test.source_runner_validation_id,
                        validated_by=self_test.validated_by,
                        idempotency_key=self_test.idempotency_key,
                        organization_id=self_test.organization_id,
                        environment_id=self_test.environment_id,
                        canonical_digest=self_test.canonical_digest,
                        payload=payload,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(raw: dict[str, object]) -> ConnectorPackageLabSelfTest:
        payload = dict(raw)
        payload["validated_at"] = datetime.fromisoformat(str(payload["validated_at"]))
        payload["outcome"] = LabSelfTestOutcome(str(payload["outcome"]))
        checks = payload.pop("checks")
        limitations = payload.pop("limitations")
        assert isinstance(checks, list) and isinstance(limitations, list)
        return ConnectorPackageLabSelfTest(
            **cast(Any, payload),
            checks=tuple(
                LabCheck(
                    code=str(item["code"]),
                    state=LabCheckState(str(item["state"])),
                    severity=LabCheckSeverity(str(item["severity"])),
                    summary=str(item["summary"]),
                    remediation=str(item["remediation"]),
                )
                for item in checks
                if isinstance(item, dict)
            ),
            limitations=tuple(str(item) for item in limitations),
        )
