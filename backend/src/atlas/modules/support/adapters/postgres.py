from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import SupportBundleExportModel
from atlas.modules.support.domain.support_bundle import (
    SupportBundleExport,
    SupportExportState,
)


class PostgreSQLSupportBundleExportRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLSupportBundleExportRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, actor_id: str, idempotency_key: str) -> SupportBundleExport | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(SupportBundleExportModel).where(
                    SupportBundleExportModel.actor_id == actor_id,
                    SupportBundleExportModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, record: SupportBundleExport) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    SupportBundleExportModel(
                        export_id=record.export_id,
                        state=record.state.value,
                        actor_id=record.actor_id,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        site_id=record.site_id,
                        source_run_id=record.source_run_id,
                        source_run_version=record.source_run_version,
                        preview_digest=record.preview_digest,
                        request_fingerprint=record.request_fingerprint,
                        idempotency_key=record.idempotency_key,
                        archive_sha256=record.archive_sha256,
                        archive_size_bytes=record.archive_size_bytes,
                        archive_name=record.archive_name,
                        included_count=record.included_count,
                        excluded_count=record.excluded_count,
                        expires_at=record.expires_at,
                        created_at=record.created_at,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(row: SupportBundleExportModel) -> SupportBundleExport:
        return SupportBundleExport(
            export_id=row.export_id,
            state=SupportExportState(row.state),
            actor_id=row.actor_id,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            site_id=row.site_id,
            source_run_id=row.source_run_id,
            source_run_version=row.source_run_version,
            preview_digest=row.preview_digest,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            archive_sha256=row.archive_sha256,
            archive_size_bytes=row.archive_size_bytes,
            archive_name=row.archive_name,
            included_count=row.included_count,
            excluded_count=row.excluded_count,
            created_at=row.created_at,
            expires_at=row.expires_at,
            reused=False,
        )
