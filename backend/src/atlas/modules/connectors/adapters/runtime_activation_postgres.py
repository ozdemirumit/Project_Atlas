from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import (
    ConnectorRuntimeActivationClaimModel,
    ConnectorRuntimeActivationModel,
)
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
)
from atlas.modules.connectors.domain.runtime_activation import (
    ConnectorRuntimeActivationClaim,
    ConnectorRuntimeActivationRecord,
    ConnectorRuntimeHealthProbeResult,
)


class PostgreSQLConnectorRuntimeActivationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorRuntimeActivationRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, activation_id: str) -> ConnectorRuntimeActivationRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorRuntimeActivationModel, activation_id)
            return self._to_domain(row) if row else None

    async def get_in_scope(
        self,
        *,
        activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRuntimeActivationModel).where(
                    ConnectorRuntimeActivationModel.activation_id == activation_id,
                    ConnectorRuntimeActivationModel.organization_id == organization_id,
                    ConnectorRuntimeActivationModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row) if row else None

    async def get_by_brokerage_authorization(
        self, *, source_brokerage_authorization_id: str
    ) -> ConnectorRuntimeActivationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRuntimeActivationModel).where(
                    ConnectorRuntimeActivationModel.source_brokerage_authorization_id
                    == source_brokerage_authorization_id
                )
            )
            return self._to_domain(row) if row else None

    async def get_by_brokerage_authorization_in_scope(
        self,
        *,
        source_brokerage_authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRuntimeActivationModel).where(
                    ConnectorRuntimeActivationModel.source_brokerage_authorization_id
                    == source_brokerage_authorization_id,
                    ConnectorRuntimeActivationModel.organization_id == organization_id,
                    ConnectorRuntimeActivationModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row) if row else None

    async def get_by_create_key_in_scope(
        self,
        *,
        activated_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationRecord | None:
        idempotency_digest = ConnectorRuntimeActivationService._digest(
            [organization_id, environment_id, activated_by, idempotency_key]
        )
        activated_by_digest = ConnectorRuntimeActivationService._identifier_digest(activated_by)
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRuntimeActivationModel).where(
                    ConnectorRuntimeActivationModel.activated_by_digest == activated_by_digest,
                    ConnectorRuntimeActivationModel.idempotency_digest == idempotency_digest,
                    ConnectorRuntimeActivationModel.organization_id == organization_id,
                    ConnectorRuntimeActivationModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row) if row else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorRuntimeActivationRecord, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ConnectorRuntimeActivationModel)
                    .where(
                        ConnectorRuntimeActivationModel.organization_id == organization_id,
                        ConnectorRuntimeActivationModel.environment_id == environment_id,
                    )
                    .order_by(ConnectorRuntimeActivationModel.activation_id)
                )
            ).all()
            return tuple(self._to_domain(row) for row in rows)

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_brokerage_authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorRuntimeActivationClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRuntimeActivationClaimModel).where(
                    ConnectorRuntimeActivationClaimModel.source_brokerage_authorization_id
                    == source_brokerage_authorization_id,
                    ConnectorRuntimeActivationClaimModel.organization_id == organization_id,
                    ConnectorRuntimeActivationClaimModel.environment_id == environment_id,
                )
            )
            return self._claim_to_domain(row) if row else None

    async def claim(self, claim: ConnectorRuntimeActivationClaim) -> bool:
        try:
            async with self._sessions() as session:
                await self._lock_coordinates(
                    session,
                    organization_id=claim.organization_id,
                    environment_id=claim.environment_id,
                    source_brokerage_authorization_id=(claim.source_brokerage_authorization_id),
                    activated_by_digest=claim.activated_by_digest,
                    idempotency_digest=claim.idempotency_digest,
                )
                published = await session.scalar(
                    select(ConnectorRuntimeActivationModel.activation_id).where(
                        ConnectorRuntimeActivationModel.organization_id == claim.organization_id,
                        ConnectorRuntimeActivationModel.environment_id == claim.environment_id,
                        or_(
                            ConnectorRuntimeActivationModel.source_brokerage_authorization_id
                            == claim.source_brokerage_authorization_id,
                            (
                                ConnectorRuntimeActivationModel.activated_by_digest
                                == claim.activated_by_digest
                            )
                            & (
                                ConnectorRuntimeActivationModel.idempotency_digest
                                == claim.idempotency_digest
                            ),
                        ),
                    )
                )
                if published is not None:
                    await session.rollback()
                    return False
                session.add(
                    ConnectorRuntimeActivationClaimModel(
                        activation_attempt_id=claim.activation_attempt_id,
                        activation_id=claim.activation_id,
                        source_brokerage_authorization_id=(claim.source_brokerage_authorization_id),
                        organization_id=claim.organization_id,
                        environment_id=claim.environment_id,
                        activated_by_digest=claim.activated_by_digest,
                        idempotency_digest=claim.idempotency_digest,
                        replay_digest=claim.replay_digest,
                        claimed_at=claim.claimed_at,
                        expires_at=claim.expires_at,
                        state="active",
                        recovery_owner_attempt_id=None,
                        recovery_lease_expires_at=None,
                        canonical_digest=claim.canonical_digest,
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False
        except Exception:
            if await self._claim_exists_exact(claim):
                return True
            raise

    async def fence_expired_claim(
        self,
        *,
        claim: ConnectorRuntimeActivationClaim,
        recovery_attempt_id: str,
        now: datetime,
    ) -> bool:
        del now
        try:
            async with self._sessions() as session:
                await self._lock_coordinates(
                    session,
                    organization_id=claim.organization_id,
                    environment_id=claim.environment_id,
                    source_brokerage_authorization_id=claim.source_brokerage_authorization_id,
                    activated_by_digest=claim.activated_by_digest,
                    idempotency_digest=claim.idempotency_digest,
                )
                result = cast(
                    CursorResult[Any],
                    await session.execute(
                        update(ConnectorRuntimeActivationClaimModel)
                        .where(
                            ConnectorRuntimeActivationClaimModel.activation_attempt_id
                            == claim.activation_attempt_id,
                            ConnectorRuntimeActivationClaimModel.canonical_digest
                            == claim.canonical_digest,
                            ConnectorRuntimeActivationClaimModel.expires_at <= func.now(),
                            or_(
                                (ConnectorRuntimeActivationClaimModel.state == "active")
                                & (
                                    ConnectorRuntimeActivationClaimModel.recovery_owner_attempt_id
                                ).is_(None)
                                & (
                                    ConnectorRuntimeActivationClaimModel.recovery_lease_expires_at
                                ).is_(None),
                                (ConnectorRuntimeActivationClaimModel.state == "recovering")
                                & (
                                    ConnectorRuntimeActivationClaimModel.recovery_lease_expires_at
                                    <= func.now()
                                ),
                            ),
                        )
                        .values(
                            state="recovering",
                            recovery_owner_attempt_id=recovery_attempt_id,
                            recovery_lease_expires_at=(func.now() + text("INTERVAL '2 minutes'")),
                        )
                    ),
                )
                await session.commit()
                return result.rowcount == 1
        except Exception:
            if await self._recovery_fence_exists_exact(claim, recovery_attempt_id):
                return True
            raise

    async def release_claim(
        self,
        claim: ConnectorRuntimeActivationClaim,
        *,
        now: datetime,
        recovery_attempt_id: str | None = None,
    ) -> bool:
        del now
        try:
            async with self._sessions() as session:
                await self._lock_coordinates(
                    session,
                    organization_id=claim.organization_id,
                    environment_id=claim.environment_id,
                    source_brokerage_authorization_id=(claim.source_brokerage_authorization_id),
                    activated_by_digest=claim.activated_by_digest,
                    idempotency_digest=claim.idempotency_digest,
                )
                state = "recovering" if recovery_attempt_id is not None else "active"
                result = cast(
                    CursorResult[Any],
                    await session.execute(
                        delete(ConnectorRuntimeActivationClaimModel).where(
                            ConnectorRuntimeActivationClaimModel.activation_attempt_id
                            == claim.activation_attempt_id,
                            ConnectorRuntimeActivationClaimModel.canonical_digest
                            == claim.canonical_digest,
                            ConnectorRuntimeActivationClaimModel.state == state,
                            ConnectorRuntimeActivationClaimModel.recovery_owner_attempt_id.is_(None)
                            if recovery_attempt_id is None
                            else ConnectorRuntimeActivationClaimModel.recovery_owner_attempt_id
                            == recovery_attempt_id,
                            ConnectorRuntimeActivationClaimModel.recovery_lease_expires_at.is_(None)
                            if recovery_attempt_id is None
                            else ConnectorRuntimeActivationClaimModel.recovery_lease_expires_at
                            > func.now(),
                        )
                    ),
                )
                await session.commit()
                return bool(result.rowcount)
        except Exception:
            if not await self._claim_exists_exact(claim):
                return True
            raise

    async def publish(
        self,
        *,
        claim: ConnectorRuntimeActivationClaim,
        record: ConnectorRuntimeActivationRecord,
        now: datetime,
    ) -> bool:
        del now
        payload = self._storage_payload(record)
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                await self._lock_coordinates(
                    session,
                    organization_id=claim.organization_id,
                    environment_id=claim.environment_id,
                    source_brokerage_authorization_id=(claim.source_brokerage_authorization_id),
                    activated_by_digest=claim.activated_by_digest,
                    idempotency_digest=claim.idempotency_digest,
                )
                released = cast(
                    CursorResult[Any],
                    await session.execute(
                        delete(ConnectorRuntimeActivationClaimModel).where(
                            ConnectorRuntimeActivationClaimModel.activation_attempt_id
                            == claim.activation_attempt_id,
                            ConnectorRuntimeActivationClaimModel.canonical_digest
                            == claim.canonical_digest,
                            ConnectorRuntimeActivationClaimModel.state == "active",
                            ConnectorRuntimeActivationClaimModel.recovery_owner_attempt_id.is_(
                                None
                            ),
                            ConnectorRuntimeActivationClaimModel.recovery_lease_expires_at.is_(
                                None
                            ),
                            ConnectorRuntimeActivationClaimModel.expires_at > func.now(),
                        )
                    ),
                )
                if released.rowcount != 1:
                    await session.rollback()
                    return False
                session.add(
                    self._model(
                        record,
                        payload=payload,
                        activation_attempt_id=claim.activation_attempt_id,
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False
        except Exception:
            if await self._published_exact(claim, record):
                return True
            raise

    async def add(self, record: ConnectorRuntimeActivationRecord) -> bool:
        payload = self._storage_payload(record)
        activated_by_digest = ConnectorRuntimeActivationService._identifier_digest(
            record.activated_by
        )
        try:
            async with self._sessions() as session:
                await self._lock_coordinates(
                    session,
                    organization_id=record.organization_id,
                    environment_id=record.environment_id,
                    source_brokerage_authorization_id=(record.source_brokerage_authorization_id),
                    activated_by_digest=activated_by_digest,
                    idempotency_digest=record.idempotency_digest,
                )
                pending = await session.scalar(
                    select(ConnectorRuntimeActivationClaimModel.activation_attempt_id).where(
                        ConnectorRuntimeActivationClaimModel.organization_id
                        == record.organization_id,
                        ConnectorRuntimeActivationClaimModel.environment_id
                        == record.environment_id,
                        or_(
                            ConnectorRuntimeActivationClaimModel.source_brokerage_authorization_id
                            == record.source_brokerage_authorization_id,
                            (
                                ConnectorRuntimeActivationClaimModel.activated_by_digest
                                == activated_by_digest
                            )
                            & (
                                ConnectorRuntimeActivationClaimModel.idempotency_digest
                                == record.idempotency_digest
                            ),
                        ),
                    )
                )
                if pending is not None:
                    await session.rollback()
                    return False
                session.add(
                    self._model(
                        record,
                        payload=payload,
                        activation_attempt_id=None,
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def close(self) -> None:
        await self._engine.dispose()

    async def _claim_exists_exact(self, claim: ConnectorRuntimeActivationClaim) -> bool:
        async with self._sessions() as session:
            row = await session.get(
                ConnectorRuntimeActivationClaimModel,
                claim.activation_attempt_id,
            )
            return row is not None and row.canonical_digest == claim.canonical_digest

    async def _recovery_fence_exists_exact(
        self,
        claim: ConnectorRuntimeActivationClaim,
        recovery_attempt_id: str,
    ) -> bool:
        async with self._sessions() as session:
            row = await session.get(
                ConnectorRuntimeActivationClaimModel,
                claim.activation_attempt_id,
            )
            return (
                row is not None
                and row.canonical_digest == claim.canonical_digest
                and row.state == "recovering"
                and row.recovery_owner_attempt_id == recovery_attempt_id
            )

    async def _published_exact(
        self,
        claim: ConnectorRuntimeActivationClaim,
        record: ConnectorRuntimeActivationRecord,
    ) -> bool:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRuntimeActivationModel).where(
                    ConnectorRuntimeActivationModel.activation_attempt_id
                    == claim.activation_attempt_id,
                    ConnectorRuntimeActivationModel.activation_id == record.activation_id,
                    ConnectorRuntimeActivationModel.canonical_digest == record.canonical_digest,
                )
            )
            return row is not None

    @staticmethod
    def _model(
        record: ConnectorRuntimeActivationRecord,
        *,
        payload: dict[str, Any],
        activation_attempt_id: str | None,
    ) -> ConnectorRuntimeActivationModel:
        return ConnectorRuntimeActivationModel(
            activation_id=record.activation_id,
            activation_attempt_id=activation_attempt_id,
            source_brokerage_authorization_id=record.source_brokerage_authorization_id,
            instance_id=record.instance_id,
            activation_profile_id=record.activation_profile_id,
            activated_by=record.activated_by,
            activated_by_digest=ConnectorRuntimeActivationService._identifier_digest(
                record.activated_by
            ),
            idempotency_digest=record.idempotency_digest,
            replay_digest=record.replay_digest,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            canonical_digest=record.canonical_digest,
            payload=payload,
        )

    @staticmethod
    def _to_domain(
        row: ConnectorRuntimeActivationModel,
    ) -> ConnectorRuntimeActivationRecord:
        payload = dict(row.payload)
        payload["replay_digest"] = row.replay_digest
        payload["idempotency_digest"] = row.idempotency_digest
        for field in ("activated_at", "healthy_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        payload["health_probe_results"] = tuple(
            ConnectorRuntimeHealthProbeResult(**item) for item in payload["health_probe_results"]
        )
        return ConnectorRuntimeActivationRecord(**cast(Any, payload))

    @staticmethod
    def _claim_to_domain(
        row: ConnectorRuntimeActivationClaimModel,
    ) -> ConnectorRuntimeActivationClaim:
        return ConnectorRuntimeActivationClaim(
            activation_attempt_id=row.activation_attempt_id,
            activation_id=row.activation_id,
            source_brokerage_authorization_id=row.source_brokerage_authorization_id,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            activated_by_digest=row.activated_by_digest,
            idempotency_digest=row.idempotency_digest,
            replay_digest=row.replay_digest,
            claimed_at=row.claimed_at,
            expires_at=row.expires_at,
            canonical_digest=row.canonical_digest,
        )

    @staticmethod
    def _storage_payload(record: ConnectorRuntimeActivationRecord) -> dict[str, Any]:
        payload = asdict(record)
        for field in ("replay_digest", "idempotency_digest"):
            payload.pop(field)
        normalized = ConnectorRuntimeActivationService._normalize(payload)
        assert isinstance(normalized, dict)
        return cast(dict[str, Any], normalized)

    @staticmethod
    async def _lock_coordinates(
        session: AsyncSession,
        *,
        organization_id: str,
        environment_id: str,
        source_brokerage_authorization_id: str,
        activated_by_digest: str,
        idempotency_digest: str,
    ) -> None:
        coordination_keys = (
            "\x1f".join(
                (
                    "actor-idempotency",
                    organization_id,
                    environment_id,
                    activated_by_digest,
                    idempotency_digest,
                )
            ),
            "\x1f".join(
                (
                    "source",
                    organization_id,
                    environment_id,
                    source_brokerage_authorization_id,
                )
            ),
        )
        for coordination_key in sorted(coordination_keys):
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:coordination_key, 0))"),
                {"coordination_key": coordination_key},
            )
