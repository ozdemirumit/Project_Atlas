from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.capabilities import CapabilityClass
from atlas.core.persistence.models import McpBuilderDomainReviewModel
from atlas.modules.mcp_builder.domain.domain_review import (
    BuilderDomainCapabilityDecision,
    BuilderDomainCapabilityDecisionKind,
    BuilderDomainReviewState,
    McpBuilderDomainReview,
)


class PostgreSQLMcpBuilderDomainReviewRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLMcpBuilderDomainReviewRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, review_id: str) -> McpBuilderDomainReview | None:
        async with self._sessions() as session:
            row = await session.get(McpBuilderDomainReviewModel, review_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_project(self, *, project_id: str) -> McpBuilderDomainReview | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderDomainReviewModel).where(
                    McpBuilderDomainReviewModel.project_id == project_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_validation(self, *, validation_id: str) -> McpBuilderDomainReview | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderDomainReviewModel).where(
                    McpBuilderDomainReviewModel.validation_id == validation_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, reviewed_by: str, idempotency_key: str
    ) -> McpBuilderDomainReview | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderDomainReviewModel).where(
                    McpBuilderDomainReviewModel.reviewed_by == reviewed_by,
                    McpBuilderDomainReviewModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, review: McpBuilderDomainReview) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    McpBuilderDomainReviewModel(
                        review_id=review.review_id,
                        schema_version=review.schema_version,
                        version=review.version,
                        state=review.state.value,
                        project_id=review.project_id,
                        project_version=review.project_version,
                        project_digest=review.project_digest,
                        source_digest=review.source_digest,
                        checkpoint_id=review.checkpoint_id,
                        checkpoint_digest=review.checkpoint_digest,
                        generation_id=review.generation_id,
                        generation_digest=review.generation_digest,
                        artifact_digest=review.artifact_digest,
                        validation_id=review.validation_id,
                        validation_digest=review.validation_digest,
                        validation_profile=review.validation_profile,
                        validator_version=review.validator_version,
                        organization_id=review.organization_id,
                        environment_id=review.environment_id,
                        reviewed_by=review.reviewed_by,
                        review_profile=review.review_profile,
                        reviewer_contract_version=review.reviewer_contract_version,
                        capability_decisions=[
                            {
                                "candidate_id": item.candidate_id,
                                "confirmed_class": item.confirmed_class.value,
                                "decision": item.decision.value,
                                "supported_product_versions": list(item.supported_product_versions),
                                "vendor_permission": item.vendor_permission,
                                "authentication_assessment": item.authentication_assessment,
                                "side_effect_assessment": item.side_effect_assessment,
                                "error_behavior_assessment": item.error_behavior_assessment,
                                "health_guidance_assessment": item.health_guidance_assessment,
                                "evidence_citations": list(item.evidence_citations),
                                "missing_case_codes": list(item.missing_case_codes),
                                "rationale": item.rationale,
                            }
                            for item in review.capability_decisions
                        ],
                        accepted_count=review.accepted_count,
                        needs_evidence_count=review.needs_evidence_count,
                        rejected_count=review.rejected_count,
                        summary=review.summary,
                        limitations=list(review.limitations),
                        canonical_digest=review.canonical_digest,
                        request_fingerprint=review.request_fingerprint,
                        idempotency_key=review.idempotency_key,
                        completed_at=review.completed_at,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(row: McpBuilderDomainReviewModel) -> McpBuilderDomainReview:
        return McpBuilderDomainReview(
            review_id=row.review_id,
            schema_version=row.schema_version,
            version=row.version,
            state=BuilderDomainReviewState(row.state),
            project_id=row.project_id,
            project_version=row.project_version,
            project_digest=row.project_digest,
            source_digest=row.source_digest,
            checkpoint_id=row.checkpoint_id,
            checkpoint_digest=row.checkpoint_digest,
            generation_id=row.generation_id,
            generation_digest=row.generation_digest,
            artifact_digest=row.artifact_digest,
            validation_id=row.validation_id,
            validation_digest=row.validation_digest,
            validation_profile=row.validation_profile,
            validator_version=row.validator_version,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            reviewed_by=row.reviewed_by,
            review_profile=row.review_profile,
            reviewer_contract_version=row.reviewer_contract_version,
            capability_decisions=tuple(
                BuilderDomainCapabilityDecision(
                    candidate_id=item["candidate_id"],
                    confirmed_class=CapabilityClass(item["confirmed_class"]),
                    decision=BuilderDomainCapabilityDecisionKind(item["decision"]),
                    supported_product_versions=tuple(item["supported_product_versions"]),
                    vendor_permission=item["vendor_permission"],
                    authentication_assessment=item["authentication_assessment"],
                    side_effect_assessment=item["side_effect_assessment"],
                    error_behavior_assessment=item["error_behavior_assessment"],
                    health_guidance_assessment=item["health_guidance_assessment"],
                    evidence_citations=tuple(item["evidence_citations"]),
                    missing_case_codes=tuple(item["missing_case_codes"]),
                    rationale=item["rationale"],
                )
                for item in row.capability_decisions
            ),
            accepted_count=row.accepted_count,
            needs_evidence_count=row.needs_evidence_count,
            rejected_count=row.rejected_count,
            summary=row.summary,
            limitations=tuple(row.limitations),
            canonical_digest=row.canonical_digest,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            completed_at=row.completed_at,
            domain_review_accepted=row.state == BuilderDomainReviewState.ACCEPTED.value,
        )
