from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import (
    ConnectorBoundedInvocationModel,
    ConnectorInvocationConsumptionClaimModel,
)
from atlas.modules.connectors.application.bounded_invocation import (
    ConnectorBoundedInvocationService,
)
from atlas.modules.connectors.domain.bounded_invocation import (
    ConnectorBoundedInvocationRecord,
    ConnectorInvocationConsumptionClaim,
)


class PostgreSQLConnectorBoundedInvocationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorBoundedInvocationRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, invocation_id: str) -> ConnectorBoundedInvocationRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorBoundedInvocationModel, invocation_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_authorization(
        self, *, source_authorization_id: str
    ) -> ConnectorBoundedInvocationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorBoundedInvocationModel).where(
                    ConnectorBoundedInvocationModel.source_authorization_id
                    == source_authorization_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_authorization(
        self, *, source_authorization_id: str
    ) -> ConnectorInvocationConsumptionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInvocationConsumptionClaimModel).where(
                    ConnectorInvocationConsumptionClaimModel.source_authorization_id
                    == source_authorization_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> ConnectorInvocationConsumptionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInvocationConsumptionClaimModel).where(
                    ConnectorInvocationConsumptionClaimModel.claimed_by == claimed_by,
                    ConnectorInvocationConsumptionClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: ConnectorInvocationConsumptionClaim) -> bool:
        payload = ConnectorBoundedInvocationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ConnectorInvocationConsumptionClaimModel(
                        claim_id=claim.claim_id,
                        source_authorization_id=claim.source_authorization_id,
                        invocation_id=claim.invocation_id,
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

    async def add(self, record: ConnectorBoundedInvocationRecord) -> bool:
        payload = ConnectorBoundedInvocationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ConnectorBoundedInvocationModel(
                        invocation_id=record.invocation_id,
                        consumption_claim_id=record.consumption_claim_id,
                        source_authorization_id=record.source_authorization_id,
                        instance_id=record.instance_id,
                        capability_id=record.capability_id,
                        invoked_by=record.invoked_by,
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

    @staticmethod
    def _claim_to_domain(raw: dict[str, Any]) -> ConnectorInvocationConsumptionClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return ConnectorInvocationConsumptionClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> ConnectorBoundedInvocationRecord:
        payload = dict(raw)
        for field in ("started_at", "completed_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return ConnectorBoundedInvocationRecord(**cast(Any, payload))
