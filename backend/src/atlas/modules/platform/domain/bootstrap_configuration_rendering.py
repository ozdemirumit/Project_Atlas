from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.release_preflight import SHA256_PATTERN, DeploymentProfile


class ConfigurationRenderingState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfigurationFileDisposition(StrEnum):
    PUBLISHED = "published"
    REUSED = "reused"


@dataclass(frozen=True, slots=True)
class RenderedConfigurationEvidence:
    file_id: str
    sha256: str
    size_bytes: int
    disposition: ConfigurationFileDisposition

    def __post_init__(self) -> None:
        validate_stable_identifier(self.file_id, "configuration file id")
        if not SHA256_PATTERN.fullmatch(self.sha256) or self.size_bytes < 1:
            raise ValueError("configuration file evidence is invalid")


@dataclass(frozen=True, slots=True)
class ConfigurationRenderingExecution:
    execution_id: str
    phase_id: str
    release_id: str
    profile: DeploymentProfile
    configuration_schema_version: str
    configuration_digest: str
    state: ConfigurationRenderingState
    result_code: str
    started_at: datetime
    completed_at: datetime | None
    evidence: tuple[RenderedConfigurationEvidence, ...]
    total_bytes: int

    def __post_init__(self) -> None:
        for value, label in (
            (self.execution_id, "execution_id"),
            (self.phase_id, "phase_id"),
            (self.release_id, "release_id"),
            (self.configuration_schema_version, "configuration_schema_version"),
            (self.result_code, "result_code"),
        ):
            validate_stable_identifier(value, label)
        if self.phase_id != "phase.configure":
            raise ValueError("configuration rendering is bound to phase.configure")
        if self.configuration_schema_version != "atlas.deployment-configuration.v1":
            raise ValueError("configuration rendering schema is unsupported")
        if not SHA256_PATTERN.fullmatch(self.configuration_digest):
            raise ValueError("configuration rendering digest is invalid")
        if self.started_at.tzinfo is None or (
            self.completed_at is not None and self.completed_at.tzinfo is None
        ):
            raise ValueError("configuration rendering timestamps must be timezone-aware")
        if self.state is ConfigurationRenderingState.RUNNING:
            if self.completed_at is not None or self.evidence or self.total_bytes != 0:
                raise ValueError("running configuration rendering cannot contain final evidence")
        elif self.completed_at is None or self.completed_at < self.started_at:
            raise ValueError("finished configuration rendering requires a valid completion time")
        if self.state is ConfigurationRenderingState.COMPLETED:
            if not self.evidence or self.total_bytes != sum(
                item.size_bytes for item in self.evidence
            ):
                raise ValueError("completed configuration rendering evidence is incomplete")
        elif self.evidence or self.total_bytes != 0:
            raise ValueError("non-completed configuration rendering cannot contain file evidence")
        file_ids = tuple(item.file_id for item in self.evidence)
        if len(file_ids) != len(set(file_ids)) or len(file_ids) > 16:
            raise ValueError("configuration rendering evidence contains invalid identifiers")


@dataclass(frozen=True, slots=True)
class ConfigurationRenderingReceipt:
    evidence: tuple[RenderedConfigurationEvidence, ...]

    def __post_init__(self) -> None:
        if not self.evidence or len(self.evidence) > 16:
            raise ValueError("configuration rendering receipt is empty or too large")
        identifiers = tuple(item.file_id for item in self.evidence)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("configuration rendering receipt contains duplicate files")

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.evidence)
