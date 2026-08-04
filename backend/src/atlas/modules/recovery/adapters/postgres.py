from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import LogicalBackupModel, RestoreValidationModel
from atlas.modules.recovery.domain.backup import (
    BackupRecord,
    BackupState,
    RestoreValidation,
    RestoreValidationState,
)


class PostgreSQLRecoveryRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLRecoveryRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_backup(self, *, actor_id: str, idempotency_key: str) -> BackupRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(LogicalBackupModel).where(
                    LogicalBackupModel.actor_id == actor_id,
                    LogicalBackupModel.idempotency_key == idempotency_key,
                )
            )
            return self._backup_to_domain(row) if row is not None else None

    async def get_backup_by_id(self, *, actor_id: str, backup_id: str) -> BackupRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(LogicalBackupModel).where(
                    LogicalBackupModel.actor_id == actor_id,
                    LogicalBackupModel.backup_id == backup_id,
                )
            )
            return self._backup_to_domain(row) if row is not None else None

    async def add_backup(self, record: BackupRecord) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    LogicalBackupModel(
                        backup_id=record.backup_id,
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
                        target_id=record.target_id,
                        archive_sha256=record.archive_sha256,
                        archive_size_bytes=record.archive_size_bytes,
                        archive_name=record.archive_name,
                        entry_count=record.entry_count,
                        created_at=record.created_at,
                        expires_at=record.expires_at,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def get_validation(
        self, *, actor_id: str, idempotency_key: str
    ) -> RestoreValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RestoreValidationModel).where(
                    RestoreValidationModel.actor_id == actor_id,
                    RestoreValidationModel.idempotency_key == idempotency_key,
                )
            )
            return self._validation_to_domain(row) if row is not None else None

    async def get_validation_by_id(
        self, *, actor_id: str, validation_id: str
    ) -> RestoreValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RestoreValidationModel).where(
                    RestoreValidationModel.actor_id == actor_id,
                    RestoreValidationModel.validation_id == validation_id,
                )
            )
            return self._validation_to_domain(row) if row is not None else None

    async def add_validation(self, record: RestoreValidation) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    RestoreValidationModel(
                        validation_id=record.validation_id,
                        state=record.state.value,
                        backup_id=record.backup_id,
                        actor_id=record.actor_id,
                        request_fingerprint=record.request_fingerprint,
                        idempotency_key=record.idempotency_key,
                        archive_sha256=record.archive_sha256,
                        validation_digest=record.validation_digest,
                        check_ids=list(record.check_ids),
                        entry_count=record.entry_count,
                        validated_at=record.validated_at,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _backup_to_domain(row: LogicalBackupModel) -> BackupRecord:
        return BackupRecord(
            backup_id=row.backup_id,
            state=BackupState(row.state),
            actor_id=row.actor_id,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            site_id=row.site_id,
            source_run_id=row.source_run_id,
            source_run_version=row.source_run_version,
            preview_digest=row.preview_digest,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            target_id=row.target_id,
            archive_sha256=row.archive_sha256,
            archive_size_bytes=row.archive_size_bytes,
            archive_name=row.archive_name,
            entry_count=row.entry_count,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )

    @staticmethod
    def _validation_to_domain(row: RestoreValidationModel) -> RestoreValidation:
        return RestoreValidation(
            validation_id=row.validation_id,
            state=RestoreValidationState(row.state),
            backup_id=row.backup_id,
            actor_id=row.actor_id,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            archive_sha256=row.archive_sha256,
            validation_digest=row.validation_digest,
            check_ids=tuple(row.check_ids),
            entry_count=row.entry_count,
            validated_at=row.validated_at,
        )
