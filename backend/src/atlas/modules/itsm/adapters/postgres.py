from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.classification import DataClassification
from atlas.core.persistence.models import ItsmIntegrationProfileModel
from atlas.modules.itsm.application.service import ItsmIntegrationService
from atlas.modules.itsm.domain.models import (
    ItsmAllowedOperation,
    ItsmCheckState,
    ItsmFieldMapping,
    ItsmIntegrationProfile,
    ItsmProfileLifecycle,
    ItsmProviderFamily,
    ItsmReadinessAssessment,
    ItsmReadinessCheck,
    ItsmReadinessState,
    ItsmWriteSemantics,
)


class PostgreSQLItsmIntegrationProfileRepository:
    durable = True

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLItsmIntegrationProfileRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    async def get(self, *, profile_id: str) -> ItsmIntegrationProfile | None:
        async with self._sessions() as session:
            row = await session.get(ItsmIntegrationProfileModel, profile_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_scope_key(
        self, *, organization_id: str, environment_id: str, profile_key: str
    ) -> ItsmIntegrationProfile | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ItsmIntegrationProfileModel).where(
                    ItsmIntegrationProfileModel.organization_id == organization_id,
                    ItsmIntegrationProfileModel.environment_id == environment_id,
                    ItsmIntegrationProfileModel.profile_key == profile_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> ItsmIntegrationProfile | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ItsmIntegrationProfileModel).where(
                    ItsmIntegrationProfileModel.created_by == created_by,
                    ItsmIntegrationProfileModel.create_idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_retirement_key(
        self, *, retired_by: str, idempotency_key: str
    ) -> ItsmIntegrationProfile | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ItsmIntegrationProfileModel).where(
                    ItsmIntegrationProfileModel.retired_by == retired_by,
                    ItsmIntegrationProfileModel.retirement_idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        lifecycle: ItsmProfileLifecycle | None,
        limit: int,
    ) -> tuple[ItsmIntegrationProfile, ...]:
        statement = select(ItsmIntegrationProfileModel).where(
            ItsmIntegrationProfileModel.organization_id == organization_id,
            ItsmIntegrationProfileModel.environment_id == environment_id,
        )
        if lifecycle is not None:
            statement = statement.where(ItsmIntegrationProfileModel.lifecycle == lifecycle.value)
        statement = statement.order_by(
            ItsmIntegrationProfileModel.updated_at.desc(),
            ItsmIntegrationProfileModel.profile_id.desc(),
        ).limit(limit)
        async with self._sessions() as session:
            rows = (await session.scalars(statement)).all()
            return tuple(self._to_domain(row.payload) for row in rows)

    async def add(self, profile: ItsmIntegrationProfile) -> bool:
        payload = ItsmIntegrationService._normalize(asdict(profile))
        assert isinstance(payload, dict)
        async with self._sessions() as session:
            try:
                session.add(self._model(profile, cast(dict[str, Any], payload)))
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return False
        return True

    async def update(self, profile: ItsmIntegrationProfile, *, expected_version: int) -> bool:
        payload = ItsmIntegrationService._normalize(asdict(profile))
        assert isinstance(payload, dict)
        async with self._sessions() as session:
            try:
                result = cast(
                    CursorResult[Any],
                    await session.execute(
                        update(ItsmIntegrationProfileModel)
                        .where(
                            ItsmIntegrationProfileModel.profile_id == profile.profile_id,
                            ItsmIntegrationProfileModel.version == expected_version,
                        )
                        .values(**self._columns(profile, cast(dict[str, Any], payload)))
                    ),
                )
                if result.rowcount != 1:
                    await session.rollback()
                    return False
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _columns(profile: ItsmIntegrationProfile, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": profile.version,
            "lifecycle": profile.lifecycle.value,
            "readiness_state": profile.readiness.state.value,
            "updated_at": profile.updated_at,
            "retired_by": profile.retired_by,
            "retirement_idempotency_key": profile.retirement_idempotency_key,
            "canonical_digest": profile.canonical_digest,
            "payload": payload,
        }

    @classmethod
    def _model(
        cls, profile: ItsmIntegrationProfile, payload: dict[str, Any]
    ) -> ItsmIntegrationProfileModel:
        return ItsmIntegrationProfileModel(
            profile_id=profile.profile_id,
            profile_key=profile.profile_key,
            version=profile.version,
            display_name=profile.display_name,
            provider_family=profile.provider_family.value,
            lifecycle=profile.lifecycle.value,
            readiness_state=profile.readiness.state.value,
            created_by=profile.created_by,
            create_idempotency_key=profile.create_idempotency_key,
            updated_at=profile.updated_at,
            retired_by=profile.retired_by,
            retirement_idempotency_key=profile.retirement_idempotency_key,
            organization_id=profile.organization_id,
            environment_id=profile.environment_id,
            site_id=profile.site_id,
            canonical_digest=profile.canonical_digest,
            payload=payload,
        )

    @staticmethod
    def _to_domain(raw: dict[str, Any]) -> ItsmIntegrationProfile:
        payload = dict(raw)
        for field in ("created_at", "updated_at", "retired_at"):
            if payload.get(field) is not None:
                payload[field] = datetime.fromisoformat(str(payload[field]))
        payload["provider_family"] = ItsmProviderFamily(str(payload["provider_family"]))
        payload["classification_ceiling"] = DataClassification(
            str(payload["classification_ceiling"])
        )
        payload["allowed_operations"] = tuple(
            ItsmAllowedOperation(str(item)) for item in payload["allowed_operations"]
        )
        payload["field_mappings"] = tuple(
            ItsmFieldMapping(
                source_field=str(item["source_field"]),
                provider_field=str(item["provider_field"]),
                write_semantics=ItsmWriteSemantics(str(item["write_semantics"])),
            )
            for item in payload["field_mappings"]
        )
        readiness = dict(payload["readiness"])
        readiness["state"] = ItsmReadinessState(str(readiness["state"]))
        readiness["assessed_at"] = datetime.fromisoformat(str(readiness["assessed_at"]))
        readiness["checks"] = tuple(
            ItsmReadinessCheck(
                check_id=str(item["check_id"]),
                state=ItsmCheckState(str(item["state"])),
                reason_code=str(item["reason_code"]),
            )
            for item in readiness["checks"]
        )
        payload["readiness"] = ItsmReadinessAssessment(**cast(Any, readiness))
        payload["lifecycle"] = ItsmProfileLifecycle(str(payload["lifecycle"]))
        return ItsmIntegrationProfile(**cast(Any, payload))
