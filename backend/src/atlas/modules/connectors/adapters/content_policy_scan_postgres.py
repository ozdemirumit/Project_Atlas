from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageContentPolicyScanModel
from atlas.modules.connectors.domain.content_policy_scan import (
    ConnectorPackageContentPolicyScan,
    ContentPolicyCheck,
    ContentPolicyCheckState,
    ContentPolicyFinding,
    ContentPolicyFindingKind,
    ContentPolicyLifecycle,
    ContentPolicyOutcome,
    ContentPolicySeverity,
)


class PostgreSQLPackageContentPolicyScanRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageContentPolicyScanRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, scan_id: str) -> ConnectorPackageContentPolicyScan | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageContentPolicyScanModel, scan_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_inventory(
        self, *, source_inventory_id: str
    ) -> ConnectorPackageContentPolicyScan | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageContentPolicyScanModel).where(
                    ConnectorPackageContentPolicyScanModel.source_inventory_id
                    == source_inventory_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, scanned_by: str, idempotency_key: str
    ) -> ConnectorPackageContentPolicyScan | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageContentPolicyScanModel).where(
                    ConnectorPackageContentPolicyScanModel.scanned_by == scanned_by,
                    ConnectorPackageContentPolicyScanModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, scan: ConnectorPackageContentPolicyScan) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(ConnectorPackageContentPolicyScanModel(**self._values(scan)))
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _values(scan: ConnectorPackageContentPolicyScan) -> dict[str, object]:
        excluded = {"lifecycle", "outcome", "findings", "checks", "limitations"}
        scalar_fields = (
            column.name
            for column in ConnectorPackageContentPolicyScanModel.__table__.columns
            if column.name not in excluded
        )
        return {
            **{field: getattr(scan, field) for field in scalar_fields},
            "lifecycle": scan.lifecycle.value,
            "outcome": scan.outcome.value,
            "findings": [
                {
                    "rule_code": item.rule_code,
                    "kind": item.kind.value,
                    "severity": item.severity.value,
                    "relative_path": item.relative_path,
                    "line_number": item.line_number,
                    "evidence_fingerprint": item.evidence_fingerprint,
                    "summary": item.summary,
                    "remediation": item.remediation,
                }
                for item in scan.findings
            ],
            "checks": [
                {
                    "code": item.code,
                    "state": item.state.value,
                    "severity": item.severity.value,
                    "summary": item.summary,
                    "evidence_paths": list(item.evidence_paths),
                    "remediation": item.remediation,
                }
                for item in scan.checks
            ],
            "limitations": list(scan.limitations),
        }

    @staticmethod
    def _to_domain(
        row: ConnectorPackageContentPolicyScanModel,
    ) -> ConnectorPackageContentPolicyScan:
        excluded = {"lifecycle", "outcome", "findings", "checks", "limitations"}
        values = {
            column.name: getattr(row, column.name)
            for column in ConnectorPackageContentPolicyScanModel.__table__.columns
            if column.name not in excluded
        }
        return ConnectorPackageContentPolicyScan(
            **values,
            lifecycle=ContentPolicyLifecycle(row.lifecycle),
            outcome=ContentPolicyOutcome(row.outcome),
            findings=tuple(
                ContentPolicyFinding(
                    rule_code=item["rule_code"],
                    kind=ContentPolicyFindingKind(item["kind"]),
                    severity=ContentPolicySeverity(item["severity"]),
                    relative_path=item["relative_path"],
                    line_number=item["line_number"],
                    evidence_fingerprint=item["evidence_fingerprint"],
                    summary=item["summary"],
                    remediation=item["remediation"],
                )
                for item in row.findings
            ),
            checks=tuple(
                ContentPolicyCheck(
                    code=item["code"],
                    state=ContentPolicyCheckState(item["state"]),
                    severity=ContentPolicySeverity(item["severity"]),
                    summary=item["summary"],
                    evidence_paths=tuple(item["evidence_paths"]),
                    remediation=item["remediation"],
                )
                for item in row.checks
            ),
            limitations=tuple(row.limitations),
        )
