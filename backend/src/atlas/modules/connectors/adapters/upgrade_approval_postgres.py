from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import (
    ConnectorUpgradeApprovalDecisionModel,
    ConnectorUpgradeApprovalRequestModel,
)
from atlas.modules.connectors.application.upgrade_approval import ConnectorUpgradeApprovalService
from atlas.modules.connectors.domain.upgrade_approval import (
    ConnectorUpgradeApprovalDecision,
    ConnectorUpgradeApprovalOutcome,
    ConnectorUpgradeApprovalRequest,
)


class PostgreSQLConnectorUpgradeApprovalRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorUpgradeApprovalRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, request_id: str) -> ConnectorUpgradeApprovalRequest | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorUpgradeApprovalRequestModel, request_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_plan(self, *, plan_digest: str) -> ConnectorUpgradeApprovalRequest | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorUpgradeApprovalRequestModel).where(
                    ConnectorUpgradeApprovalRequestModel.plan_digest == plan_digest
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorUpgradeApprovalRequest | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorUpgradeApprovalRequestModel).where(
                    ConnectorUpgradeApprovalRequestModel.requested_by == requested_by,
                    ConnectorUpgradeApprovalRequestModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, request: ConnectorUpgradeApprovalRequest) -> bool:
        payload = ConnectorUpgradeApprovalService._normalize(asdict(request))
        assert isinstance(payload, dict)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorUpgradeApprovalRequestModel(
                        request_id=request.request_id,
                        source_record_id=request.source_record_id,
                        instance_id=request.instance_id,
                        connector_id=request.connector_id,
                        plan_digest=request.plan_digest,
                        candidate_receipt_id=request.candidate_receipt_id,
                        requested_by=request.requested_by,
                        idempotency_key=request.idempotency_key,
                        organization_id=request.organization_id,
                        environment_id=request.environment_id,
                        state=request.state,
                        expires_at=request.expires_at,
                        canonical_digest=request.canonical_digest,
                        payload=payload,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def get_decision(self, *, request_id: str) -> ConnectorUpgradeApprovalDecision | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorUpgradeApprovalDecisionModel).where(
                    ConnectorUpgradeApprovalDecisionModel.request_id == request_id
                )
            )
            return self._decision_to_domain(row.payload) if row else None

    async def get_decision_by_key(
        self, *, decided_by: str, idempotency_key: str
    ) -> ConnectorUpgradeApprovalDecision | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorUpgradeApprovalDecisionModel).where(
                    ConnectorUpgradeApprovalDecisionModel.decided_by == decided_by,
                    ConnectorUpgradeApprovalDecisionModel.idempotency_key == idempotency_key,
                )
            )
            return self._decision_to_domain(row.payload) if row else None

    async def add_decision(self, decision: ConnectorUpgradeApprovalDecision) -> bool:
        payload = ConnectorUpgradeApprovalService._normalize(asdict(decision))
        assert isinstance(payload, dict)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorUpgradeApprovalDecisionModel(
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
    def _to_domain(raw: dict[str, object]) -> ConnectorUpgradeApprovalRequest:
        payload = dict(raw)
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        payload["expires_at"] = datetime.fromisoformat(str(payload["expires_at"]))
        return ConnectorUpgradeApprovalRequest(**cast(Any, payload))

    @staticmethod
    def _decision_to_domain(raw: dict[str, object]) -> ConnectorUpgradeApprovalDecision:
        payload = dict(raw)
        payload["outcome"] = ConnectorUpgradeApprovalOutcome(str(payload["outcome"]))
        payload["decided_at"] = datetime.fromisoformat(str(payload["decided_at"]))
        return ConnectorUpgradeApprovalDecision(**cast(Any, payload))
