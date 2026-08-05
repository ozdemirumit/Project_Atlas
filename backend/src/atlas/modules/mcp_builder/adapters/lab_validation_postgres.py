from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import McpBuilderLabValidationModel
from atlas.modules.mcp_builder.domain.lab_validation import (
    BuilderLabCheck,
    BuilderLabCheckCode,
    BuilderLabCheckSeverity,
    BuilderLabCheckState,
    BuilderLabValidationState,
    McpBuilderLabValidation,
)


class PostgreSQLMcpBuilderLabValidationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLMcpBuilderLabValidationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, lab_validation_id: str) -> McpBuilderLabValidation | None:
        async with self._sessions() as session:
            row = await session.get(McpBuilderLabValidationModel, lab_validation_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_project(self, *, project_id: str) -> McpBuilderLabValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderLabValidationModel).where(
                    McpBuilderLabValidationModel.project_id == project_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_security_review(
        self, *, security_review_id: str
    ) -> McpBuilderLabValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderLabValidationModel).where(
                    McpBuilderLabValidationModel.security_review_id == security_review_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, operated_by: str, idempotency_key: str
    ) -> McpBuilderLabValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(McpBuilderLabValidationModel).where(
                    McpBuilderLabValidationModel.operated_by == operated_by,
                    McpBuilderLabValidationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, validation: McpBuilderLabValidation) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    McpBuilderLabValidationModel(
                        **{
                            field: getattr(validation, field)
                            for field in (
                                "lab_validation_id",
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
                                "organization_id",
                                "environment_id",
                                "operated_by",
                                "lab_profile",
                                "runner_contract_version",
                                "runtime_version",
                                "passed_count",
                                "failed_count",
                                "skipped_count",
                                "child_started",
                                "child_exit_code",
                                "duration_ms",
                                "output_digest",
                                "output_size_bytes",
                                "artifact_file_count",
                                "artifact_size_bytes",
                                "workspace_removed",
                                "canonical_digest",
                                "request_fingerprint",
                                "idempotency_key",
                                "completed_at",
                            )
                        },
                        state=validation.state.value,
                        checks=[
                            {
                                "code": item.code.value,
                                "state": item.state.value,
                                "severity": item.severity.value,
                                "summary": item.summary,
                                "evidence_paths": list(item.evidence_paths),
                                "remediation": item.remediation,
                            }
                            for item in validation.checks
                        ],
                        limitations=list(validation.limitations),
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(row: McpBuilderLabValidationModel) -> McpBuilderLabValidation:
        return McpBuilderLabValidation(
            **{
                field: getattr(row, field)
                for field in (
                    "lab_validation_id",
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
                    "organization_id",
                    "environment_id",
                    "operated_by",
                    "lab_profile",
                    "runner_contract_version",
                    "runtime_version",
                    "passed_count",
                    "failed_count",
                    "skipped_count",
                    "child_started",
                    "child_exit_code",
                    "duration_ms",
                    "output_digest",
                    "output_size_bytes",
                    "artifact_file_count",
                    "artifact_size_bytes",
                    "workspace_removed",
                    "canonical_digest",
                    "request_fingerprint",
                    "idempotency_key",
                    "completed_at",
                )
            },
            state=BuilderLabValidationState(row.state),
            checks=tuple(
                BuilderLabCheck(
                    code=BuilderLabCheckCode(item["code"]),
                    state=BuilderLabCheckState(item["state"]),
                    severity=BuilderLabCheckSeverity(item["severity"]),
                    summary=item["summary"],
                    evidence_paths=tuple(item["evidence_paths"]),
                    remediation=item["remediation"],
                )
                for item in row.checks
            ),
            limitations=tuple(row.limitations),
            lab_validation_passed=row.state == BuilderLabValidationState.PASSED.value,
            runtime_self_test_performed=row.child_started,
            subprocess_invoked=row.child_started,
            dynamic_code_execution_performed=row.child_started,
        )
