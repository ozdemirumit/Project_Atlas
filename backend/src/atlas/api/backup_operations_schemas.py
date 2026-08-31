from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from atlas.api.schemas import ResponseMeta
from atlas.modules.backup_operations.domain.models import BackupOverview


class EvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str
    source: str
    source_version: str
    observed_at: datetime
    freshness: str
    trust_basis: str


class BackupProtectedClientData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str
    client_name: str
    host_name: str
    os_type: str | None
    is_deleted: bool | None
    observed_at: datetime
    evidence_references: list[str]


class BackupStoragePolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    policy_name: str
    number_of_copies: int | None
    number_of_streams: int
    observed_at: datetime
    evidence_references: list[str]


class BackupFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    subject_id: str
    severity: str
    component: str
    summary: str
    observed_at: datetime
    evidence_references: list[str]
    status: str


class HypothesisData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    title: str
    state: str
    rationale: str
    confidence_basis: str
    evidence_references: list[str]
    contradicting_evidence: list[str]


class InvestigationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: str
    title: str
    state: str
    summary: str
    hypotheses: list[HypothesisData]
    unknowns: list[str]
    next_checks: list[str]
    evidence_references: list[str]
    updated_at: datetime


class ReportData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    title: str
    generated_at: datetime
    executive_summary: str
    confirmed_facts: list[str]
    provisional_findings: list[str]
    unknowns: list[str]
    evidence_references: list[str]
    safety_notice: str


class BackupOverviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    data_profile: str
    generated_at: datetime
    clients: list[BackupProtectedClientData]
    policies: list[BackupStoragePolicyData]
    findings: list[BackupFindingData]
    evidence: list[EvidenceData]
    investigation: InvestigationData
    report: ReportData

    @classmethod
    def from_domain(cls, overview: BackupOverview) -> BackupOverviewData:
        return cls.model_validate(overview, from_attributes=True)


class BackupOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: BackupOverviewData
    meta: ResponseMeta
