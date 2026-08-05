from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import McpBuilderGenerationModel
from atlas.modules.mcp_builder.domain.generation import (
    BuilderGeneratedFile,
    BuilderGenerationState,
    McpBuilderGeneration,
)


class PostgreSQLMcpBuilderGenerationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLMcpBuilderGenerationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, generation_id: str) -> McpBuilderGeneration | None:
        async with self._sessions() as session:
            row = await session.get(McpBuilderGenerationModel, generation_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_project(self, *, project_id: str) -> McpBuilderGeneration | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderGenerationModel).where(
                    McpBuilderGenerationModel.project_id == project_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> McpBuilderGeneration | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderGenerationModel).where(
                    McpBuilderGenerationModel.requested_by == requested_by,
                    McpBuilderGenerationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, generation: McpBuilderGeneration) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    McpBuilderGenerationModel(
                        generation_id=generation.generation_id,
                        schema_version=generation.schema_version,
                        version=generation.version,
                        state=generation.state.value,
                        project_id=generation.project_id,
                        project_version=generation.project_version,
                        project_digest=generation.project_digest,
                        source_digest=generation.source_digest,
                        checkpoint_id=generation.checkpoint_id,
                        checkpoint_digest=generation.checkpoint_digest,
                        organization_id=generation.organization_id,
                        environment_id=generation.environment_id,
                        requested_by=generation.requested_by,
                        language_profile=generation.language_profile,
                        template_version=generation.template_version,
                        artifact_digest=generation.artifact_digest,
                        artifact_size_bytes=generation.artifact_size_bytes,
                        files=[
                            {
                                "relative_path": item.relative_path,
                                "media_type": item.media_type,
                                "sha256": item.sha256,
                                "size_bytes": item.size_bytes,
                                "source_candidate_ids": list(item.source_candidate_ids),
                            }
                            for item in generation.files
                        ],
                        canonical_digest=generation.canonical_digest,
                        request_fingerprint=generation.request_fingerprint,
                        idempotency_key=generation.idempotency_key,
                        created_at=generation.created_at,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(row: McpBuilderGenerationModel) -> McpBuilderGeneration:
        return McpBuilderGeneration(
            generation_id=row.generation_id,
            schema_version=row.schema_version,
            version=row.version,
            state=BuilderGenerationState(row.state),
            project_id=row.project_id,
            project_version=row.project_version,
            project_digest=row.project_digest,
            source_digest=row.source_digest,
            checkpoint_id=row.checkpoint_id,
            checkpoint_digest=row.checkpoint_digest,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            requested_by=row.requested_by,
            language_profile=row.language_profile,
            template_version=row.template_version,
            artifact_digest=row.artifact_digest,
            artifact_size_bytes=row.artifact_size_bytes,
            files=tuple(
                BuilderGeneratedFile(
                    relative_path=item["relative_path"],
                    media_type=item["media_type"],
                    sha256=item["sha256"],
                    size_bytes=item["size_bytes"],
                    source_candidate_ids=tuple(item["source_candidate_ids"]),
                )
                for item in row.files
            ),
            canonical_digest=row.canonical_digest,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            created_at=row.created_at,
        )
