from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import McpBuilderValidationModel
from atlas.modules.mcp_builder.domain.validation import (
    BuilderValidationCheck,
    BuilderValidationCheckState,
    BuilderValidationSeverity,
    BuilderValidationState,
    McpBuilderValidation,
)


class PostgreSQLMcpBuilderValidationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLMcpBuilderValidationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, validation_id: str) -> McpBuilderValidation | None:
        async with self._sessions() as session:
            row = await session.get(McpBuilderValidationModel, validation_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_project(self, *, project_id: str) -> McpBuilderValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderValidationModel).where(
                    McpBuilderValidationModel.project_id == project_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> McpBuilderValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderValidationModel).where(
                    McpBuilderValidationModel.validated_by == validated_by,
                    McpBuilderValidationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, validation: McpBuilderValidation) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    McpBuilderValidationModel(
                        validation_id=validation.validation_id,
                        schema_version=validation.schema_version,
                        version=validation.version,
                        state=validation.state.value,
                        project_id=validation.project_id,
                        project_version=validation.project_version,
                        project_digest=validation.project_digest,
                        source_digest=validation.source_digest,
                        checkpoint_id=validation.checkpoint_id,
                        checkpoint_digest=validation.checkpoint_digest,
                        generation_id=validation.generation_id,
                        generation_digest=validation.generation_digest,
                        artifact_digest=validation.artifact_digest,
                        organization_id=validation.organization_id,
                        environment_id=validation.environment_id,
                        validated_by=validation.validated_by,
                        language_profile=validation.language_profile,
                        template_version=validation.template_version,
                        validation_profile=validation.validation_profile,
                        validator_version=validation.validator_version,
                        checks=[
                            {
                                "code": item.code,
                                "state": item.state.value,
                                "severity": item.severity.value,
                                "summary": item.summary,
                                "evidence_paths": list(item.evidence_paths),
                                "remediation": item.remediation,
                            }
                            for item in validation.checks
                        ],
                        passed_count=validation.passed_count,
                        failed_count=validation.failed_count,
                        skipped_count=validation.skipped_count,
                        limitations=list(validation.limitations),
                        canonical_digest=validation.canonical_digest,
                        request_fingerprint=validation.request_fingerprint,
                        idempotency_key=validation.idempotency_key,
                        completed_at=validation.completed_at,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(row: McpBuilderValidationModel) -> McpBuilderValidation:
        return McpBuilderValidation(
            validation_id=row.validation_id,
            schema_version=row.schema_version,
            version=row.version,
            state=BuilderValidationState(row.state),
            project_id=row.project_id,
            project_version=row.project_version,
            project_digest=row.project_digest,
            source_digest=row.source_digest,
            checkpoint_id=row.checkpoint_id,
            checkpoint_digest=row.checkpoint_digest,
            generation_id=row.generation_id,
            generation_digest=row.generation_digest,
            artifact_digest=row.artifact_digest,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            validated_by=row.validated_by,
            language_profile=row.language_profile,
            template_version=row.template_version,
            validation_profile=row.validation_profile,
            validator_version=row.validator_version,
            checks=tuple(
                BuilderValidationCheck(
                    code=item["code"],
                    state=BuilderValidationCheckState(item["state"]),
                    severity=BuilderValidationSeverity(item["severity"]),
                    summary=item["summary"],
                    evidence_paths=tuple(item["evidence_paths"]),
                    remediation=item["remediation"],
                )
                for item in row.checks
            ),
            passed_count=row.passed_count,
            failed_count=row.failed_count,
            skipped_count=row.skipped_count,
            limitations=tuple(row.limitations),
            canonical_digest=row.canonical_digest,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            completed_at=row.completed_at,
            static_validation_passed=row.state == BuilderValidationState.PASSED.value,
        )
