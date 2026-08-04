from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.release_preflight import SHA256_PATTERN, AcquisitionMode


class ArtifactAcquisitionState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactDisposition(StrEnum):
    PUBLISHED = "published"
    REUSED = "reused"


@dataclass(frozen=True, slots=True)
class VerifiedArtifactEvidence:
    artifact_id: str
    sha256: str
    size_bytes: int
    disposition: ArtifactDisposition

    def __post_init__(self) -> None:
        validate_stable_identifier(self.artifact_id, "artifact_id")
        if not SHA256_PATTERN.fullmatch(self.sha256) or self.size_bytes < 1:
            raise ValueError("artifact evidence is invalid")


@dataclass(frozen=True, slots=True)
class ArtifactAcquisitionExecution:
    execution_id: str
    phase_id: str
    release_id: str
    manifest_digest: str
    mode: AcquisitionMode
    preflight_report_id: str
    state: ArtifactAcquisitionState
    result_code: str
    started_at: datetime
    completed_at: datetime | None
    evidence: tuple[VerifiedArtifactEvidence, ...]
    total_bytes: int

    def __post_init__(self) -> None:
        for value, label in (
            (self.execution_id, "execution_id"),
            (self.phase_id, "phase_id"),
            (self.release_id, "release_id"),
            (self.preflight_report_id, "preflight_report_id"),
            (self.result_code, "result_code"),
        ):
            validate_stable_identifier(value, label)
        if self.phase_id != "phase.acquire":
            raise ValueError("artifact acquisition is bound to phase.acquire")
        if not SHA256_PATTERN.fullmatch(self.manifest_digest):
            raise ValueError("artifact acquisition manifest digest is invalid")
        if self.started_at.tzinfo is None or (
            self.completed_at is not None and self.completed_at.tzinfo is None
        ):
            raise ValueError("artifact acquisition timestamps must be timezone-aware")
        if self.state is ArtifactAcquisitionState.RUNNING:
            if self.completed_at is not None or self.evidence or self.total_bytes != 0:
                raise ValueError("running artifact acquisition cannot contain final evidence")
        elif self.completed_at is None or self.completed_at < self.started_at:
            raise ValueError("finished artifact acquisition requires a valid completion time")
        if self.state is ArtifactAcquisitionState.COMPLETED:
            if not self.evidence or self.total_bytes != sum(
                item.size_bytes for item in self.evidence
            ):
                raise ValueError("completed artifact acquisition evidence is incomplete")
        elif self.evidence or self.total_bytes != 0:
            raise ValueError("non-completed artifact acquisition cannot contain artifact evidence")
        artifact_ids = tuple(item.artifact_id for item in self.evidence)
        if len(artifact_ids) != len(set(artifact_ids)) or len(artifact_ids) > 128:
            raise ValueError("artifact acquisition evidence contains invalid identifiers")


@dataclass(frozen=True, slots=True)
class ArtifactAcquisitionReceipt:
    evidence: tuple[VerifiedArtifactEvidence, ...]

    def __post_init__(self) -> None:
        if not self.evidence or len(self.evidence) > 128:
            raise ValueError("artifact acquisition receipt is empty or too large")
        identifiers = tuple(item.artifact_id for item in self.evidence)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("artifact acquisition receipt contains duplicate artifacts")

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.evidence)
