from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.capabilities import CapabilityClass
from atlas.core.persistence.models import McpBuilderDesignCheckpointModel
from atlas.modules.mcp_builder.domain.design_review import (
    BuilderCapabilityDecision,
    BuilderCapabilityDecisionKind,
    BuilderEntityMapping,
    McpBuilderDesignCheckpoint,
)


class PostgreSQLMcpBuilderDesignCheckpointRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLMcpBuilderDesignCheckpointRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, checkpoint_id: str) -> McpBuilderDesignCheckpoint | None:
        async with self._sessions() as session:
            row = await session.get(McpBuilderDesignCheckpointModel, checkpoint_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_project(self, *, project_id: str) -> McpBuilderDesignCheckpoint | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderDesignCheckpointModel).where(
                    McpBuilderDesignCheckpointModel.project_id == project_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, reviewer_id: str, idempotency_key: str
    ) -> McpBuilderDesignCheckpoint | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderDesignCheckpointModel).where(
                    McpBuilderDesignCheckpointModel.reviewer_id == reviewer_id,
                    McpBuilderDesignCheckpointModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, checkpoint: McpBuilderDesignCheckpoint) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    McpBuilderDesignCheckpointModel(
                        checkpoint_id=checkpoint.checkpoint_id,
                        schema_version=checkpoint.schema_version,
                        version=checkpoint.version,
                        project_id=checkpoint.project_id,
                        project_version=checkpoint.project_version,
                        project_digest=checkpoint.project_digest,
                        source_digest=checkpoint.source_digest,
                        organization_id=checkpoint.organization_id,
                        environment_id=checkpoint.environment_id,
                        reviewer_id=checkpoint.reviewer_id,
                        connector_boundary=checkpoint.connector_boundary,
                        target_products=list(checkpoint.target_products),
                        network_destinations=list(checkpoint.network_destinations),
                        configuration_keys=list(checkpoint.configuration_keys),
                        secret_reference_ids=list(checkpoint.secret_reference_ids),
                        entity_mappings=[
                            {
                                "source_entity": item.source_entity,
                                "atlas_entity": item.atlas_entity,
                            }
                            for item in checkpoint.entity_mappings
                        ],
                        capability_decisions=[
                            {
                                "candidate_id": item.candidate_id,
                                "decision": item.decision.value,
                                "analyzed_class": item.analyzed_class.value,
                                "confirmed_class": item.confirmed_class.value,
                                "required_permission": item.required_permission,
                                "rationale": item.rationale,
                                "generation_eligible": item.generation_eligible,
                            }
                            for item in checkpoint.capability_decisions
                        ],
                        canonical_digest=checkpoint.canonical_digest,
                        request_fingerprint=checkpoint.request_fingerprint,
                        idempotency_key=checkpoint.idempotency_key,
                        created_at=checkpoint.created_at,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(row: McpBuilderDesignCheckpointModel) -> McpBuilderDesignCheckpoint:
        return McpBuilderDesignCheckpoint(
            checkpoint_id=row.checkpoint_id,
            schema_version=row.schema_version,
            version=row.version,
            project_id=row.project_id,
            project_version=row.project_version,
            project_digest=row.project_digest,
            source_digest=row.source_digest,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            reviewer_id=row.reviewer_id,
            connector_boundary=row.connector_boundary,
            target_products=tuple(row.target_products),
            network_destinations=tuple(row.network_destinations),
            configuration_keys=tuple(row.configuration_keys),
            secret_reference_ids=tuple(row.secret_reference_ids),
            entity_mappings=tuple(
                BuilderEntityMapping(
                    source_entity=item["source_entity"], atlas_entity=item["atlas_entity"]
                )
                for item in row.entity_mappings
            ),
            capability_decisions=tuple(
                BuilderCapabilityDecision(
                    candidate_id=item["candidate_id"],
                    decision=BuilderCapabilityDecisionKind(item["decision"]),
                    analyzed_class=CapabilityClass(item["analyzed_class"]),
                    confirmed_class=CapabilityClass(item["confirmed_class"]),
                    required_permission=item["required_permission"],
                    rationale=item["rationale"],
                    generation_eligible=item["generation_eligible"],
                )
                for item in row.capability_decisions
            ),
            canonical_digest=row.canonical_digest,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            created_at=row.created_at,
        )
