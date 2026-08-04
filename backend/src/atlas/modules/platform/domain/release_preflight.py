from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from atlas.modules.identity.domain.models import validate_stable_identifier

SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def _validate_release_source(value: str, schemes: tuple[str, ...], field: str) -> None:
    parsed = urlsplit(value)
    if (
        len(value) > 2048
        or any(ord(item) < 32 for item in value)
        or parsed.scheme not in schemes
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{field} is invalid or contains embedded credentials")


class AcquisitionMode(StrEnum):
    CONNECTED = "connected"
    MIRRORED = "mirrored"
    OFFLINE = "offline"


class DeploymentProfile(StrEnum):
    DEVELOPER = "developer"
    LINUX_LAB = "linux_lab"


class PreflightState(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    UNCHECKED = "unchecked"


@dataclass(frozen=True, slots=True)
class ManifestArtifact:
    artifact_id: str
    component: str
    relative_path: str
    media_type: str
    size_bytes: int
    sha256: str
    required: bool
    upstream_source: str
    immutable_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.artifact_id, "artifact_id")
        validate_stable_identifier(self.component, "component")
        path = PurePosixPath(self.relative_path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or self.relative_path != path.as_posix()
            or not self.relative_path.startswith("artifacts/")
        ):
            raise ValueError("release artifact path is unsafe")
        if not 1 <= len(self.media_type) <= 128 or any(ord(item) < 32 for item in self.media_type):
            raise ValueError("release artifact media type is invalid")
        if self.size_bytes < 1 or not SHA256_PATTERN.fullmatch(self.sha256):
            raise ValueError("release artifact size or digest is invalid")
        _validate_release_source(
            self.upstream_source, ("https", "oci", "mirror", "offline"), "artifact source"
        )
        _validate_release_source(self.immutable_reference, ("oci",), "artifact reference")
        if not re.search(r"@sha256:[a-f0-9]{64}$", self.immutable_reference):
            raise ValueError("release artifact reference is not immutable")


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    schema_version: str
    release_id: str
    release_version: str
    build_id: str
    source_commit: str
    supported_profiles: tuple[DeploymentProfile, ...]
    artifacts: tuple[ManifestArtifact, ...]
    configuration_schema_version: str
    minimum_python: str
    minimum_cpu_cores: int
    minimum_memory_mb: int
    minimum_disk_mb: int
    required_tools: tuple[str, ...]
    required_ports: tuple[int, ...]
    approved_connected_sources: tuple[str, ...]
    approved_mirror_sources: tuple[str, ...]
    known_limitations: tuple[str, ...]
    publisher_id: str
    signature_algorithm: str
    signing_key_reference: str
    signature: str
    published_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.release_id, "release_id"),
            (self.build_id, "build_id"),
            (self.configuration_schema_version, "configuration_schema_version"),
            (self.publisher_id, "publisher_id"),
            (self.signing_key_reference, "signing_key_reference"),
        ):
            validate_stable_identifier(value, name)
        if self.schema_version != "atlas.release-manifest.v1":
            raise ValueError("release manifest schema is unsupported")
        if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-z0-9.]+)?", self.release_version):
            raise ValueError("release version is invalid")
        if not re.fullmatch(r"[a-f0-9]{7,64}", self.source_commit):
            raise ValueError("source commit is invalid")
        if not self.supported_profiles or len(set(self.supported_profiles)) != len(
            self.supported_profiles
        ):
            raise ValueError("supported release profiles are invalid")
        artifact_ids = [item.artifact_id for item in self.artifacts]
        artifact_paths = [item.relative_path for item in self.artifacts]
        if not self.artifacts or len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("release artifacts contain duplicate identifiers")
        if len(artifact_paths) != len(set(artifact_paths)):
            raise ValueError("release artifacts contain duplicate paths")
        if self.minimum_cpu_cores < 1 or min(self.minimum_memory_mb, self.minimum_disk_mb) < 1:
            raise ValueError("release resource requirements are invalid")
        if not self.required_tools or len(self.required_tools) != len(set(self.required_tools)):
            raise ValueError("required tools are invalid")
        if any(not re.fullmatch(r"[a-z0-9_.-]{2,64}", item) for item in self.required_tools):
            raise ValueError("required tool identifier is invalid")
        if len(self.required_ports) != len(set(self.required_ports)) or any(
            not 1 <= item <= 65535 for item in self.required_ports
        ):
            raise ValueError("required ports are invalid")
        if not self.approved_connected_sources or not self.approved_mirror_sources:
            raise ValueError("release source allowlists are required")
        for item in self.approved_connected_sources:
            _validate_release_source(item, ("https",), "connected source")
            if not item.endswith("/"):
                raise ValueError("connected source must end with a path boundary")
        for item in self.approved_mirror_sources:
            _validate_release_source(item, ("mirror",), "mirror source")
            if not item.endswith("/"):
                raise ValueError("mirror source must end with a path boundary")
        if self.signature_algorithm != "hmac-sha256-lab":
            raise ValueError("release signature algorithm is unsupported")
        if not SHA256_PATTERN.fullmatch(self.signature):
            raise ValueError("release signature is invalid")
        if self.published_at.tzinfo is None:
            raise ValueError("release publication time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ArtifactObservation:
    relative_path: str
    size_bytes: int
    sha256: str
    source: str


@dataclass(frozen=True, slots=True)
class HostSnapshot:
    operating_system: str
    architecture: str
    python_version: str
    cpu_cores: int
    memory_mb: int
    disk_available_mb: int
    available_tools: tuple[str, ...]
    busy_ports: tuple[int, ...]
    configuration: tuple[tuple[str, str], ...]
    secret_reference_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    code: str
    category: str
    state: PreflightState
    mandatory: bool
    summary: str
    evidence: str
    remediation: str | None = None


@dataclass(frozen=True, slots=True)
class ReleasePreflightReport:
    report_id: str
    release_id: str
    release_version: str
    build_id: str
    manifest_digest: str
    mode: AcquisitionMode
    profile: DeploymentProfile
    state: PreflightState
    checks: tuple[PreflightCheck, ...]
    generated_at: datetime
    correlation_id: str
    mutation_authorized: bool = False
    execution_authorized: bool = False
