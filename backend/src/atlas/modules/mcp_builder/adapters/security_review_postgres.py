from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import McpBuilderSecurityReviewModel
from atlas.modules.mcp_builder.domain.security_review import (
    BuilderSecurityControl,
    BuilderSecurityControlAssessment,
    BuilderSecurityControlDecisionKind,
    BuilderSecurityReviewState,
    McpBuilderSecurityReview,
)


class PostgreSQLMcpBuilderSecurityReviewRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLMcpBuilderSecurityReviewRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, review_id: str) -> McpBuilderSecurityReview | None:
        async with self._sessions() as session:
            row = await session.get(McpBuilderSecurityReviewModel, review_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_project(self, *, project_id: str) -> McpBuilderSecurityReview | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderSecurityReviewModel).where(
                    McpBuilderSecurityReviewModel.project_id == project_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_domain_review(
        self, *, domain_review_id: str
    ) -> McpBuilderSecurityReview | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderSecurityReviewModel).where(
                    McpBuilderSecurityReviewModel.domain_review_id == domain_review_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, reviewed_by: str, idempotency_key: str
    ) -> McpBuilderSecurityReview | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderSecurityReviewModel).where(
                    McpBuilderSecurityReviewModel.reviewed_by == reviewed_by,
                    McpBuilderSecurityReviewModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, review: McpBuilderSecurityReview) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    McpBuilderSecurityReviewModel(
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
                        domain_review_id=review.domain_review_id,
                        domain_review_digest=review.domain_review_digest,
                        domain_review_profile=review.domain_review_profile,
                        domain_reviewer_contract_version=(review.domain_reviewer_contract_version),
                        domain_reviewed_by=review.domain_reviewed_by,
                        organization_id=review.organization_id,
                        environment_id=review.environment_id,
                        reviewed_by=review.reviewed_by,
                        review_profile=review.review_profile,
                        reviewer_contract_version=review.reviewer_contract_version,
                        control_assessments=[
                            {
                                "control": item.control.value,
                                "decision": item.decision.value,
                                "assessment": item.assessment,
                                "evidence_references": list(item.evidence_references),
                                "finding_codes": list(item.finding_codes),
                                "required_controls": list(item.required_controls),
                            }
                            for item in review.control_assessments
                        ],
                        accepted_count=review.accepted_count,
                        needs_remediation_count=review.needs_remediation_count,
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
    def _to_domain(row: McpBuilderSecurityReviewModel) -> McpBuilderSecurityReview:
        return McpBuilderSecurityReview(
            review_id=row.review_id,
            schema_version=row.schema_version,
            version=row.version,
            state=BuilderSecurityReviewState(row.state),
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
            domain_review_id=row.domain_review_id,
            domain_review_digest=row.domain_review_digest,
            domain_review_profile=row.domain_review_profile,
            domain_reviewer_contract_version=row.domain_reviewer_contract_version,
            domain_reviewed_by=row.domain_reviewed_by,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            reviewed_by=row.reviewed_by,
            review_profile=row.review_profile,
            reviewer_contract_version=row.reviewer_contract_version,
            control_assessments=tuple(
                BuilderSecurityControlAssessment(
                    control=BuilderSecurityControl(item["control"]),
                    decision=BuilderSecurityControlDecisionKind(item["decision"]),
                    assessment=item["assessment"],
                    evidence_references=tuple(item["evidence_references"]),
                    finding_codes=tuple(item["finding_codes"]),
                    required_controls=tuple(item["required_controls"]),
                )
                for item in row.control_assessments
            ),
            accepted_count=row.accepted_count,
            needs_remediation_count=row.needs_remediation_count,
            rejected_count=row.rejected_count,
            summary=row.summary,
            limitations=tuple(row.limitations),
            canonical_digest=row.canonical_digest,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            completed_at=row.completed_at,
            security_review_accepted=row.state == BuilderSecurityReviewState.ACCEPTED.value,
        )
