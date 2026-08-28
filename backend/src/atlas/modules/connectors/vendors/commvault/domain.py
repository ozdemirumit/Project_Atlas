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
