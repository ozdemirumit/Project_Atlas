from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.core.persistence.models import Base
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.platform.adapters.bootstrap_artifact_filesystem import (
    FileSystemReleaseArtifactPublisher,
    MemoryArtifactContentSource,
)
from atlas.modules.platform.adapters.bootstrap_state_memory import (
    InMemoryBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_state_postgres import (
    PostgreSQLBootstrapStateRepository,
)
from atlas.modules.platform.adapters.release_preflight import (
    SYNTHETIC_ARTIFACT_CONTENT,
    LabHmacReleaseSignatureVerifier,
    SyntheticPreflightHostProbe,
    SyntheticReleaseArtifactInventory,
    build_synthetic_release_manifest,
)
from atlas.modules.platform.application.bootstrap_artifact_acquisition import (
    BootstrapArtifactAcquisitionService,
    BootstrapArtifactExecutionError,
)
from atlas.modules.platform.application.bootstrap_artifact_ports import (
    ArtifactAcquisitionError,
)
from atlas.modules.platform.application.bootstrap_state import BootstrapStateService
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError
from atlas.modules.platform.application.release_preflight import (
    ReleasePreflightService,
    canonical_manifest_payload,
)
from atlas.modules.platform.application.release_preflight_ports import ReleaseArtifactInventory
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import (
    ArtifactAcquisitionExecution,
    ArtifactAcquisitionState,
    ArtifactDisposition,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapMutationResult,
    BootstrapRunIdentity,
)
from atlas.modules.platform.domain.release_preflight import (
    AcquisitionMode,
    ArtifactObservation,
    DeploymentProfile,
    PreflightState,
)

NOW = datetime(2026, 8, 4, 16, 0, tzinfo=UTC)
KEY = sha256(b"atlas-synthetic-release-verifier").digest()


class AuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []
        self.fail_artifact = False

    async def record(self, event: AuditRecord) -> None:
        if self.fail_artifact and event.event_type.startswith("atlas.platform.bootstrap-artifact"):
            raise RuntimeError("audit unavailable")
        self.records.append(event)


class IdentityProvider:
    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        if authentication_input.authorization_scheme != "basic":
            return None
        return actor()


class ExtraInventorySource(MemoryArtifactContentSource):
    async def inventory(self, mode: AcquisitionMode) -> tuple[str, ...]:
        return (*await super().inventory(mode), "artifacts/unlisted.bin")


class EmptyArtifactInventory:
    async def observations(self, mode: AcquisitionMode) -> tuple[ArtifactObservation, ...]:
        del mode
        return ()


def actor() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.development.operator",
        display_name="Artifact Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.development",
        role_ids=("role.development.operator",),
    )


def manifest_digest() -> str:
    return sha256(canonical_manifest_payload(build_synthetic_release_manifest(KEY))).hexdigest()


def identity() -> BootstrapRunIdentity:
    return BootstrapRunIdentity(
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        plan_digest="a" * 64,
        resume_key="resume.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        configuration_digest="b" * 64,
        phase_ids=("phase.acquire", "phase.configure", "phase.trust"),
    )


def build_services(
    root: Path,
    *,
    sink: AuditSink | None = None,
    content: dict[str, bytes] | None = None,
    source: MemoryArtifactContentSource | None = None,
    artifact_inventory: ReleaseArtifactInventory | None = None,
) -> tuple[
    BootstrapStateService,
    BootstrapArtifactAcquisitionService,
    ReleasePreflightService,
    AuditSink,
]:
    resolved_sink = sink or AuditSink()
    release = build_synthetic_release_manifest(KEY)
    preflight = ReleasePreflightService(
        manifest=release,
        signature_verifier=LabHmacReleaseSignatureVerifier(KEY),
        artifact_inventory=artifact_inventory or SyntheticReleaseArtifactInventory(release),
        host_probe=SyntheticPreflightHostProbe(),
        audit_sink=resolved_sink,
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    repository = InMemoryBootstrapStateRepository()
    state = BootstrapStateService(
        repository=repository,
        environment_id="environment.test",
        site_id="site.local",
        audit_sink=resolved_sink,
        clock=lambda: NOW,
    )
    publisher = FileSystemReleaseArtifactPublisher(
        root=root,
        source=source or MemoryArtifactContentSource(content or SYNTHETIC_ARTIFACT_CONTENT),
        max_total_bytes=1024 * 1024,
    )
    acquisition = BootstrapArtifactAcquisitionService(
        repository=repository,
        preflight_service=preflight,
        publisher=publisher,
        audit_sink=resolved_sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    return state, acquisition, preflight, resolved_sink


async def claim(state: BootstrapStateService, holder: str = "session.artifact.primary") -> int:
    result = await state.claim(
        actor=actor(),
        lease_holder_id=holder,
        identity=identity(),
        lease_duration=timedelta(minutes=5),
        idempotency_key="artifact-claim-0001",
        correlation_id="correlation.artifact.claim",
    )
    return result.record.version


async def execute(
    service: BootstrapArtifactAcquisitionService,
    *,
    holder: str = "session.artifact.primary",
    expected_version: int = 1,
    idempotency_key: str = "artifact-execute-0001",
    justification: str = "Acquire verified lab release artifacts",
    preflight_state: PreflightState = PreflightState.PASSED,
) -> BootstrapMutationResult:
    run_digest = sha256(
        "/".join(
            (
                identity().organization_id,
                identity().environment_id,
                identity().site_id,
                identity().resume_key,
            )
        ).encode()
    ).hexdigest()[:24]
    return await service.execute(
        actor=actor(),
        lease_holder_id=holder,
        run_id=f"bootstrap-run.{run_digest}",
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        expected_version=expected_version,
        plan_digest=identity().plan_digest,
        resume_key=identity().resume_key,
        release_id=identity().release_id,
        manifest_digest=manifest_digest(),
        mode=AcquisitionMode.CONNECTED,
        profile=DeploymentProfile.LINUX_LAB,
        preflight_report_id="preflight.reviewed-001",
        preflight_state=preflight_state,
        warning_accepted=False,
        justification=justification,
        idempotency_key=idempotency_key,
        correlation_id="correlation.artifact.execute",
    )


@pytest.mark.asyncio
async def test_filesystem_publisher_atomically_publishes_and_reuses_verified_artifacts(
    tmp_path: Path,
) -> None:
    release = build_synthetic_release_manifest(KEY)
    publisher = FileSystemReleaseArtifactPublisher(
        root=tmp_path,
        source=MemoryArtifactContentSource(SYNTHETIC_ARTIFACT_CONTENT),
        max_total_bytes=1024 * 1024,
    )
    first = await publisher.acquire(
        manifest=release,
        manifest_digest=manifest_digest(),
        mode=AcquisitionMode.OFFLINE,
        execution_id="phase-execution.aaaaaaaaaaaaaaaaaaaaaaaa",
    )
    replay = await publisher.acquire(
        manifest=release,
        manifest_digest=manifest_digest(),
        mode=AcquisitionMode.OFFLINE,
        execution_id="phase-execution.bbbbbbbbbbbbbbbbbbbbbbbb",
    )

    assert {item.disposition for item in first.evidence} == {ArtifactDisposition.PUBLISHED}
    assert {item.disposition for item in replay.evidence} == {ArtifactDisposition.REUSED}
    release_root = tmp_path / "releases" / release.release_id / manifest_digest()
    assert (release_root / "artifacts" / "backend.oci").read_bytes() == b"atlas-backend"
    assert not any((tmp_path / ".staging").iterdir())


@pytest.mark.asyncio
async def test_publisher_rejects_extra_tampered_and_conflicting_content(tmp_path: Path) -> None:
    release = build_synthetic_release_manifest(KEY)
    extra = FileSystemReleaseArtifactPublisher(
        root=tmp_path / "extra",
        source=ExtraInventorySource(SYNTHETIC_ARTIFACT_CONTENT),
        max_total_bytes=1024 * 1024,
    )
    with pytest.raises(ArtifactAcquisitionError) as inventory_error:
        await extra.acquire(
            manifest=release,
            manifest_digest=manifest_digest(),
            mode=AcquisitionMode.MIRRORED,
            execution_id="phase-execution.cccccccccccccccccccccccc",
        )
    assert inventory_error.value.code == "bootstrap_artifact_inventory_mismatch"

    tampered_content = dict(SYNTHETIC_ARTIFACT_CONTENT)
    tampered_content["artifacts/backend.oci"] = b"atlas-tampered"
    tampered_root = tmp_path / "tampered"
    tampered = FileSystemReleaseArtifactPublisher(
        root=tampered_root,
        source=MemoryArtifactContentSource(tampered_content),
        max_total_bytes=1024 * 1024,
    )
    with pytest.raises(ArtifactAcquisitionError) as digest_error:
        await tampered.acquire(
            manifest=release,
            manifest_digest=manifest_digest(),
            mode=AcquisitionMode.CONNECTED,
            execution_id="phase-execution.dddddddddddddddddddddddd",
        )
    assert digest_error.value.code in {
        "bootstrap_artifact_size_mismatch",
        "bootstrap_artifact_digest_mismatch",
    }
    assert not (tampered_root / "releases" / release.release_id).exists()
    assert not any((tampered_root / ".staging").iterdir())

    valid_root = tmp_path / "conflict"
    valid = FileSystemReleaseArtifactPublisher(
        root=valid_root,
        source=MemoryArtifactContentSource(SYNTHETIC_ARTIFACT_CONTENT),
        max_total_bytes=1024 * 1024,
    )
    await valid.acquire(
        manifest=release,
        manifest_digest=manifest_digest(),
        mode=AcquisitionMode.CONNECTED,
        execution_id="phase-execution.eeeeeeeeeeeeeeeeeeeeeeee",
    )
    target = valid_root / "releases" / release.release_id / manifest_digest()
    (target / "artifacts" / "backend.oci").write_bytes(b"changed")
    with pytest.raises(ArtifactAcquisitionError) as conflict:
        await valid.acquire(
            manifest=release,
            manifest_digest=manifest_digest(),
            mode=AcquisitionMode.CONNECTED,
            execution_id="phase-execution.ffffffffffffffffffffffff",
        )
    assert conflict.value.code == "bootstrap_artifact_existing_conflict"


def test_publisher_rejects_symlinked_staging_boundary(tmp_path: Path) -> None:
    root = tmp_path / "root"
    target = tmp_path / "outside"
    root.mkdir()
    target.mkdir()
    try:
        os.symlink(target, root / ".staging", target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not available on this Windows host")
    publisher = FileSystemReleaseArtifactPublisher(
        root=root,
        source=MemoryArtifactContentSource(SYNTHETIC_ARTIFACT_CONTENT),
        max_total_bytes=1024 * 1024,
    )
    with pytest.raises(ArtifactAcquisitionError) as unsafe:
        asyncio.run(
            publisher.acquire(
                manifest=build_synthetic_release_manifest(KEY),
                manifest_digest=manifest_digest(),
                mode=AcquisitionMode.OFFLINE,
                execution_id="phase-execution.111111111111111111111111",
            )
        )
    assert unsafe.value.code == "bootstrap_artifact_path_unsafe"


@pytest.mark.asyncio
async def test_service_completes_checkpoint_and_exact_replay_without_rewrite(
    tmp_path: Path,
) -> None:
    state, acquisition, _, sink = build_services(tmp_path)
    assert await claim(state) == 1
    first = await execute(acquisition)
    replay = await execute(acquisition)

    assert first.record.version == 3
    assert first.record.completed_phase_ids == ("phase.acquire",)
    assert first.artifact_acquisition is not None
    assert first.artifact_acquisition.state is ArtifactAcquisitionState.COMPLETED
    assert len(first.artifact_acquisition.evidence) == 3
    assert replay.replayed is True and replay.record.version == 3
    assert all(
        item.disposition is ArtifactDisposition.PUBLISHED
        for item in first.artifact_acquisition.evidence
    )
    assert (
        len(
            [
                item
                for item in sink.records
                if item.event_type == "atlas.platform.bootstrap-artifact.execute"
            ]
        )
        >= 3
    )

    with pytest.raises(BootstrapRepositoryError) as changed_replay:
        await execute(acquisition, justification="Acquire changed reviewed release artifacts")
    assert changed_replay.value.code == "bootstrap_idempotency_conflict"

    encoded = PostgreSQLBootstrapStateRepository._record_to_json(first.record)
    decoded = PostgreSQLBootstrapStateRepository._record_from_json(encoded)
    assert decoded == first.record
    model = PostgreSQLBootstrapStateRepository._new_model(first.record)
    PostgreSQLBootstrapStateRepository._remember(
        model,
        "session.artifact.primary",
        "artifact-postgres-replay",
        "f" * 64,
        first,
    )
    durable_replay = PostgreSQLBootstrapStateRepository._replay(
        model,
        "session.artifact.primary",
        "artifact-postgres-replay",
        "f" * 64,
    )
    assert durable_replay is not None and durable_replay.artifact_acquisition is not None
    assert durable_replay.artifact_acquisition.evidence == first.artifact_acquisition.evidence
    assert "artifact_acquisition" in Base.metadata.tables["platform_bootstrap_runs"].columns


@pytest.mark.asyncio
async def test_service_failure_records_bounded_result_and_cleans_attempt(tmp_path: Path) -> None:
    tampered = dict(SYNTHETIC_ARTIFACT_CONTENT)
    tampered["artifacts/backend.oci"] = b"wrong"
    state, acquisition, _, _ = build_services(tmp_path, content=tampered)
    await claim(state)
    result = await execute(acquisition)

    assert result.record.version == 3
    assert result.record.failed_phase_id == "phase.acquire"
    assert result.artifact_acquisition is not None
    assert result.artifact_acquisition.state is ArtifactAcquisitionState.FAILED
    assert result.artifact_acquisition.result_code == "bootstrap_artifact_size_mismatch"
    assert result.artifact_acquisition.evidence == ()
    assert not any((tmp_path / ".staging").iterdir())
    assert not (tmp_path / "releases" / identity().release_id).exists()


@pytest.mark.asyncio
async def test_stale_foreign_and_failed_preflight_requests_do_not_stage(tmp_path: Path) -> None:
    state, acquisition, _, _ = build_services(tmp_path)
    await claim(state)
    with pytest.raises(BootstrapRepositoryError) as stale:
        await execute(acquisition, expected_version=2)
    assert stale.value.code == "bootstrap_stale_revision"
    with pytest.raises(BootstrapRepositoryError) as foreign:
        await execute(
            acquisition,
            holder="session.artifact.foreign",
            idempotency_key="artifact-foreign-0001",
        )
    assert foreign.value.code == "bootstrap_lease_unavailable"
    with pytest.raises(BootstrapArtifactExecutionError) as failed_preflight:
        await execute(
            acquisition,
            idempotency_key="artifact-preflight-0001",
            preflight_state=PreflightState.FAILED,
        )
    assert failed_preflight.value.code == "bootstrap_preflight_stale"
    view = await state.current(
        actor=actor(),
        lease_holder_id="session.artifact.primary",
        correlation_id="correlation.artifact.current",
    )
    assert view.record is not None and view.record.version == 1
    assert not await asyncio.to_thread((tmp_path / ".staging").exists)
    assert not await asyncio.to_thread((tmp_path / "releases").exists)


@pytest.mark.asyncio
async def test_authoritative_failed_preflight_blocks_before_attempt(tmp_path: Path) -> None:
    state, acquisition, _, _ = build_services(
        tmp_path,
        artifact_inventory=EmptyArtifactInventory(),
    )
    await claim(state)
    with pytest.raises(BootstrapArtifactExecutionError) as failure:
        await execute(
            acquisition,
            idempotency_key="artifact-authoritative-preflight",
            preflight_state=PreflightState.FAILED,
        )
    assert failure.value.code == "bootstrap_preflight_failed"
    view = await state.current(
        actor=actor(),
        lease_holder_id="session.artifact.primary",
        correlation_id="correlation.artifact.failed-preflight",
    )
    assert view.record is not None and view.record.version == 1
    assert not await asyncio.to_thread((tmp_path / ".staging").exists)


@pytest.mark.asyncio
async def test_expired_running_attempt_is_marked_interrupted_on_lease_reclaim() -> None:
    repository = InMemoryBootstrapStateRepository()
    first = await repository.claim(
        identity=identity(),
        lease_holder_id="session.artifact.original",
        lease_duration=timedelta(minutes=1),
        idempotency_key="claim-original",
        request_fingerprint="a" * 64,
        now=NOW,
    )
    running = ArtifactAcquisitionExecution(
        execution_id="phase-execution.222222222222222222222222",
        phase_id="phase.acquire",
        release_id=identity().release_id,
        manifest_digest=manifest_digest(),
        mode=AcquisitionMode.OFFLINE,
        preflight_report_id="preflight.interrupted-001",
        state=ArtifactAcquisitionState.RUNNING,
        result_code="bootstrap.artifact.running",
        started_at=NOW,
        completed_at=None,
        evidence=(),
        total_bytes=0,
    )
    begun = await repository.begin_artifact_acquisition(
        run_id=first.record.run_id,
        plan_digest=identity().plan_digest,
        resume_key=identity().resume_key,
        execution=running,
        lease_holder_id="session.artifact.original",
        expected_version=1,
        idempotency_key="attempt-original",
        request_fingerprint="b" * 64,
        now=NOW,
    )
    reclaimed = await repository.claim(
        identity=identity(),
        lease_holder_id="session.artifact.recovery",
        lease_duration=timedelta(minutes=5),
        idempotency_key="claim-recovery",
        request_fingerprint="c" * 64,
        now=NOW + timedelta(minutes=2),
    )
    assert begun.record.version == 2 and reclaimed.record.version == 3
    assert reclaimed.reclaimed_expired_lease is True
    assert reclaimed.record.failed_phase_id == "phase.acquire"
    assert reclaimed.record.artifact_acquisition is not None
    assert reclaimed.record.artifact_acquisition.state is ArtifactAcquisitionState.FAILED
    assert reclaimed.record.artifact_acquisition.result_code == "bootstrap.artifact.interrupted"


@pytest.mark.asyncio
async def test_required_audit_failure_prevents_phase_and_file_mutation(tmp_path: Path) -> None:
    sink = AuditSink()
    state, acquisition, _, _ = build_services(tmp_path, sink=sink)
    await claim(state)
    sink.fail_artifact = True
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await execute(acquisition)
    view = await state.current(
        actor=actor(),
        lease_holder_id="session.artifact.primary",
        correlation_id="correlation.artifact.audit-failed",
    )
    assert view.record is not None and view.record.version == 1
    assert not await asyncio.to_thread((tmp_path / ".staging").exists)
    assert not await asyncio.to_thread((tmp_path / "releases").exists)


@pytest.mark.asyncio
async def test_concurrent_execution_has_one_phase_owner(tmp_path: Path) -> None:
    state, acquisition, _, _ = build_services(tmp_path)
    await claim(state)
    outcomes = await asyncio.gather(
        execute(acquisition, idempotency_key="artifact-concurrent-one"),
        execute(acquisition, idempotency_key="artifact-concurrent-two"),
        return_exceptions=True,
    )
    successes = [item for item in outcomes if not isinstance(item, BaseException)]
    failures = [item for item in outcomes if isinstance(item, BootstrapRepositoryError)]
    assert len(successes) == 1 and len(failures) == 1
    assert failures[0].code in {"bootstrap_phase_in_progress", "bootstrap_stale_revision"}


def claim_payload() -> dict[str, object]:
    return {
        "schema_version": "atlas.bootstrap-claim.v1",
        "release_id": identity().release_id,
        "profile": identity().profile.value,
        "organization_id": identity().organization_id,
        "environment_id": identity().environment_id,
        "site_id": identity().site_id,
        "plan_digest": identity().plan_digest,
        "resume_key": identity().resume_key,
        "configuration_digest": identity().configuration_digest,
        "phase_ids": list(identity().phase_ids),
        "lease_minutes": 5,
    }


def test_api_requires_csrf_strict_input_and_returns_redacted_execution(
    tmp_path: Path,
) -> None:
    state, acquisition, preflight, sink = build_services(tmp_path)
    app = create_app(
        Settings(environment="test", development_identity_enabled=True),
        identity_provider=IdentityProvider(),
        audit_sink=sink,
        release_preflight_service=preflight,
        bootstrap_state_service=state,
        bootstrap_artifact_acquisition_service=acquisition,
    )
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/authentication/sessions",
            json={"username": "operator", "password": "valid-password"},
        )
        csrf = login.headers["X-CSRF-Token"]
        created = client.post(
            "/api/v1/platform/bootstrap-state/claims",
            json=claim_payload(),
            headers={"Idempotency-Key": "api-artifact-claim", "X-CSRF-Token": csrf},
        )
        preflight_response = client.get(
            "/api/v1/platform/release-preflight?mode=connected&profile=linux_lab"
        )
        preflight_data = preflight_response.json()["data"]
        payload = {
            "schema_version": "atlas.bootstrap-artifact-acquisition.v1",
            "organization_id": identity().organization_id,
            "environment_id": identity().environment_id,
            "site_id": identity().site_id,
            "expected_version": 1,
            "plan_digest": identity().plan_digest,
            "resume_key": identity().resume_key,
            "phase_id": "phase.acquire",
            "release_id": identity().release_id,
            "manifest_digest": preflight_data["manifest_digest"],
            "mode": "connected",
            "profile": "linux_lab",
            "preflight_report_id": preflight_data["report_id"],
            "preflight_state": preflight_data["state"],
            "warning_accepted": False,
            "justification": "Acquire the reviewed lab artifact set",
        }
        denied = client.post(
            f"/api/v1/platform/bootstrap-state/{created.json()['data']['run']['run_id']}/phases/acquire",
            json=payload,
            headers={"Idempotency-Key": "api-artifact-execute"},
        )
        malformed = client.post(
            f"/api/v1/platform/bootstrap-state/{created.json()['data']['run']['run_id']}/phases/acquire",
            json={**payload, "unexpected": "value"},
            headers={
                "Idempotency-Key": "api-artifact-malformed",
                "X-CSRF-Token": csrf,
            },
        )
        completed = client.post(
            f"/api/v1/platform/bootstrap-state/{created.json()['data']['run']['run_id']}/phases/acquire",
            json=payload,
            headers={
                "Idempotency-Key": "api-artifact-execute",
                "X-CSRF-Token": csrf,
            },
        )
        current = client.get("/api/v1/platform/bootstrap-state/current")

    assert login.status_code == 201 and created.status_code == 201
    assert denied.status_code == 403 and denied.json()["code"] == "csrf_validation_failed"
    assert malformed.status_code == 422
    assert completed.status_code == 200 and completed.headers["Cache-Control"] == "no-store"
    assert completed.json()["data"]["execution"]["state"] == "completed"
    assert completed.json()["data"]["run"]["version"] == 3
    assert current.json()["data"]["run"]["artifact_acquisition"]["artifact_count"] == 3
    forbidden = ("lease_holder", "password", "source", "path", "content", "session.artifact")
    assert not any(item in completed.text for item in forbidden)
    assert completed.json()["data"]["configuration_mutation_authorized"] is False
    assert completed.json()["data"]["service_deployment_authorized"] is False
    assert completed.json()["data"]["infrastructure_mutation_authorized"] is False
