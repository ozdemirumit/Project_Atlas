from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class FreshnessState(StrEnum):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"
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
class BackupProtectedClient:
    """One Commvault-protected client, read from the real `GET webservice/Client` inventory.
    Represents registration in Commvault's protection scope -- not backup job outcome, which is
    a separate, already-implemented health_checks signal (see
    health_checks/adapters/commvault.py). `os_type` and `is_deleted` are optional: the official
    REST API reference does not confirm either field on this list endpoint's response (only on
    the single-client `GET Client/{clientId}` endpoint), so a real server may omit them."""

    client_id: str
    client_name: str
    host_name: str
    os_type: str | None
    is_deleted: bool | None
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.client_id.strip() or not self.client_name.strip():
            raise ValueError("protected clients require an identifier and name")
        if not self.evidence_references:
            raise ValueError("protected clients require evidence")


@dataclass(frozen=True, slots=True)
class BackupStoragePolicy:
    """One Commvault storage policy, read from the real `GET webservice/V2/StoragePolicy`
    inventory. `number_of_copies` is the one field this connector treats as a real redundancy
    signal (a policy with zero copies retains no backup data); it is optional because it is
    read from a separate, bounded per-policy Details call and may be unavailable for some
    policies (see `ConfiguredCommvaultBackupOverviewProvider`)."""

    policy_id: str
    policy_name: str
    number_of_copies: int | None
    number_of_streams: int
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.policy_id.strip() or not self.policy_name.strip():
            raise ValueError("storage policies require an identifier and name")
        if (self.number_of_copies is not None and self.number_of_copies < 0) or (
            self.number_of_streams < 0
        ):
            raise ValueError("storage policy counts must not be negative")
        if not self.evidence_references:
            raise ValueError("storage policies require evidence")


@dataclass(frozen=True, slots=True)
class BackupRecoveryPoint:
    """One backed-up item, read from a bounded, per-subclient root-level browse
    (`GET webservice/Subclient/{id}/Browse`). This is a small sample for a bounded number of
    clients and subclients, not an exhaustive recovery-point catalog -- see
    `ConfiguredCommvaultBackupOverviewProvider._read_recovery_points`. `modification_time` and
    `backup_time` are optional: not every browsed item carries them (e.g. the confirmed
    virtual-machine browse example omits some advancedData fields other items carry)."""

    client_id: str
    client_name: str
    subclient_id: str
    subclient_name: str
    name: str
    path: str
    size: int | None
    modification_time: datetime | None
    backup_job_id: int | None
    backup_time: datetime | None
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.modification_time is not None and self.modification_time.tzinfo is None:
            raise ValueError("modification_time must be timezone-aware")
        if self.backup_time is not None and self.backup_time.tzinfo is None:
            raise ValueError("backup_time must be timezone-aware")
        if not self.name.strip() or not self.path.strip():
            raise ValueError("recovery points require a name and path")
        if not self.evidence_references:
            raise ValueError("recovery points require evidence")


@dataclass(frozen=True, slots=True)
class BackupFinding:
    finding_id: str
    subject_id: str
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
            raise ValueError("findings require a summary and evidence")


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
class BackupInvestigation:
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
class BackupReport:
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
class BackupOverview:
    snapshot_id: str
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    data_profile: str
    generated_at: datetime
    clients: tuple[BackupProtectedClient, ...]
    policies: tuple[BackupStoragePolicy, ...]
    recovery_points: tuple[BackupRecoveryPoint, ...]
    findings: tuple[BackupFinding, ...]
    evidence: tuple[EvidenceRecord, ...]
    investigation: BackupInvestigation
    report: BackupReport

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        evidence_ids = {item.reference for item in self.evidence}
        referenced = {
            reference
            for references in (
                *(client.evidence_references for client in self.clients),
                *(policy.evidence_references for policy in self.policies),
                *(point.evidence_references for point in self.recovery_points),
                *(finding.evidence_references for finding in self.findings),
                self.investigation.evidence_references,
                self.report.evidence_references,
            )
            for reference in references
        }
        if not referenced <= evidence_ids:
            raise ValueError("overview contains unresolved evidence references")
