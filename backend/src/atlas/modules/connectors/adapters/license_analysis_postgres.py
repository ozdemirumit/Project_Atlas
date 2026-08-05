from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageLicenseAnalysisModel
from atlas.modules.connectors.application.license_analysis import (
    PackageLicenseAnalysisService,
)
from atlas.modules.connectors.domain.license_analysis import (
    ConnectorPackageLicenseAnalysis,
    LicenseCheck,
    LicenseCheckSeverity,
    LicenseCheckState,
    LicenseDisposition,
    LicenseFinding,
    LicenseLifecycle,
    LicenseOutcome,
    LicensePolicySnapshotSummary,
    LicenseSeverity,
    LicenseSubjectScope,
    LicenseSubjectSummary,
)


class PostgreSQLPackageLicenseAnalysisRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageLicenseAnalysisRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, analysis_id: str) -> ConnectorPackageLicenseAnalysis | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageLicenseAnalysisModel, analysis_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_source_analysis(
        self, *, source_malware_analysis_id: str
    ) -> ConnectorPackageLicenseAnalysis | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageLicenseAnalysisModel).where(
                    ConnectorPackageLicenseAnalysisModel.source_malware_analysis_id
                    == source_malware_analysis_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, analyzed_by: str, idempotency_key: str
    ) -> ConnectorPackageLicenseAnalysis | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageLicenseAnalysisModel).where(
                    ConnectorPackageLicenseAnalysisModel.analyzed_by == analyzed_by,
                    ConnectorPackageLicenseAnalysisModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, analysis: ConnectorPackageLicenseAnalysis) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(ConnectorPackageLicenseAnalysisModel(**self._values(analysis)))
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _values(analysis: ConnectorPackageLicenseAnalysis) -> dict[str, object]:
        excluded = {
            "lifecycle",
            "outcome",
            "policy_snapshot",
            "subject_summary",
            "findings",
            "checks",
            "limitations",
        }
        scalar_fields = (
            column.name
            for column in ConnectorPackageLicenseAnalysisModel.__table__.columns
            if column.name not in excluded
        )
        return {
            **{field: getattr(analysis, field) for field in scalar_fields},
            "lifecycle": analysis.lifecycle.value,
            "outcome": analysis.outcome.value,
            "policy_snapshot": PackageLicenseAnalysisService._snapshot_summary_payload(
                analysis.policy_snapshot
            ),
            "subject_summary": PackageLicenseAnalysisService._subject_summary_payload(
                analysis.subject_summary
            ),
            "findings": PackageLicenseAnalysisService._finding_payload(analysis.findings),
            "checks": PackageLicenseAnalysisService._check_payload(analysis.checks),
            "limitations": list(analysis.limitations),
        }

    @staticmethod
    def _to_domain(
        row: ConnectorPackageLicenseAnalysisModel,
    ) -> ConnectorPackageLicenseAnalysis:
        excluded = {
            "lifecycle",
            "outcome",
            "policy_snapshot",
            "subject_summary",
            "findings",
            "checks",
            "limitations",
        }
        values = {
            column.name: getattr(row, column.name)
            for column in ConnectorPackageLicenseAnalysisModel.__table__.columns
            if column.name not in excluded
        }
        snapshot = dict(row.policy_snapshot)
        snapshot["issued_at"] = datetime.fromisoformat(snapshot["issued_at"])
        snapshot["expires_at"] = datetime.fromisoformat(snapshot["expires_at"])
        return ConnectorPackageLicenseAnalysis(
            **values,
            lifecycle=LicenseLifecycle(row.lifecycle),
            outcome=LicenseOutcome(row.outcome),
            policy_snapshot=LicensePolicySnapshotSummary(**snapshot),
            subject_summary=LicenseSubjectSummary(**row.subject_summary),
            findings=tuple(
                LicenseFinding(
                    rule_id=item["rule_id"],
                    category=item["category"],
                    severity=LicenseSeverity(item["severity"]),
                    subject_scope=LicenseSubjectScope(item["subject_scope"]),
                    subject_fingerprint=item["subject_fingerprint"],
                    disposition=LicenseDisposition(item["disposition"]),
                    obligations=tuple(item["obligations"]),
                    summary=item["summary"],
                    remediation=item["remediation"],
                )
                for item in row.findings
            ),
            checks=tuple(
                LicenseCheck(
                    code=item["code"],
                    state=LicenseCheckState(item["state"]),
                    severity=LicenseCheckSeverity(item["severity"]),
                    summary=item["summary"],
                    remediation=item["remediation"],
                )
                for item in row.checks
            ),
            limitations=tuple(row.limitations),
        )
