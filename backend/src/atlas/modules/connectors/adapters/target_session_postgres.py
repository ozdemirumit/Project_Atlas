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
    ConnectorTargetSessionClaimModel,
    ConnectorTargetSessionVerificationModel,
)
from atlas.modules.connectors.application.target_session import ConnectorTargetSessionService
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetConnectivityCheckResult,
    ConnectorTargetSessionClaim,
    ConnectorTargetSessionVerificationRecord,
)


class PostgreSQLConnectorTargetSessionRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorTargetSessionRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, verification_id: str) -> ConnectorTargetSessionVerificationRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorTargetSessionVerificationModel, verification_id)
            return self._to_domain(row) if row else None

    async def get_in_scope(
        self,
        *,
        verification_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionVerificationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorTargetSessionVerificationModel).where(
                    ConnectorTargetSessionVerificationModel.verification_id == verification_id,
                    ConnectorTargetSessionVerificationModel.organization_id == organization_id,
                    ConnectorTargetSessionVerificationModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row) if row else None

    async def get_by_runtime_activation(
        self, *, source_runtime_activation_id: str
    ) -> ConnectorTargetSessionVerificationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorTargetSessionVerificationModel).where(
                    ConnectorTargetSessionVerificationModel.source_runtime_activation_id
                    == source_runtime_activation_id
                )
            )
            return self._to_domain(row) if row else None

    async def get_by_runtime_activation_in_scope(
        self,
        *,
        source_runtime_activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionVerificationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorTargetSessionVerificationModel).where(
                    ConnectorTargetSessionVerificationModel.source_runtime_activation_id
                    == source_runtime_activation_id,
                    ConnectorTargetSessionVerificationModel.organization_id == organization_id,
                    ConnectorTargetSessionVerificationModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row) if row else None

    async def get_by_create_key(
        self, *, verified_by: str, idempotency_key: str
    ) -> ConnectorTargetSessionVerificationRecord | None:
        async with self._sessions() as session:
            rows = tuple(
                (
                    await session.scalars(
                        select(ConnectorTargetSessionVerificationModel).where(
                            ConnectorTargetSessionVerificationModel.verified_by == verified_by,
                        )
                    )
                ).all()
            )
        for row in rows:
            expected = ConnectorTargetSessionService._digest(
                [row.organization_id, row.environment_id, verified_by, idempotency_key]
            )
            if row.idempotency_digest == expected:
                return self._to_domain(row)
        return None

    async def get_by_create_key_in_scope(
        self,
        *,
        verified_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionVerificationRecord | None:
        verified_by_digest = ConnectorTargetSessionService._identifier_digest(verified_by)
        idempotency_digest = ConnectorTargetSessionService._digest(
            [organization_id, environment_id, verified_by, idempotency_key]
        )
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorTargetSessionVerificationModel).where(
                    ConnectorTargetSessionVerificationModel.verified_by_digest
                    == verified_by_digest,
                    ConnectorTargetSessionVerificationModel.idempotency_digest
                    == idempotency_digest,
                    ConnectorTargetSessionVerificationModel.organization_id == organization_id,
                    ConnectorTargetSessionVerificationModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row) if row else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorTargetSessionVerificationRecord, ...]:
        async with self._sessions() as session:
            rows = tuple(
                (
                    await session.scalars(
                        select(ConnectorTargetSessionVerificationModel)
                        .where(
                            ConnectorTargetSessionVerificationModel.organization_id
                            == organization_id,
                            ConnectorTargetSessionVerificationModel.environment_id
                            == environment_id,
                        )
                        .order_by(ConnectorTargetSessionVerificationModel.verification_id)
                    )
                ).all()
            )
        return tuple(self._to_domain(row) for row in rows)

    async def get_claim_by_source_in_scope(
        self,
        *,
        source_runtime_activation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorTargetSessionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorTargetSessionClaimModel).where(
                    ConnectorTargetSessionClaimModel.source_runtime_activation_id
                    == source_runtime_activation_id,
                    ConnectorTargetSessionClaimModel.organization_id == organization_id,
                    ConnectorTargetSessionClaimModel.environment_id == environment_id,
                )
            )
            return self._claim_to_domain(row) if row else None

    async def claim(self, claim: ConnectorTargetSessionClaim) -> bool:
        try:
            async with self._sessions() as session:
                await self._lock_coordinates(
                    session,
                    organization_id=claim.organization_id,
                    environment_id=claim.environment_id,
                    source_runtime_activation_id=claim.source_runtime_activation_id,
                    verified_by_digest=claim.verified_by_digest,
                    idempotency_digest=claim.idempotency_digest,
                )
                published = await session.scalar(
                    select(ConnectorTargetSessionVerificationModel.verification_id).where(
                        ConnectorTargetSessionVerificationModel.organization_id
                        == claim.organization_id,
                        ConnectorTargetSessionVerificationModel.environment_id
                        == claim.environment_id,
                        or_(
                            ConnectorTargetSessionVerificationModel.source_runtime_activation_id
                            == claim.source_runtime_activation_id,
                            (
                                ConnectorTargetSessionVerificationModel.verified_by_digest
                                == claim.verified_by_digest
                            )
                            & (
                                ConnectorTargetSessionVerificationModel.idempotency_digest
                                == claim.idempotency_digest
                            ),
                        ),
                    )
                )
                if published is not None:
                    await session.rollback()
                    return False
                session.add(
                    ConnectorTargetSessionClaimModel(
                        verification_attempt_id=claim.verification_attempt_id,
                        verification_id=claim.verification_id,
                        source_runtime_activation_id=claim.source_runtime_activation_id,
                        organization_id=claim.organization_id,
                        environment_id=claim.environment_id,
                        verified_by_digest=claim.verified_by_digest,
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
        claim: ConnectorTargetSessionClaim,
        recovery_attempt_id: str,
        now: datetime,
    ) -> bool:
        del now
        try:
            async with self._sessions() as session:
                await self._lock_claim_coordinates(session, claim)
                result = cast(
                    CursorResult[Any],
                    await session.execute(
                        update(ConnectorTargetSessionClaimModel)
                        .where(
                            ConnectorTargetSessionClaimModel.verification_attempt_id
                            == claim.verification_attempt_id,
                            ConnectorTargetSessionClaimModel.canonical_digest
                            == claim.canonical_digest,
                            ConnectorTargetSessionClaimModel.expires_at <= func.now(),
                            or_(
                                (ConnectorTargetSessionClaimModel.state == "active")
                                & ConnectorTargetSessionClaimModel.recovery_owner_attempt_id.is_(
                                    None
                                )
                                & ConnectorTargetSessionClaimModel.recovery_lease_expires_at.is_(
                                    None
                                ),
                                (ConnectorTargetSessionClaimModel.state == "recovering")
                                & (
                                    ConnectorTargetSessionClaimModel.recovery_lease_expires_at
                                    <= func.now()
                                ),
                            ),
                        )
                        .values(
                            state="recovering",
                            recovery_owner_attempt_id=recovery_attempt_id,
                            recovery_lease_expires_at=func.now() + text("INTERVAL '5 minutes'"),
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
        claim: ConnectorTargetSessionClaim,
        *,
        now: datetime,
        recovery_attempt_id: str | None = None,
    ) -> bool:
        del now
        try:
            async with self._sessions() as session:
                await self._lock_claim_coordinates(session, claim)
                state = "recovering" if recovery_attempt_id is not None else "active"
                result = cast(
                    CursorResult[Any],
                    await session.execute(
                        delete(ConnectorTargetSessionClaimModel).where(
                            ConnectorTargetSessionClaimModel.verification_attempt_id
                            == claim.verification_attempt_id,
                            ConnectorTargetSessionClaimModel.canonical_digest
                            == claim.canonical_digest,
                            ConnectorTargetSessionClaimModel.state == state,
                            ConnectorTargetSessionClaimModel.recovery_owner_attempt_id.is_(None)
                            if recovery_attempt_id is None
                            else ConnectorTargetSessionClaimModel.recovery_owner_attempt_id
                            == recovery_attempt_id,
                            ConnectorTargetSessionClaimModel.recovery_lease_expires_at.is_(None)
                            if recovery_attempt_id is None
                            else ConnectorTargetSessionClaimModel.recovery_lease_expires_at
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
        claim: ConnectorTargetSessionClaim,
        record: ConnectorTargetSessionVerificationRecord,
        now: datetime,
    ) -> bool:
        del now
        payload = self._storage_payload(record)
        try:
            async with self._sessions() as session:
                await self._lock_claim_coordinates(session, claim)
                released = cast(
                    CursorResult[Any],
                    await session.execute(
                        delete(ConnectorTargetSessionClaimModel).where(
                            ConnectorTargetSessionClaimModel.verification_attempt_id
                            == claim.verification_attempt_id,
                            ConnectorTargetSessionClaimModel.canonical_digest
                            == claim.canonical_digest,
                            ConnectorTargetSessionClaimModel.state == "active",
                            ConnectorTargetSessionClaimModel.recovery_owner_attempt_id.is_(None),
                            ConnectorTargetSessionClaimModel.recovery_lease_expires_at.is_(None),
                            ConnectorTargetSessionClaimModel.expires_at > func.now(),
                        )
                    ),
                )
                if released.rowcount != 1:
                    await session.rollback()
                    return False
                session.add(self._model(record, payload=payload))
                await session.commit()
            return True
        except IntegrityError:
            return False
        except Exception:
            if await self._published_exact(claim, record):
                return True
            raise

    async def add(self, record: ConnectorTargetSessionVerificationRecord) -> bool:
        payload = self._storage_payload(record)
        verified_by_digest = ConnectorTargetSessionService._identifier_digest(record.verified_by)
        try:
            async with self._sessions() as session:
                await self._lock_coordinates(
                    session,
                    organization_id=record.organization_id,
                    environment_id=record.environment_id,
                    source_runtime_activation_id=record.source_runtime_activation_id,
                    verified_by_digest=verified_by_digest,
                    idempotency_digest=record.idempotency_digest,
                )
                pending = await session.scalar(
                    select(ConnectorTargetSessionClaimModel.verification_attempt_id).where(
                        ConnectorTargetSessionClaimModel.organization_id == record.organization_id,
                        ConnectorTargetSessionClaimModel.environment_id == record.environment_id,
                        or_(
                            ConnectorTargetSessionClaimModel.source_runtime_activation_id
                            == record.source_runtime_activation_id,
                            (
                                ConnectorTargetSessionClaimModel.verified_by_digest
                                == verified_by_digest
                            )
                            & (
                                ConnectorTargetSessionClaimModel.idempotency_digest
                                == record.idempotency_digest
                            ),
                        ),
                    )
                )
                if pending is not None:
                    await session.rollback()
                    return False
                session.add(self._model(record, payload=payload))
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def close(self) -> None:
        await self._engine.dispose()

    async def _claim_exists_exact(self, claim: ConnectorTargetSessionClaim) -> bool:
        async with self._sessions() as session:
            row = await session.get(
                ConnectorTargetSessionClaimModel,
                claim.verification_attempt_id,
            )
            return row is not None and row.canonical_digest == claim.canonical_digest

    async def _recovery_fence_exists_exact(
        self,
        claim: ConnectorTargetSessionClaim,
        recovery_attempt_id: str,
    ) -> bool:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorTargetSessionClaimModel.verification_attempt_id).where(
                    ConnectorTargetSessionClaimModel.verification_attempt_id
                    == claim.verification_attempt_id,
                    ConnectorTargetSessionClaimModel.canonical_digest == claim.canonical_digest,
                    ConnectorTargetSessionClaimModel.state == "recovering",
                    ConnectorTargetSessionClaimModel.recovery_owner_attempt_id
                    == recovery_attempt_id,
                    ConnectorTargetSessionClaimModel.recovery_lease_expires_at > func.now(),
                )
            )
            return row is not None

    async def _published_exact(
        self,
        claim: ConnectorTargetSessionClaim,
        record: ConnectorTargetSessionVerificationRecord,
    ) -> bool:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorTargetSessionVerificationModel).where(
                    ConnectorTargetSessionVerificationModel.verification_attempt_id
                    == claim.verification_attempt_id,
                    ConnectorTargetSessionVerificationModel.verification_id
                    == record.verification_id,
                    ConnectorTargetSessionVerificationModel.canonical_digest
                    == record.canonical_digest,
                )
            )
            return row is not None

    @staticmethod
    def _model(
        record: ConnectorTargetSessionVerificationRecord,
        *,
        payload: dict[str, Any],
    ) -> ConnectorTargetSessionVerificationModel:
        return ConnectorTargetSessionVerificationModel(
            verification_id=record.verification_id,
            verification_attempt_id=record.verification_attempt_id,
            source_runtime_activation_id=record.source_runtime_activation_id,
            instance_id=record.instance_id,
            session_profile_id=record.session_profile_id,
            verified_by=record.verified_by,
            verified_by_digest=ConnectorTargetSessionService._identifier_digest(record.verified_by),
            idempotency_digest=record.idempotency_digest,
            replay_digest=record.replay_digest,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            canonical_digest=record.canonical_digest,
            payload=payload,
        )

    @staticmethod
    def _to_domain(
        raw: ConnectorTargetSessionVerificationModel | dict[str, Any],
    ) -> ConnectorTargetSessionVerificationRecord:
        payload = dict(
            raw.payload if isinstance(raw, ConnectorTargetSessionVerificationModel) else raw
        )
        if isinstance(raw, ConnectorTargetSessionVerificationModel):
            payload["verification_attempt_id"] = raw.verification_attempt_id
            payload["replay_digest"] = raw.replay_digest
            payload["idempotency_digest"] = raw.idempotency_digest
        payload.setdefault("reused", False)
        payload["verified_at"] = datetime.fromisoformat(str(payload["verified_at"]))
        payload["connectivity_check_results"] = tuple(
            ConnectorTargetConnectivityCheckResult(**item)
            for item in payload["connectivity_check_results"]
        )
        return ConnectorTargetSessionVerificationRecord(**cast(Any, payload))

    @staticmethod
    def _claim_to_domain(row: ConnectorTargetSessionClaimModel) -> ConnectorTargetSessionClaim:
        return ConnectorTargetSessionClaim(
            verification_attempt_id=row.verification_attempt_id,
            verification_id=row.verification_id,
            source_runtime_activation_id=row.source_runtime_activation_id,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            verified_by_digest=row.verified_by_digest,
            idempotency_digest=row.idempotency_digest,
            replay_digest=row.replay_digest,
            claimed_at=row.claimed_at,
            expires_at=row.expires_at,
            canonical_digest=row.canonical_digest,
        )

    @staticmethod
    def _storage_payload(record: ConnectorTargetSessionVerificationRecord) -> dict[str, Any]:
        payload = asdict(record)
        for field in ("replay_digest", "idempotency_digest", "reused"):
            payload.pop(field)
        normalized = ConnectorTargetSessionService._normalize(payload)
        assert isinstance(normalized, dict)
        return cast(dict[str, Any], normalized)

    @staticmethod
    async def _lock_coordinates(
        session: AsyncSession,
        *,
        organization_id: str,
        environment_id: str,
        source_runtime_activation_id: str,
        verified_by_digest: str,
        idempotency_digest: str,
    ) -> None:
        coordination_keys = (
            "\x1f".join(
                (
                    "actor-idempotency",
                    organization_id,
                    environment_id,
                    verified_by_digest,
                    idempotency_digest,
                )
            ),
            "\x1f".join(
                (
                    "source",
                    organization_id,
                    environment_id,
                    source_runtime_activation_id,
                )
            ),
        )
        for coordination_key in sorted(coordination_keys):
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:coordination_key, 0))"),
                {"coordination_key": coordination_key},
            )

    async def _lock_claim_coordinates(
        self,
        session: AsyncSession,
        claim: ConnectorTargetSessionClaim,
    ) -> None:
        await self._lock_coordinates(
            session,
            organization_id=claim.organization_id,
            environment_id=claim.environment_id,
            source_runtime_activation_id=claim.source_runtime_activation_id,
            verified_by_digest=claim.verified_by_digest,
            idempotency_digest=claim.idempotency_digest,
        )
