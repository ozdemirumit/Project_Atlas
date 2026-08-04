from __future__ import annotations

import hmac
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.platform.application.release_preflight import canonical_manifest_payload
from atlas.modules.platform.domain.release_preflight import (
    AcquisitionMode,
    ArtifactObservation,
    DeploymentProfile,
    HostSnapshot,
    ManifestArtifact,
    ReleaseManifest,
)

LAB_SIGNING_KEY_REFERENCE = "secret.release-signing.lab"


class LabHmacReleaseSignatureVerifier:
    def __init__(self, key: bytes) -> None:
        if len(key) < 32:
            raise ValueError("lab release verification key must contain at least 256 bits")
        self._key = key

    def verify(self, payload: bytes, manifest: ReleaseManifest) -> bool:
        if manifest.signing_key_reference != LAB_SIGNING_KEY_REFERENCE:
            return False
        expected = hmac.digest(self._key, payload, "sha256").hex()
        return hmac.compare_digest(expected, manifest.signature)


class SyntheticReleaseArtifactInventory:
    def __init__(self, manifest: ReleaseManifest) -> None:
        self._manifest = manifest

    async def observations(self, mode: AcquisitionMode) -> tuple[ArtifactObservation, ...]:
        prefix = {
            AcquisitionMode.CONNECTED: "https://releases.synthetic.atlas/",
            AcquisitionMode.MIRRORED: "mirror://atlas-lab/",
            AcquisitionMode.OFFLINE: "offline://bundle/atlas-lab/",
        }[mode]
        return tuple(
            ArtifactObservation(
                relative_path=item.relative_path,
                size_bytes=item.size_bytes,
                sha256=item.sha256,
                source=f"{prefix}{item.relative_path}",
            )
            for item in self._manifest.artifacts
        )


class SyntheticPreflightHostProbe:
    async def snapshot(self) -> HostSnapshot:
        return HostSnapshot(
            operating_system="linux",
            architecture="x86_64",
            python_version="3.12.13",
            cpu_cores=4,
            memory_mb=8192,
            disk_available_mb=51200,
            available_tools=("docker", "python"),
            busy_ports=(),
            configuration=(
                ("api_bind", "127.0.0.1"),
                ("database_credential", "secret.database.atlas"),
            ),
            secret_reference_ids=("secret.database.atlas", "secret.release-signing.lab"),
        )


def build_synthetic_release_manifest(key: bytes) -> ReleaseManifest:
    artifacts = (
        _artifact(
            "artifact.backend.image", "component.backend", "artifacts/backend.oci", b"atlas-backend"
        ),
        _artifact(
            "artifact.frontend.image",
            "component.frontend",
            "artifacts/frontend.oci",
            b"atlas-frontend",
        ),
        _artifact(
            "artifact.database.migrations",
            "component.database",
            "artifacts/migrations.tar",
            b"atlas-migrations",
        ),
    )
    manifest = ReleaseManifest(
        schema_version="atlas.release-manifest.v1",
        release_id="release.atlas.lab-0.1.0",
        release_version="0.1.0",
        build_id="build.synthetic.main",
        source_commit="7f7954c",
        supported_profiles=(DeploymentProfile.DEVELOPER, DeploymentProfile.LINUX_LAB),
        artifacts=artifacts,
        configuration_schema_version="schema.configuration.v1",
        minimum_python="3.12",
        minimum_cpu_cores=2,
        minimum_memory_mb=4096,
        minimum_disk_mb=10240,
        required_tools=("docker", "python"),
        required_ports=(8000, 5173),
        approved_connected_sources=("https://releases.synthetic.atlas/",),
        approved_mirror_sources=("mirror://atlas-lab/",),
        known_limitations=(
            "Synthetic lab trust only; production signing and deployment are not authorized.",
        ),
        publisher_id="publisher.atlas.synthetic",
        signature_algorithm="hmac-sha256-lab",
        signing_key_reference=LAB_SIGNING_KEY_REFERENCE,
        signature="0" * 64,
        published_at=datetime(2026, 8, 4, 12, 30, tzinfo=UTC),
    )
    signature = hmac.digest(key, canonical_manifest_payload(manifest), "sha256").hex()
    return replace(manifest, signature=signature)


def _artifact(
    artifact_id: str, component: str, relative_path: str, content: bytes
) -> ManifestArtifact:
    digest = sha256(content).hexdigest()
    return ManifestArtifact(
        artifact_id=artifact_id,
        component=component,
        relative_path=relative_path,
        media_type="application/vnd.oci.image.layout.v1+tar",
        size_bytes=len(content),
        sha256=digest,
        required=True,
        upstream_source=f"https://releases.synthetic.atlas/{relative_path}",
        immutable_reference=f"oci://registry.synthetic.atlas/{component}@sha256:{digest}",
    )
