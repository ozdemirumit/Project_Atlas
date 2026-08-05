from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import McpBuilderCandidateHandoffModel
from atlas.modules.mcp_builder.domain.candidate_handoff import (
    CandidateCapabilityEvidence,
    CandidateHandoffState,
    CandidateSignatureState,
    McpBuilderCandidateHandoff,
)


class PostgreSQLMcpBuilderCandidateHandoffRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLMcpBuilderCandidateHandoffRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, handoff_id: str) -> McpBuilderCandidateHandoff | None:
        async with self._sessions() as session:
            row = await session.get(McpBuilderCandidateHandoffModel, handoff_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_project(self, *, project_id: str) -> McpBuilderCandidateHandoff | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderCandidateHandoffModel).where(
                    McpBuilderCandidateHandoffModel.project_id == project_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_lab_validation(
        self, *, lab_validation_id: str
    ) -> McpBuilderCandidateHandoff | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderCandidateHandoffModel).where(
                    McpBuilderCandidateHandoffModel.lab_validation_id == lab_validation_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, custodied_by: str, idempotency_key: str
    ) -> McpBuilderCandidateHandoff | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderCandidateHandoffModel).where(
                    McpBuilderCandidateHandoffModel.custodied_by == custodied_by,
                    McpBuilderCandidateHandoffModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, handoff: McpBuilderCandidateHandoff) -> bool:
        scalar_fields = (
            "handoff_id",
            "schema_version",
            "version",
            "project_id",
            "project_version",
            "project_digest",
            "source_digest",
            "checkpoint_id",
            "checkpoint_digest",
            "generation_id",
            "generation_digest",
            "artifact_digest",
            "validation_id",
            "validation_digest",
            "domain_review_id",
            "domain_review_digest",
            "domain_reviewed_by",
            "security_review_id",
            "security_review_digest",
            "security_reviewed_by",
            "lab_validation_id",
            "lab_validation_digest",
            "lab_operated_by",
            "organization_id",
            "environment_id",
            "custodied_by",
            "handoff_profile",
            "archive_contract_version",
            "package_filename",
            "package_digest",
            "package_size_bytes",
            "package_entry_count",
            "generated_file_count",
            "generated_size_bytes",
            "envelope_digest",
            "manual_change_count",
            "canonical_digest",
            "request_fingerprint",
            "idempotency_key",
            "created_at",
        )
        try:
            async with self._sessions.begin() as session:
                session.add(
                    McpBuilderCandidateHandoffModel(
                        **{field: getattr(handoff, field) for field in scalar_fields},
                        state=handoff.state.value,
                        signature_state=handoff.signature_state.value,
                        capabilities=[
                            {
                                "candidate_id": item.candidate_id,
                                "capability_class": item.capability_class,
                                "required_permission": item.required_permission,
                                "supported_product_versions": list(item.supported_product_versions),
                                "source_citations": list(item.source_citations),
                            }
                            for item in handoff.capabilities
                        ],
                        network_destinations=list(handoff.network_destinations),
                        limitations=list(handoff.limitations),
                        unsupported_behavior=list(handoff.unsupported_behavior),
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(row: McpBuilderCandidateHandoffModel) -> McpBuilderCandidateHandoff:
        excluded = {
            "state",
            "signature_state",
            "capabilities",
            "network_destinations",
            "limitations",
            "unsupported_behavior",
        }
        values = {
            column.name: getattr(row, column.name)
            for column in McpBuilderCandidateHandoffModel.__table__.columns
            if column.name not in excluded
        }
        return McpBuilderCandidateHandoff(
            **values,
            state=CandidateHandoffState(row.state),
            signature_state=CandidateSignatureState(row.signature_state),
            capabilities=tuple(
                CandidateCapabilityEvidence(
                    candidate_id=item["candidate_id"],
                    capability_class=item["capability_class"],
                    required_permission=item["required_permission"],
                    supported_product_versions=tuple(item["supported_product_versions"]),
                    source_citations=tuple(item["source_citations"]),
                )
                for item in row.capabilities
            ),
            network_destinations=tuple(row.network_destinations),
            limitations=tuple(row.limitations),
            unsupported_behavior=tuple(row.unsupported_behavior),
        )
