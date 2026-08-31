from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CommvaultJobStatus(StrEnum):
    """Commvault's GET Job API `status` field. Only the values directly confirmed against real
    sources are named here -- a literal example response on the official api.commvault.com
    JobOperations reference page ("Completed"), and the "Killed" and "Suspended, Waiting, ..."
    values referenced by Commvault's own REST API and cvpysdk documentation. Commvault's own
    documentation states the complete status vocabulary is longer than what could be
    independently confirmed during connector construction, so any value not in this confirmed set
    maps to UNKNOWN rather than being guessed."""

    COMPLETED = "Completed"
    RUNNING = "Running"
    WAITING = "Waiting"
    SUSPENDED = "Suspended"
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
    `is_deleted` (the confirmed real `clientProps.IsDeletedClient` field) is the one field this
    connector treats as a real protection-coverage signal."""

    client_id: str
    client_name: str
    host_name: str
    os_type: str
    is_deleted: bool

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
    inventory."""

    policy_id: str
    policy_name: str
    number_of_copies: int
    number_of_streams: int

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or not self.policy_name.strip():
            raise ValueError("storage policy requires an identifier and name")
        if self.number_of_copies < 0 or self.number_of_streams < 0:
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
