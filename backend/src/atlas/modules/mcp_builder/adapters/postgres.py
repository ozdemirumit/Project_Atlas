from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.core.persistence.models import McpBuilderProjectModel
from atlas.modules.mcp_builder.domain.models import (
    BuilderAuthenticationScheme,
    BuilderCapabilityCandidate,
    BuilderFinding,
    BuilderFindingSeverity,
    BuilderProjectState,
    McpBuilderProject,
)


class PostgreSQLMcpBuilderProjectRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLMcpBuilderProjectRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, owner_id: str, idempotency_key: str) -> McpBuilderProject | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderProjectModel).where(
                    McpBuilderProjectModel.owner_id == owner_id,
                    McpBuilderProjectModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_id(self, *, owner_id: str, project_id: str) -> McpBuilderProject | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderProjectModel).where(
                    McpBuilderProjectModel.owner_id == owner_id,
                    McpBuilderProjectModel.project_id == project_id,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, project: McpBuilderProject) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    McpBuilderProjectModel(
                        project_id=project.project_id,
                        schema_version=project.schema_version,
                        version=project.version,
                        state=project.state.value,
                        organization_id=project.organization_id,
                        environment_id=project.environment_id,
                        owner_id=project.owner_id,
                        vendor=project.vendor,
                        product=project.product,
                        intended_product_versions=list(project.intended_product_versions),
                        target_environment=project.target_environment,
                        sdk_profile=project.sdk_profile,
                        source_id=project.source_id,
                        source_authority=project.source_authority,
                        source_owner=project.source_owner,
                        documentation_version=project.documentation_version,
                        publication_date=project.publication_date,
                        license_id=project.license_id,
                        redistribution_allowed=project.redistribution_allowed,
                        classification=project.classification.value,
                        openapi_version=project.openapi_version,
                        api_title=project.api_title,
                        api_version=project.api_version,
                        source_digest=project.source_digest,
                        source_size_bytes=project.source_size_bytes,
                        canonical_source_json=project.canonical_source_json,
                        declared_servers=list(project.declared_servers),
                        authentication_schemes=[
                            {
                                "scheme_id": item.scheme_id,
                                "scheme_type": item.scheme_type,
                                "scheme": item.scheme,
                                "location": item.location,
                                "bearer_format": item.bearer_format,
                                "requires_secret_reference": item.requires_secret_reference,
                                "supported_for_unattended_use": item.supported_for_unattended_use,
                                "finding_codes": list(item.finding_codes),
                            }
                            for item in project.authentication_schemes
                        ],
                        capability_candidates=[
                            {
                                "candidate_id": item.candidate_id,
                                "operation_id": item.operation_id,
                                "method": item.method,
                                "path": item.path,
                                "summary": item.summary,
                                "citation": item.citation,
                                "proposed_capability_class": item.proposed_capability_class.value,
                                "side_effects": list(item.side_effects),
                                "security_scheme_ids": list(item.security_scheme_ids),
                                "parameter_count": item.parameter_count,
                                "response_codes": list(item.response_codes),
                                "request_body_present": item.request_body_present,
                                "confidence_basis": list(item.confidence_basis),
                                "clarification_codes": list(item.clarification_codes),
                                "generation_blocked": item.generation_blocked,
                            }
                            for item in project.capability_candidates
                        ],
                        findings=[
                            {
                                "code": item.code,
                                "severity": item.severity.value,
                                "location": item.location,
                                "message": item.message,
                                "blocking": item.blocking,
                            }
                            for item in project.findings
                        ],
                        canonical_digest=project.canonical_digest,
                        request_fingerprint=project.request_fingerprint,
                        idempotency_key=project.idempotency_key,
                        created_at=project.created_at,
                        analyzed_at=project.analyzed_at,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(row: McpBuilderProjectModel) -> McpBuilderProject:
        return McpBuilderProject(
            project_id=row.project_id,
            schema_version=row.schema_version,
            version=row.version,
            state=BuilderProjectState(row.state),
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            owner_id=row.owner_id,
            vendor=row.vendor,
            product=row.product,
            intended_product_versions=tuple(row.intended_product_versions),
            target_environment=row.target_environment,
            sdk_profile=row.sdk_profile,
            source_id=row.source_id,
            source_authority=row.source_authority,
            source_owner=row.source_owner,
            documentation_version=row.documentation_version,
            publication_date=row.publication_date,
            license_id=row.license_id,
            redistribution_allowed=row.redistribution_allowed,
            classification=DataClassification(row.classification),
            openapi_version=row.openapi_version,
            api_title=row.api_title,
            api_version=row.api_version,
            source_digest=row.source_digest,
            source_size_bytes=row.source_size_bytes,
            canonical_source_json=row.canonical_source_json,
            declared_servers=tuple(row.declared_servers),
            authentication_schemes=tuple(
                BuilderAuthenticationScheme(
                    scheme_id=item["scheme_id"],
                    scheme_type=item["scheme_type"],
                    scheme=item["scheme"],
                    location=item["location"],
                    bearer_format=item["bearer_format"],
                    requires_secret_reference=item["requires_secret_reference"],
                    supported_for_unattended_use=item["supported_for_unattended_use"],
                    finding_codes=tuple(item["finding_codes"]),
                )
                for item in row.authentication_schemes
            ),
            capability_candidates=tuple(
                BuilderCapabilityCandidate(
                    candidate_id=item["candidate_id"],
                    operation_id=item["operation_id"],
                    method=item["method"],
                    path=item["path"],
                    summary=item["summary"],
                    citation=item["citation"],
                    proposed_capability_class=CapabilityClass(item["proposed_capability_class"]),
                    side_effects=tuple(item["side_effects"]),
                    security_scheme_ids=tuple(item["security_scheme_ids"]),
                    parameter_count=item["parameter_count"],
                    response_codes=tuple(item["response_codes"]),
                    request_body_present=item["request_body_present"],
                    confidence_basis=tuple(item["confidence_basis"]),
                    clarification_codes=tuple(item["clarification_codes"]),
                    generation_blocked=item["generation_blocked"],
                )
                for item in row.capability_candidates
            ),
            findings=tuple(
                BuilderFinding(
                    code=item["code"],
                    severity=BuilderFindingSeverity(item["severity"]),
                    location=item["location"],
                    message=item["message"],
                    blocking=item["blocking"],
                )
                for item in row.findings
            ),
            canonical_digest=row.canonical_digest,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            created_at=row.created_at,
            analyzed_at=row.analyzed_at,
        )
