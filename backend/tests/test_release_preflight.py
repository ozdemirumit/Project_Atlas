from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.platform.adapters.release_preflight import (
    LabHmacReleaseSignatureVerifier,
    SyntheticPreflightHostProbe,
    SyntheticReleaseArtifactInventory,
    build_synthetic_release_manifest,
)
from atlas.modules.platform.application.release_preflight import (
    ReleasePreflightService,
    canonical_manifest_payload,
)
from atlas.modules.platform.application.release_preflight_ports import (
    PreflightHostProbe,
    ReleaseArtifactInventory,
)
from atlas.modules.platform.domain.release_preflight import (
    AcquisitionMode,
    ArtifactObservation,
    DeploymentProfile,
    HostSnapshot,
    PreflightState,
    ReleaseManifest,
)

KEY = b"release-preflight-test-key-material"[:32]


class CollectingAuditSink:
    def __init__(self, *, fail_preflight: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail_preflight = fail_preflight

    async def record(self, event: AuditRecord) -> None:
        if self.fail_preflight and event.event_type == "atlas.platform.release-preflight.read":
            raise RuntimeError("required preflight audit unavailable")
        self.records.append(event)


class FixedInventory:
    def __init__(self, observations: tuple[ArtifactObservation, ...]) -> None:
        self.items = observations

    async def observations(self, mode: AcquisitionMode) -> tuple[ArtifactObservation, ...]:
        return self.items


class FixedHostProbe:
    def __init__(self, snapshot: HostSnapshot) -> None:
        self.value = snapshot

    async def snapshot(self) -> HostSnapshot:
        return self.value


def actor() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.enterprise.platform-operator",
        display_name="Platform Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=build_synthetic_release_manifest(KEY).published_at,
        organization_id="organization.enterprise",
        role_ids=("role.platform-operator",),
    )


def service(
    *,
    manifest: ReleaseManifest | None = None,
    inventory: ReleaseArtifactInventory | None = None,
    host: PreflightHostProbe | None = None,
    sink: CollectingAuditSink | None = None,
) -> ReleasePreflightService:
    selected_manifest = manifest or build_synthetic_release_manifest(KEY)
    return ReleasePreflightService(
        manifest=selected_manifest,
        signature_verifier=LabHmacReleaseSignatureVerifier(KEY),
        artifact_inventory=inventory or SyntheticReleaseArtifactInventory(selected_manifest),
        host_probe=host or SyntheticPreflightHostProbe(),
        audit_sink=sink or CollectingAuditSink(),
        environment_id="environment.test",
    )


@pytest.mark.asyncio
async def test_canonical_manifest_signature_and_offline_inventory_pass() -> None:
    manifest = build_synthetic_release_manifest(KEY)
    payload = canonical_manifest_payload(manifest)
    report = await service(manifest=manifest).run(
        actor=actor(),
        mode=AcquisitionMode.OFFLINE,
        profile=DeploymentProfile.LINUX_LAB,
        correlation_id="correlation.preflight.pass",
    )

    assert payload == canonical_manifest_payload(manifest)
    assert report.state is PreflightState.PASSED
    assert report.mutation_authorized is False
    assert report.execution_authorized is False
    assert all(item.state is PreflightState.PASSED for item in report.checks)


@pytest.mark.asyncio
async def test_signature_substitution_fails_without_hiding_other_checks() -> None:
    manifest = replace(build_synthetic_release_manifest(KEY), signature="f" * 64)
    report = await service(manifest=manifest).run(
        actor=actor(),
        mode=AcquisitionMode.OFFLINE,
        profile=DeploymentProfile.LINUX_LAB,
        correlation_id="correlation.preflight.signature",
    )

    assert report.state is PreflightState.FAILED
    signature = next(item for item in report.checks if item.code == "release.signature.valid")
    assert signature.state is PreflightState.FAILED
    assert KEY.hex() not in repr(report)


@pytest.mark.asyncio
async def test_missing_modified_extra_and_public_mirror_artifacts_fail_closed() -> None:
    manifest = build_synthetic_release_manifest(KEY)
    first, second, *_ = manifest.artifacts
    observations = (
        ArtifactObservation(
            relative_path=first.relative_path,
            size_bytes=first.size_bytes,
            sha256="0" * 64,
            source="https://public.invalid/artifact",
        ),
        ArtifactObservation(
            relative_path="artifacts/unlisted.bin",
            size_bytes=1,
            sha256="1" * 64,
            source="mirror://atlas-lab/artifacts/unlisted.bin",
        ),
    )
    report = await service(inventory=FixedInventory(observations)).run(
        actor=actor(),
        mode=AcquisitionMode.MIRRORED,
        profile=DeploymentProfile.LINUX_LAB,
        correlation_id="correlation.preflight.artifacts",
    )

    failed_codes = {item.code for item in report.checks if item.state is PreflightState.FAILED}
    assert report.state is PreflightState.FAILED
    assert "artifacts.inventory.exact" in failed_codes
    assert f"artifact.{first.artifact_id}" in failed_codes
    assert f"artifact.{second.artifact_id}" in failed_codes
    assert all("public.invalid" not in item.evidence for item in report.checks)


@pytest.mark.asyncio
async def test_incompatible_host_ports_capacity_and_plaintext_configuration_block() -> None:
    host = HostSnapshot(
        operating_system="windows",
        architecture="arm64",
        python_version="3.11",
        cpu_cores=1,
        memory_mb=1024,
        disk_available_mb=2048,
        available_tools=("python",),
        busy_ports=(8000,),
        configuration=(("api_bind", "0.0.0.0"), ("database_password", "raw-value")),
        secret_reference_ids=(),
    )
    report = await service(host=FixedHostProbe(host)).run(
        actor=actor(),
        mode=AcquisitionMode.OFFLINE,
        profile=DeploymentProfile.LINUX_LAB,
        correlation_id="correlation.preflight.host",
    )

    failed = {item.code for item in report.checks if item.state is PreflightState.FAILED}
    assert {
        "host.operating-system.supported",
        "host.architecture.supported",
        "host.python.compatible",
        "host.capacity.minimum",
        "host.tools.available",
        "host.ports.available",
        "configuration.safe",
    } <= failed
    assert "raw-value" not in repr(report)


def test_manifest_rejects_unsafe_paths_duplicates_and_mutable_references() -> None:
    artifact = build_synthetic_release_manifest(KEY).artifacts[0]
    with pytest.raises(ValueError, match="unsafe"):
        replace(artifact, relative_path="../private.key")
    with pytest.raises(ValueError, match="immutable"):
        replace(artifact, immutable_reference="oci://registry/atlas:latest")
    with pytest.raises(ValueError, match="embedded credentials"):
        replace(artifact, upstream_source="https://operator:secret@releases.invalid/artifact")
    manifest = build_synthetic_release_manifest(KEY)
    with pytest.raises(ValueError, match="duplicate"):
        replace(manifest, artifacts=(artifact, artifact))
    with pytest.raises(ValueError, match="embedded credentials"):
        replace(manifest, approved_connected_sources=("https://token@releases.invalid/",))


def test_development_api_exposes_read_only_preflight_and_audits() -> None:
    sink = CollectingAuditSink()
    app = create_app(
        Settings(environment="test", development_identity_enabled=True), audit_sink=sink
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/platform/release-preflight?mode=offline&profile=linux_lab",
            headers={"X-Correlation-ID": "correlation.preflight.api"},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["state"] == "passed"
    assert data["mutation_authorized"] is False
    assert data["execution_authorized"] is False
    assert data["correlation_id"] == "correlation.preflight.api"
    assert "synthetic-release-verifier" not in response.text
    assert any(item.event_type == "atlas.platform.release-preflight.read" for item in sink.records)


def test_api_denies_missing_exact_assignment_without_inventory_disclosure() -> None:
    app = create_app(
        Settings(
            environment="test",
            development_identity_enabled=True,
            development_role_ids=(),
        )
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/platform/release-preflight")

    assert response.status_code == 403
    assert "artifact.backend.image" not in response.text
    assert "linux" not in response.text.lower()


def test_required_audit_failure_blocks_preflight_response() -> None:
    sink = CollectingAuditSink(fail_preflight=True)
    custom_service = service(sink=sink)
    app = create_app(
        Settings(environment="test", development_identity_enabled=True),
        audit_sink=sink,
        release_preflight_service=custom_service,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/platform/release-preflight")

    assert response.status_code == 500
    assert "artifact.backend.image" not in response.text
