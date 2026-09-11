from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from atlas.api.schemas import ResponseMeta
from atlas.core.audit_ledger import AuditIntegrityFindingKind, AuditIntegrityReport


class AuditIntegrityFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    kind: AuditIntegrityFindingKind
    sequence: int
    detail: str


class AuditIntegrityReportData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    verified_at: datetime
    first_sequence: int
    last_sequence: int
    records_checked: int
    findings: list[AuditIntegrityFindingData]
    is_intact: bool

    @classmethod
    def from_domain(cls, report: AuditIntegrityReport) -> AuditIntegrityReportData:
        return cls.model_validate(report)


class AuditLedgerIntegrityVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: AuditIntegrityReportData
    meta: ResponseMeta
