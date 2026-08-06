from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import (
    ConnectorPackageApprovalDecisionModel,
    ConnectorPackageApprovalRequestModel,
)
from atlas.modules.connectors.application.package_approval import PackageApprovalService
from atlas.modules.connectors.domain.package_approval import (
    ConnectorPackageApprovalDecision,
    ConnectorPackageApprovalRequest,
    PackageApprovalOutcome,
)


class PostgreSQLPackageApprovalRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageApprovalRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_request(self, *, request_id: str) -> ConnectorPackageApprovalRequest | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageApprovalRequestModel, request_id)
            return self._request_to_domain(row.payload) if row else None

    async def get_request_by_source(
        self, *, source_final_validation_id: str
    ) -> ConnectorPackageApprovalRequest | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageApprovalRequestModel).where(
                    ConnectorPackageApprovalRequestModel.source_final_validation_id
                    == source_final_validation_id
                )
            )
            return self._request_to_domain(row.payload) if row else None

    async def get_request_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorPackageApprovalRequest | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageApprovalRequestModel).where(
                    ConnectorPackageApprovalRequestModel.requested_by == requested_by,
                    ConnectorPackageApprovalRequestModel.idempotency_key == idempotency_key,
                )
            )
            return self._request_to_domain(row.payload) if row else None

    async def add_request(self, request: ConnectorPackageApprovalRequest) -> bool:
        payload = PackageApprovalService._normalize(asdict(request))
        assert isinstance(payload, dict)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorPackageApprovalRequestModel(
                        request_id=request.request_id,
                        source_final_validation_id=request.source_final_validation_id,
                        requested_by=request.requested_by,
                        idempotency_key=request.idempotency_key,
                        organization_id=request.organization_id,
                        environment_id=request.environment_id,
                        canonical_digest=request.canonical_digest,
                        payload=payload,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def get_decision(self, *, request_id: str) -> ConnectorPackageApprovalDecision | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageApprovalDecisionModel).where(
                    ConnectorPackageApprovalDecisionModel.request_id == request_id
                )
            )
            return self._decision_to_domain(row.payload) if row else None

    async def get_decision_by_create_key(
        self, *, decided_by: str, idempotency_key: str
    ) -> ConnectorPackageApprovalDecision | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageApprovalDecisionModel).where(
                    ConnectorPackageApprovalDecisionModel.decided_by == decided_by,
                    ConnectorPackageApprovalDecisionModel.idempotency_key == idempotency_key,
                )
            )
            return self._decision_to_domain(row.payload) if row else None

    async def add_decision(self, decision: ConnectorPackageApprovalDecision) -> bool:
        payload = PackageApprovalService._normalize(asdict(decision))
        assert isinstance(payload, dict)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorPackageApprovalDecisionModel(
                        decision_id=decision.decision_id,
                        request_id=decision.request_id,
                        decided_by=decision.decided_by,
                        idempotency_key=decision.idempotency_key,
                        organization_id=decision.organization_id,
                        environment_id=decision.environment_id,
                        canonical_digest=decision.canonical_digest,
                        payload=payload,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _request_to_domain(raw: dict[str, object]) -> ConnectorPackageApprovalRequest:
        payload = dict(raw)
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        payload["expires_at"] = datetime.fromisoformat(str(payload["expires_at"]))
        return ConnectorPackageApprovalRequest(**cast(Any, payload))

    @staticmethod
    def _decision_to_domain(raw: dict[str, object]) -> ConnectorPackageApprovalDecision:
        payload = dict(raw)
        payload["decided_at"] = datetime.fromisoformat(str(payload["decided_at"]))
        payload["outcome"] = PackageApprovalOutcome(str(payload["outcome"]))
        return ConnectorPackageApprovalDecision(**cast(Any, payload))
