from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CommvaultJobStatus(StrEnum):
    """Commvault's GET Job API `status` field. This is the complete 19-value vocabulary
    documented in the "Valid values are" list under `jobSummary.status` in Commvault's official
    REST API reference (a two-column table; values confirmed by inspecting each entry's exact
    page coordinates to correctly resolve wrapped multi-word entries, e.g. "Running" and
    "Running (cannot be verified)" are two distinct documented values, not one wrapped entry).
    Any value not in this confirmed set maps to UNKNOWN rather than being guessed."""

    RUNNING = "Running"
    WAITING = "Waiting"
    PENDING = "Pending"
    SUSPEND = "Suspend"
    SUSPENDED = "Suspended"
    KILL_PENDING = "Kill Pending"
    INTERRUPT_PENDING = "Interrupt Pending"
    INTERRUPTED = "Interrupted"
    QUEUED = "Queued"
    RUNNING_CANNOT_BE_VERIFIED = "Running (cannot be verified)"
    ABNORMAL_TERMINATED = "Abnormal Terminated"
    CLEANUP = "Cleanup"
    COMPLETED = "Completed"
    COMPLETED_WITH_ERRORS = "Completed w/ one or more errors"
    COMPLETED_WITH_WARNINGS = "Completed w/ one or more warnings"
    COMMITTED = "Committed"
    FAILED = "Failed"
    FAILED_TO_START = "Failed to Start"
    KILLED = "Killed"
    UNKNOWN = "unknown"


def job_status_from_value(raw: object) -> CommvaultJobStatus:
    if isinstance(raw, str):
        try:
            return CommvaultJobStatus(raw)
        except ValueError:
            return CommvaultJobStatus.UNKNOWN
    return CommvaultJobStatus.UNKNOWN


@dataclass(frozen=True, slots=True)
class CommvaultJob:
    job_id: int
    client_name: str
    subclient_name: str
    job_type: str
    status: CommvaultJobStatus
    percent_complete: int

    def __post_init__(self) -> None:
        if self.job_id < 0:
            raise ValueError("job_id must not be negative")
        if not self.client_name.strip():
            raise ValueError("job requires a client name")
        if not 0 <= self.percent_complete <= 100:
            raise ValueError("percent_complete must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class CommvaultJobListResult:
    jobs: tuple[CommvaultJob, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("job list results require evidence")


@dataclass(frozen=True, slots=True)
class CommvaultClientRecord:
    """One registered Commvault client, read from the real `GET webservice/Client` inventory.
    The official REST API reference's response-parameter table for this exact list endpoint
    (as opposed to the single-client `GET Client/{clientId}` endpoint, whose table is longer)
    documents only `clientId`, `clientName`, `hostName`, `displayName`, and `clientGUID` under
    `clientEntity`, plus `enableAccessControl` under `clientProps` -- confirmed further by a
    literal example list response whose `clientProps` element carries only
    `enableAccessControl`. Neither `clientProps.IsDeletedClient` (documented only for the
    single-client endpoint) nor any `osInfo.Type` field is confirmed present on this list read,
    so both are optional here and parsed defensively rather than required."""

    client_id: str
    client_name: str
    host_name: str
    os_type: str | None
    is_deleted: bool | None

    def __post_init__(self) -> None:
        if not self.client_id.strip() or not self.client_name.strip():
            raise ValueError("client record requires an identifier and name")


@dataclass(frozen=True, slots=True)
class CommvaultClientListResult:
    clients: tuple[CommvaultClientRecord, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("client list results require evidence")


@dataclass(frozen=True, slots=True)
class CommvaultStoragePolicy:
    """One Commvault storage policy, read from the real `GET webservice/V2/StoragePolicy`
    inventory. `number_of_copies` is not part of that list endpoint's documented response --
    it is optional here, sourced instead (when available) from the bounded per-policy Details
    read, see `CommvaultClient.read_storage_policy_copy_count()`."""

    policy_id: str
    policy_name: str
    number_of_copies: int | None
    number_of_streams: int

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or not self.policy_name.strip():
            raise ValueError("storage policy requires an identifier and name")
        if (self.number_of_copies is not None and self.number_of_copies < 0) or (
            self.number_of_streams < 0
        ):
            raise ValueError("storage policy counts must not be negative")


@dataclass(frozen=True, slots=True)
class CommvaultStoragePolicyListResult:
    policies: tuple[CommvaultStoragePolicy, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("storage policy list results require evidence")
