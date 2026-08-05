from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_SAFE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,239}$")
_WINDOWS_RESERVED = frozenset(
    {
        "aux",
        "con",
        "nul",
        "prn",
        *(f"com{index}" for index in range(1, 10)),
        *(f"lpt{index}" for index in range(1, 10)),
    }
)
_MEDIA_TYPES = frozenset(
    {
        "application/json",
        "application/toml",
        "application/yaml",
        "text/markdown",
        "text/x-python",
    }
)


def validate_generated_path(value: str) -> None:
    if _SAFE_PATH.fullmatch(value) is None:
        raise ValueError("generated file path is outside platform bounds")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("generated file path is unsafe")
    for part in path.parts:
        stem = part.split(".", 1)[0].casefold()
        if stem in _WINDOWS_RESERVED or len(part) > 80:
            raise ValueError("generated file path is not portable")


class BuilderGenerationState(StrEnum):
    QUARANTINED = "quarantined"


@dataclass(frozen=True, slots=True)
class BuilderGeneratedFile:
    relative_path: str
    media_type: str
    sha256: str
    size_bytes: int
    source_candidate_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_generated_path(self.relative_path)
        if self.media_type not in _MEDIA_TYPES:
            raise ValueError("generated file media type is unsupported")
        if _DIGEST.fullmatch(self.sha256) is None or not 1 <= self.size_bytes <= 65_536:
            raise ValueError("generated file digest or size is invalid")
        if len(self.source_candidate_ids) != len(set(self.source_candidate_ids)):
            raise ValueError("generated file candidate lineage must be unique")
        for candidate_id in self.source_candidate_ids:
            validate_stable_identifier(candidate_id, "generated file candidate id")


@dataclass(frozen=True, slots=True)
class McpBuilderGeneration:
    generation_id: str
    schema_version: str
    version: int
    state: BuilderGenerationState
    project_id: str
    project_version: int
    project_digest: str
    source_digest: str
    checkpoint_id: str
    checkpoint_digest: str
    organization_id: str
    environment_id: str
    requested_by: str
    language_profile: str
    template_version: str
    artifact_digest: str
    artifact_size_bytes: int
    files: tuple[BuilderGeneratedFile, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    created_at: datetime
    artifact_published: bool = True
    generated_artifact_created: bool = True
    validation_completed: bool = False
    candidate_package_created: bool = False
    connector_registered: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    network_request_performed: bool = False
    model_inference_performed: bool = False
    subprocess_invoked: bool = False
    dynamic_code_execution_performed: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.generation_id, "generation id"),
            (self.schema_version, "schema version"),
            (self.project_id, "project id"),
            (self.checkpoint_id, "checkpoint id"),
            (self.organization_id, "organization id"),
            (self.environment_id, "environment id"),
            (self.requested_by, "requester id"),
            (self.language_profile, "language profile"),
            (self.template_version, "template version"),
        ):
            validate_stable_identifier(value, name)
        if self.version != 1 or self.project_version != 1:
            raise ValueError("Builder generation version is invalid")
        for value in (
            self.project_digest,
            self.source_digest,
            self.checkpoint_digest,
            self.artifact_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Builder generation digest is invalid")
        if not 1 <= len(self.files) <= 256:
            raise ValueError("Builder generation file inventory is outside platform bounds")
        paths = [item.relative_path for item in self.files]
        if len(paths) != len(set(paths)) or len(paths) != len({path.casefold() for path in paths}):
            raise ValueError("Builder generation file paths must be portable and unique")
        expected_size = sum(item.size_bytes for item in self.files)
        if self.artifact_size_bytes != expected_size or not 1 <= expected_size <= 2_097_152:
            raise ValueError("Builder generation artifact size is invalid")
        if self.created_at.tzinfo is None or not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Builder generation timestamp or idempotency key is invalid")
        if (
            self.state is not BuilderGenerationState.QUARANTINED
            or not self.artifact_published
            or not self.generated_artifact_created
        ):
            raise ValueError("Builder generation must remain a published quarantined artifact")
        if any(
            (
                self.validation_completed,
                self.candidate_package_created,
                self.connector_registered,
                self.connector_installed,
                self.connector_enabled,
                self.network_request_performed,
                self.model_inference_performed,
                self.subprocess_invoked,
                self.dynamic_code_execution_performed,
                self.runtime_trust_granted,
                self.execution_authorized,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("Builder generation violates the quarantine boundary")
