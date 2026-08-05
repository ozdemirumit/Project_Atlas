from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageStaticDependencyAnalysisModel
from atlas.modules.connectors.domain.static_dependency_analysis import (
    ConnectorPackageStaticDependencyAnalysis,
    DependencyHygieneSummary,
    StaticDependencyCategory,
    StaticDependencyCheck,
    StaticDependencyCheckState,
    StaticDependencyFinding,
    StaticDependencyLifecycle,
    StaticDependencyOutcome,
    StaticDependencySeverity,
    StaticSourceSummary,
)


class PostgreSQLPackageStaticDependencyAnalysisRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageStaticDependencyAnalysisRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(
        self, *, analysis_id: str
    ) -> ConnectorPackageStaticDependencyAnalysis | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageStaticDependencyAnalysisModel, analysis_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_source_validation(
        self, *, source_authority_behavior_validation_id: str
    ) -> ConnectorPackageStaticDependencyAnalysis | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageStaticDependencyAnalysisModel).where(
                    ConnectorPackageStaticDependencyAnalysisModel.source_authority_behavior_validation_id
                    == source_authority_behavior_validation_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, analyzed_by: str, idempotency_key: str
    ) -> ConnectorPackageStaticDependencyAnalysis | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageStaticDependencyAnalysisModel).where(
                    ConnectorPackageStaticDependencyAnalysisModel.analyzed_by == analyzed_by,
                    ConnectorPackageStaticDependencyAnalysisModel.idempotency_key
                    == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, analysis: ConnectorPackageStaticDependencyAnalysis) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(ConnectorPackageStaticDependencyAnalysisModel(**self._values(analysis)))
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _values(analysis: ConnectorPackageStaticDependencyAnalysis) -> dict[str, object]:
        excluded = {
            "lifecycle",
            "outcome",
            "source_summary",
            "dependency_summary",
            "findings",
            "checks",
            "limitations",
        }
        scalar_fields = (
            column.name
            for column in ConnectorPackageStaticDependencyAnalysisModel.__table__.columns
            if column.name not in excluded
        )
        return {
            **{field: getattr(analysis, field) for field in scalar_fields},
            "lifecycle": analysis.lifecycle.value,
            "outcome": analysis.outcome.value,
            "source_summary": StaticDependencyPayload.source_summary(analysis.source_summary),
            "dependency_summary": StaticDependencyPayload.dependency_summary(
                analysis.dependency_summary
            ),
            "findings": StaticDependencyPayload.findings(analysis.findings),
            "checks": StaticDependencyPayload.checks(analysis.checks),
            "limitations": list(analysis.limitations),
        }

    @staticmethod
    def _to_domain(
        row: ConnectorPackageStaticDependencyAnalysisModel,
    ) -> ConnectorPackageStaticDependencyAnalysis:
        excluded = {
            "lifecycle",
            "outcome",
            "source_summary",
            "dependency_summary",
            "findings",
            "checks",
            "limitations",
        }
        values = {
            column.name: getattr(row, column.name)
            for column in ConnectorPackageStaticDependencyAnalysisModel.__table__.columns
            if column.name not in excluded
        }
        return ConnectorPackageStaticDependencyAnalysis(
            **values,
            lifecycle=StaticDependencyLifecycle(row.lifecycle),
            outcome=StaticDependencyOutcome(row.outcome),
            source_summary=StaticSourceSummary(**row.source_summary),
            dependency_summary=DependencyHygieneSummary(**row.dependency_summary),
            findings=tuple(
                StaticDependencyFinding(
                    rule_code=item["rule_code"],
                    category=StaticDependencyCategory(item["category"]),
                    severity=StaticDependencySeverity(item["severity"]),
                    relative_path=item["relative_path"],
                    line_number=item["line_number"],
                    evidence_fingerprint=item["evidence_fingerprint"],
                    summary=item["summary"],
                    remediation=item["remediation"],
                )
                for item in row.findings
            ),
            checks=tuple(
                StaticDependencyCheck(
                    code=item["code"],
                    state=StaticDependencyCheckState(item["state"]),
                    severity=StaticDependencySeverity(item["severity"]),
                    summary=item["summary"],
                    evidence_paths=tuple(item["evidence_paths"]),
                    remediation=item["remediation"],
                )
                for item in row.checks
            ),
            limitations=tuple(row.limitations),
        )


class StaticDependencyPayload:
    @staticmethod
    def source_summary(item: StaticSourceSummary) -> dict[str, object]:
        return {
            "source_file_count": item.source_file_count,
            "module_count": item.module_count,
            "function_count": item.function_count,
            "import_count": item.import_count,
            "external_import_count": item.external_import_count,
            "unresolved_import_count": item.unresolved_import_count,
            "source_set_digest": item.source_set_digest,
        }

    @staticmethod
    def dependency_summary(item: DependencyHygieneSummary) -> dict[str, object]:
        return {
            "runtime_dependency_count": item.runtime_dependency_count,
            "build_dependency_count": item.build_dependency_count,
            "imported_dependency_count": item.imported_dependency_count,
            "dependency_lock_present": item.dependency_lock_present,
            "dependency_lock_required": item.dependency_lock_required,
            "dependency_set_digest": item.dependency_set_digest,
            "metadata_consistent": item.metadata_consistent,
            "imports_reconciled": item.imports_reconciled,
            "deterministic_constraints": item.deterministic_constraints,
        }

    @staticmethod
    def findings(items: tuple[StaticDependencyFinding, ...]) -> list[dict[str, object]]:
        return [
            {
                "rule_code": item.rule_code,
                "category": item.category.value,
                "severity": item.severity.value,
                "relative_path": item.relative_path,
                "line_number": item.line_number,
                "evidence_fingerprint": item.evidence_fingerprint,
                "summary": item.summary,
                "remediation": item.remediation,
            }
            for item in items
        ]

    @staticmethod
    def checks(items: tuple[StaticDependencyCheck, ...]) -> list[dict[str, object]]:
        return [
            {
                "code": item.code,
                "state": item.state.value,
                "severity": item.severity.value,
                "summary": item.summary,
                "evidence_paths": list(item.evidence_paths),
                "remediation": item.remediation,
            }
            for item in items
        ]
