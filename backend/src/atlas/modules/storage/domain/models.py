from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class FreshnessState(StrEnum):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


class StorageHealthState(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class FindingSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class InvestigationState(StrEnum):
    PROVISIONAL = "provisional"
    INCONCLUSIVE = "inconclusive"
    REVIEWED = "reviewed"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    reference: str
    source: str
    source_version: str
    observed_at: datetime
    freshness: FreshnessState
    trust_basis: str

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.reference or not self.source or not self.trust_basis:
            raise ValueError("evidence identity and trust basis are required")


@dataclass(frozen=True, slots=True)
class StorageAsset:
    asset_id: str
    storage_device_id: str
    vendor: str
    model: str
    # Hitachi's serial numbers are numeric; Huawei's system identifiers are alphanumeric
    # (e.g. "2102350ABC") -- widened to accept either rather than coercing one vendor's real
    # identity format into the other's shape.
    serial_number: int | str
    health: StorageHealthState
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("storage assets require evidence")


@dataclass(frozen=True, slots=True)
class HealthFinding:
    finding_id: str
    asset_id: str
    severity: FindingSeverity
    component: str
    summary: str
    observed_at: datetime
    evidence_references: tuple[str, ...]
    status: str = "open"

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.summary.strip() or not self.evidence_references:
            raise ValueError("health findings require a summary and evidence")


@dataclass(frozen=True, slots=True)
class InvestigationHypothesis:
    hypothesis_id: str
    title: str
    state: str
    rationale: str
    confidence_basis: str
    evidence_references: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StorageInvestigation:
    investigation_id: str
    title: str
    state: InvestigationState
    summary: str
    hypotheses: tuple[InvestigationHypothesis, ...]
    unknowns: tuple[str, ...]
    next_checks: tuple[str, ...]
    evidence_references: tuple[str, ...]
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        if self.state is InvestigationState.PROVISIONAL and not self.unknowns:
            raise ValueError("provisional investigations must declare unknowns")


@dataclass(frozen=True, slots=True)
class StorageReport:
    report_id: str
    title: str
    generated_at: datetime
    executive_summary: str
    confirmed_facts: tuple[str, ...]
    provisional_findings: tuple[str, ...]
    unknowns: tuple[str, ...]
    evidence_references: tuple[str, ...]
    safety_notice: str

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("reports require evidence")


@dataclass(frozen=True, slots=True)
class StorageOverview:
    snapshot_id: str
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    data_profile: str
    generated_at: datetime
    assets: tuple[StorageAsset, ...]
    findings: tuple[HealthFinding, ...]
    evidence: tuple[EvidenceRecord, ...]
    investigation: StorageInvestigation
    report: StorageReport

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        evidence_ids = {item.reference for item in self.evidence}
        referenced = {
            reference
            for references in (
                *(asset.evidence_references for asset in self.assets),
                *(finding.evidence_references for finding in self.findings),
                self.investigation.evidence_references,
                self.report.evidence_references,
            )
            for reference in references
        }
        if not referenced <= evidence_ids:
            raise ValueError("overview contains unresolved evidence references")
