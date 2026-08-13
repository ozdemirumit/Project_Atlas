from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.classification import DataClassification
from atlas.core.persistence.models import TechnicalReportModel
from atlas.modules.reports.domain.models import (
    HandoffState,
    ItsmFieldMapping,
    ItsmHandoffDraft,
    RedactionState,
    ReportAudience,
    ReportReview,
    ReportSection,
    ReportSourceLineage,
    ReportState,
    ReportType,
    ReviewStatus,
    SectionState,
    TechnicalReport,
)


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_normalize(item) for item in value]
    return value


class PostgreSQLTechnicalReportRepository:
    durable = True

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLTechnicalReportRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, report_id: str) -> TechnicalReport | None:
        async with self._sessions() as session:
            row = await session.get(TechnicalReportModel, report_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_request_fingerprint(
        self, *, request_fingerprint: str
    ) -> TechnicalReport | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(TechnicalReportModel).where(
                    TechnicalReportModel.request_fingerprint == request_fingerprint
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_latest(self, *, lineage_fingerprint: str) -> TechnicalReport | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(TechnicalReportModel)
                .where(TechnicalReportModel.lineage_fingerprint == lineage_fingerprint)
                .order_by(TechnicalReportModel.version.desc())
                .limit(1)
            )
            return self._to_domain(row.payload) if row else None

    async def add(
        self,
        report: TechnicalReport,
        *,
        request_fingerprint: str,
        lineage_fingerprint: str,
    ) -> bool:
        payload = _normalize(asdict(report))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    TechnicalReportModel(
                        report_id=report.report_id,
                        request_fingerprint=request_fingerprint,
                        lineage_fingerprint=lineage_fingerprint,
                        version=report.version,
                        prior_version_id=report.prior_version_id,
                        organization_id=report.organization_id,
                        environment_id=report.environment_id,
                        site_id=report.site_id,
                        target_id=report.target_id,
                        requested_by=report.requested_by,
                        expires_at=report.expires_at,
                        content_digest=report.content_digest,
                        payload=cast(dict[str, Any], payload),
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(raw: dict[str, Any]) -> TechnicalReport:
        payload = dict(raw)
        payload["state"] = ReportState(payload["state"])
        payload["report_type"] = ReportType(payload["report_type"])
        payload["audience"] = ReportAudience(payload["audience"])
        payload["classification"] = DataClassification(payload["classification"])
        payload["redaction_state"] = RedactionState(payload["redaction_state"])
        payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        payload["expires_at"] = datetime.fromisoformat(payload["expires_at"])

        source = dict(payload["source"])
        source["recommendation_created_at"] = datetime.fromisoformat(
            source["recommendation_created_at"]
        )
        source["recommendation_expires_at"] = datetime.fromisoformat(
            source["recommendation_expires_at"]
        )
        source["evidence_ids"] = tuple(source["evidence_ids"])
        source["component_versions"] = tuple(source["component_versions"])
        payload["source"] = ReportSourceLineage(**source)

        sections = []
        for raw_section in payload["sections"]:
            section = dict(raw_section)
            section["state"] = SectionState(section["state"])
            section["statements"] = tuple(section["statements"])
            section["evidence_references"] = tuple(section["evidence_references"])
            section["limitations"] = tuple(section["limitations"])
            sections.append(ReportSection(**section))
        payload["sections"] = tuple(sections)

        review = dict(payload["review"])
        review["status"] = ReviewStatus(review["status"])
        if review["reviewed_at"] is not None:
            review["reviewed_at"] = datetime.fromisoformat(review["reviewed_at"])
        payload["review"] = ReportReview(**review)

        raw_handoff = payload["itsm_handoff"]
        if raw_handoff is not None:
            handoff = dict(raw_handoff)
            handoff["state"] = HandoffState(handoff["state"])
            handoff["classification"] = DataClassification(handoff["classification"])
            handoff["redaction_state"] = RedactionState(handoff["redaction_state"])
            handoff["field_mappings"] = tuple(
                ItsmFieldMapping(**mapping) for mapping in handoff["field_mappings"]
            )
            handoff["artifact_references"] = tuple(handoff["artifact_references"])
            payload["itsm_handoff"] = ItsmHandoffDraft(**handoff)

        payload["component_versions"] = tuple(payload["component_versions"])
        return TechnicalReport(**cast(Any, payload))
