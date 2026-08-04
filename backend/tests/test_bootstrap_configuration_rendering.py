from __future__ import annotations

import asyncio
import json
import os
from dataclasses import replace
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
from atlas.modules.platform.adapters.bootstrap_configuration_filesystem import (
    CONFIGURATION_FILE_NAME,
    FilesystemEffectiveConfigurationPublisher,
)
from atlas.modules.platform.adapters.bootstrap_state_memory import (
    InMemoryBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_state_postgres import (
    PostgreSQLBootstrapStateRepository,
)
from atlas.modules.platform.application.bootstrap_configuration_ports import (
    ConfigurationRenderingError,
)
from atlas.modules.platform.application.bootstrap_configuration_rendering import (
    BootstrapConfigurationExecutionError,
    BootstrapConfigurationRenderingService,
)
from atlas.modules.platform.application.bootstrap_state import BootstrapStateService
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError
from atlas.modules.platform.application.deployment_configuration import (
    DeploymentConfigurationService,
)
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import (
    ArtifactAcquisitionExecution,
    ArtifactAcquisitionState,
    ArtifactDisposition,
    VerifiedArtifactEvidence,
)
from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationFileDisposition,
    ConfigurationRenderingExecution,
    ConfigurationRenderingState,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapRunIdentity,
)
from atlas.modules.platform.domain.deployment_configuration import (
    DeploymentConfigurationOverlay,
    DeploymentConfigurationRequest,
)
from atlas.modules.platform.domain.release_preflight import AcquisitionMode, DeploymentProfile

NOW = datetime(2026, 8, 4, 17, 0, tzinfo=UTC)


class AuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []
        self.fail_configuration = False

    async def record(self, event: AuditRecord) -> None:
        if self.fail_configuration and event.event_type.startswith(
            "atlas.platform.bootstrap-configuration"
        ):
            raise RuntimeError("configuration audit unavailable")
        self.records.append(event)


class IdentityProvider:
    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        if authentication_input.authorization_scheme != "basic":
            return None
        return actor()


def actor() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.development.operator",
        display_name="Configuration Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.development",
        role_ids=("role.development.operator",),
    )


def configuration_request(
    overlay: DeploymentConfigurationOverlay | None = None,
) -> DeploymentConfigurationRequest:
    return DeploymentConfigurationRequest(
        schema_version="atlas.deployment-configuration-request.v1",
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        overlay=overlay or DeploymentConfigurationOverlay(),
    )


def configuration_service(sink: AuditSink) -> DeploymentConfigurationService:
    return DeploymentConfigurationService(
        release_id="release.atlas.lab-0.1.0",
        environment_id="environment.test",
        site_id="site.local",
        audit_sink=sink,
        clock=lambda: NOW,
    )


def identity(digest: str) -> BootstrapRunIdentity:
    return BootstrapRunIdentity(
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        plan_digest="a" * 64,
        resume_key="resume.configuration-aaaaaaaaaaaaaaaaaaaa",
        configuration_digest=digest,
        phase_ids=("phase.acquire", "phase.configure", "phase.trust"),
    )


def build_services(
    root: Path,
    *,
    sink: AuditSink | None = None,
    overlay: DeploymentConfigurationOverlay | None = None,
    max_bytes: int = 1024 * 1024,
) -> tuple[
    BootstrapStateService,
    BootstrapConfigurationRenderingService,
    InMemoryBootstrapStateRepository,
    BootstrapRunIdentity,
    AuditSink,
]:
    resolved_sink = sink or AuditSink()
    deployment = configuration_service(resolved_sink)
    selected_request = configuration_request(overlay)
    selected_identity = identity(deployment.prepare(selected_request).configuration_digest)
    repository = InMemoryBootstrapStateRepository()
    state = BootstrapStateService(
        repository=repository,
        environment_id="environment.test",
        site_id="site.local",
        audit_sink=resolved_sink,
        clock=lambda: NOW,
    )
    rendering = BootstrapConfigurationRenderingService(
        repository=repository,
        configuration_service=deployment,
        publisher=FilesystemEffectiveConfigurationPublisher(root=root, max_bytes=max_bytes),
        audit_sink=resolved_sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    return state, rendering, repository, selected_identity, resolved_sink


async def claim_with_verified_artifact(
    state: BootstrapStateService,
    repository: InMemoryBootstrapStateRepository,
    selected_identity: BootstrapRunIdentity,
    *,
    holder: str = "session.configuration.primary",
    lease_duration: timedelta = timedelta(minutes=5),
) -> int:
    claimed = await state.claim(
        actor=actor(),
        lease_holder_id=holder,
        identity=selected_identity,
        lease_duration=lease_duration,
        idempotency_key="configuration-claim-0001",
        correlation_id="correlation.configuration.claim",
    )
    running = ArtifactAcquisitionExecution(
        execution_id="phase-execution.artifact-verified-001",
        phase_id="phase.acquire",
        release_id=selected_identity.release_id,
        manifest_digest="b" * 64,
        mode=AcquisitionMode.OFFLINE,
        preflight_report_id="preflight.configuration-001",
        state=ArtifactAcquisitionState.RUNNING,
        result_code="bootstrap.artifact.running",
        started_at=NOW,
        completed_at=None,
        evidence=(),
        total_bytes=0,
    )
    begun = await repository.begin_artifact_acquisition(
        run_id=claimed.record.run_id,
        plan_digest=selected_identity.plan_digest,
        resume_key=selected_identity.resume_key,
        execution=running,
        lease_holder_id=holder,
        expected_version=1,
        idempotency_key="configuration-artifact-begin",
        request_fingerprint="1" * 64,
        now=NOW,
    )
    completed = replace(
        running,
        state=ArtifactAcquisitionState.COMPLETED,
        result_code="bootstrap.artifact.completed",
        completed_at=NOW,
        evidence=(
            VerifiedArtifactEvidence(
                artifact_id="artifact.backend.image",
                sha256="c" * 64,
                size_bytes=13,
                disposition=ArtifactDisposition.PUBLISHED,
            ),
        ),
        total_bytes=13,
    )
    finished = await repository.finish_artifact_acquisition(
        run_id=claimed.record.run_id,
        execution=completed,
        lease_holder_id=holder,
        expected_version=begun.record.version,
        idempotency_key="configuration-artifact-finish",
        request_fingerprint="2" * 64,
        now=NOW,
    )
    return finished.record.version


async def execute(
    service: BootstrapConfigurationRenderingService,
    selected_identity: BootstrapRunIdentity,
    *,
    overlay: DeploymentConfigurationOverlay | None = None,
    holder: str = "session.configuration.primary",
    expected_version: int = 3,
    configuration_digest: str | None = None,
    idempotency_key: str = "configuration-execute-0001",
    justification: str = "Render the approved effective lab configuration",
) -> BootstrapMutationResult:
    run_digest = sha256(
        "/".join(
            (
                selected_identity.organization_id,
                selected_identity.environment_id,
                selected_identity.site_id,
                selected_identity.resume_key,
            )
        ).encode()
    ).hexdigest()[:24]
    return await service.execute(
        actor=actor(),
        lease_holder_id=holder,
        run_id=f"bootstrap-run.{run_digest}",
        organization_id=selected_identity.organization_id,
        environment_id=selected_identity.environment_id,
        site_id=selected_identity.site_id,
        expected_version=expected_version,
        plan_digest=selected_identity.plan_digest,
        resume_key=selected_identity.resume_key,
        release_id=selected_identity.release_id,
        profile=selected_identity.profile,
        configuration_schema_version="atlas.deployment-configuration.v1",
        configuration_digest=configuration_digest or selected_identity.configuration_digest,
        overlay=overlay or DeploymentConfigurationOverlay(),
        justification=justification,
        idempotency_key=idempotency_key,
        correlation_id="correlation.configuration.execute",
    )


def rendered_root(root: Path, selected_identity: BootstrapRunIdentity) -> Path:
    return (
        root
        / "deployments"
        / selected_identity.organization_id
        / selected_identity.environment_id
        / selected_identity.site_id
        / selected_identity.release_id
        / "configurations"
        / selected_identity.configuration_digest
    )


def test_prepared_configuration_is_deterministic_canonical_and_secret_reference_only() -> None:
    sink = AuditSink()
    service = configuration_service(sink)
    first = service.prepare(configuration_request())
    second = service.prepare(configuration_request())
    document = json.loads(first.rendered_content)

    assert first.rendered_content == second.rendered_content
    assert first.configuration_digest == second.configuration_digest
    assert document["configuration_digest"] == first.configuration_digest
    assert document["configuration"]["secret_references"] == [
        ["secret.database", "secret.database.atlas"],
        ["secret.model-reader", "secret.model.local-reader"],
    ]
    assert set(document["source_precedence"].values()) == {"release_default"}
    assert "password" not in first.rendered_content.decode().lower()


@pytest.mark.asyncio
async def test_filesystem_publisher_atomically_publishes_and_reuses_exact_content(
    tmp_path: Path,
) -> None:
    content = b'{"configuration":{"safe":true}}\n'
    publisher = FilesystemEffectiveConfigurationPublisher(root=tmp_path, max_bytes=1024)
    first = await publisher.publish(
        execution_id="phase-execution.configuration-one",
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        release_id="release.atlas.lab-0.1.0",
        configuration_digest="d" * 64,
        content=content,
    )
    replay = await publisher.publish(
        execution_id="phase-execution.configuration-two",
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        release_id="release.atlas.lab-0.1.0",
        configuration_digest="d" * 64,
        content=content,
    )

    assert first.evidence[0].disposition is ConfigurationFileDisposition.PUBLISHED
    assert replay.evidence[0].disposition is ConfigurationFileDisposition.REUSED
    target = (
        tmp_path
        / "deployments/organization.development/environment.test/site.local"
        / "release.atlas.lab-0.1.0/configurations"
        / ("d" * 64)
        / CONFIGURATION_FILE_NAME
    )
    assert target.read_bytes() == content
    assert not any((tmp_path / ".staging").iterdir())


@pytest.mark.asyncio
async def test_publisher_rejects_conflicting_extra_oversized_and_symlink_content(
    tmp_path: Path,
) -> None:
    publisher = FilesystemEffectiveConfigurationPublisher(root=tmp_path, max_bytes=64)
    kwargs = {
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "release_id": "release.atlas.lab-0.1.0",
        "configuration_digest": "e" * 64,
    }
    with pytest.raises(ConfigurationRenderingError) as oversized:
        await publisher.publish(
            execution_id="phase-execution.configuration-oversized",
            content=b"x" * 65,
            **kwargs,
        )
    assert oversized.value.code == "bootstrap_configuration_size_invalid"

    await publisher.publish(
        execution_id="phase-execution.configuration-valid",
        content=b'{"safe":true}\n',
        **kwargs,
    )
    destination = (
        tmp_path
        / "deployments/organization.development/environment.test/site.local"
        / "release.atlas.lab-0.1.0/configurations"
        / ("e" * 64)
    )
    (destination / "extra.json").write_text("{}")
    with pytest.raises(ConfigurationRenderingError) as conflict:
        await publisher.publish(
            execution_id="phase-execution.configuration-conflict",
            content=b'{"safe":true}\n',
            **kwargs,
        )
    assert conflict.value.code == "bootstrap_configuration_existing_conflict"

    symlink_root = tmp_path / "symlink"
    outside = tmp_path / "outside"
    symlink_root.mkdir()
    outside.mkdir()
    try:
        os.symlink(outside, symlink_root / ".staging", target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not available on this Windows host")
    unsafe = FilesystemEffectiveConfigurationPublisher(root=symlink_root, max_bytes=1024)
    with pytest.raises(ConfigurationRenderingError) as symlink_error:
        await unsafe.publish(
            execution_id="phase-execution.configuration-symlink",
            content=b'{"safe":true}\n',
            **kwargs,
        )
    assert symlink_error.value.code == "bootstrap_configuration_path_unsafe"


@pytest.mark.asyncio
async def test_service_completes_checkpoint_and_exact_replay_without_rewrite(
    tmp_path: Path,
) -> None:
    state, rendering, repository, selected_identity, sink = build_services(tmp_path)
    assert await claim_with_verified_artifact(state, repository, selected_identity) == 3
    first = await execute(rendering, selected_identity)
    replay = await execute(rendering, selected_identity)

    assert first.record.version == 5
    assert first.record.completed_phase_ids == ("phase.acquire", "phase.configure")
    assert first.configuration_rendering is not None
    assert first.configuration_rendering.state is ConfigurationRenderingState.COMPLETED
    assert first.configuration_rendering.evidence[0].disposition is (
        ConfigurationFileDisposition.PUBLISHED
    )
    assert replay.replayed is True and replay.record.version == 5
    assert (
        len(
            [
                item
                for item in sink.records
                if item.event_type == "atlas.platform.bootstrap-configuration.execute"
            ]
        )
        >= 3
    )
    with pytest.raises(BootstrapRepositoryError) as changed:
        await execute(
            rendering,
            selected_identity,
            justification="Render a differently justified effective lab configuration",
        )
    assert changed.value.code == "bootstrap_idempotency_conflict"

    encoded = PostgreSQLBootstrapStateRepository._record_to_json(first.record)
    assert PostgreSQLBootstrapStateRepository._record_from_json(encoded) == first.record
    model = PostgreSQLBootstrapStateRepository._new_model(first.record)
    PostgreSQLBootstrapStateRepository._remember(
        model,
        "session.configuration.primary",
        "configuration-postgres-replay",
        "f" * 64,
        first,
    )
    durable = PostgreSQLBootstrapStateRepository._replay(
        model,
        "session.configuration.primary",
        "configuration-postgres-replay",
        "f" * 64,
    )
    assert durable is not None and durable.configuration_rendering is not None
    assert durable.configuration_rendering.evidence == first.configuration_rendering.evidence
    assert "configuration_rendering" in Base.metadata.tables["platform_bootstrap_runs"].columns


@pytest.mark.asyncio
async def test_service_rejects_stale_foreign_drift_invalid_and_missing_artifact_evidence(
    tmp_path: Path,
) -> None:
    state, rendering, repository, selected_identity, _ = build_services(tmp_path)
    await claim_with_verified_artifact(state, repository, selected_identity)
    with pytest.raises(BootstrapRepositoryError) as stale:
        await execute(rendering, selected_identity, expected_version=4)
    assert stale.value.code == "bootstrap_stale_revision"
    with pytest.raises(BootstrapRepositoryError) as foreign:
        await execute(
            rendering,
            selected_identity,
            holder="session.configuration.foreign",
            idempotency_key="configuration-foreign-0001",
        )
    assert foreign.value.code == "bootstrap_lease_unavailable"
    with pytest.raises(BootstrapConfigurationExecutionError) as drift:
        await execute(
            rendering,
            selected_identity,
            configuration_digest="9" * 64,
            idempotency_key="configuration-drift-0001",
        )
    assert drift.value.code == "bootstrap_plan_mismatch"

    unsafe_overlay = DeploymentConfigurationOverlay(api_bind="0.0.0.0")
    unsafe_state, unsafe_rendering, unsafe_repository, unsafe_identity, _ = build_services(
        tmp_path / "unsafe", overlay=unsafe_overlay
    )
    await claim_with_verified_artifact(unsafe_state, unsafe_repository, unsafe_identity)
    with pytest.raises(BootstrapConfigurationExecutionError) as invalid:
        await execute(
            unsafe_rendering,
            unsafe_identity,
            overlay=unsafe_overlay,
            idempotency_key="configuration-invalid-0001",
        )
    assert invalid.value.code == "bootstrap_configuration_validation_failed"

    missing_state, missing_rendering, missing_repository, missing_identity, _ = build_services(
        tmp_path / "missing"
    )
    claimed = await missing_state.claim(
        actor=actor(),
        lease_holder_id="session.configuration.primary",
        identity=missing_identity,
        lease_duration=timedelta(minutes=5),
        idempotency_key="configuration-missing-claim",
        correlation_id="correlation.configuration.missing",
    )
    checkpointed = await missing_repository.checkpoint(
        run_id=claimed.record.run_id,
        plan_digest=missing_identity.plan_digest,
        resume_key=missing_identity.resume_key,
        phase_id="phase.acquire",
        state=BootstrapCheckpointState.COMPLETED,
        safe_output_references=("artifact.receipt.missing",),
        lease_holder_id="session.configuration.primary",
        expected_version=1,
        idempotency_key="configuration-missing-checkpoint",
        request_fingerprint="7" * 64,
        now=NOW,
    )
    assert checkpointed.record.current_phase_id == "phase.configure"
    with pytest.raises(BootstrapConfigurationExecutionError) as missing:
        await execute(missing_rendering, missing_identity, expected_version=2)
    assert missing.value.code == "bootstrap_artifact_evidence_missing"

    assert not (tmp_path / "deployments").exists()


@pytest.mark.asyncio
async def test_required_audit_failure_prevents_configuration_file_and_state_mutation(
    tmp_path: Path,
) -> None:
    sink = AuditSink()
    state, rendering, repository, selected_identity, _ = build_services(tmp_path, sink=sink)
    await claim_with_verified_artifact(state, repository, selected_identity)
    sink.fail_configuration = True
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await execute(rendering, selected_identity)
    current = await repository.get_current(
        organization_id=selected_identity.organization_id,
        environment_id=selected_identity.environment_id,
        site_id=selected_identity.site_id,
    )
    assert current is not None and current.version == 3
    assert not (tmp_path / "deployments").exists()
    assert not (tmp_path / ".staging").exists()


@pytest.mark.asyncio
async def test_concurrent_execution_has_one_configuration_phase_owner(tmp_path: Path) -> None:
    state, rendering, repository, selected_identity, _ = build_services(tmp_path)
    await claim_with_verified_artifact(state, repository, selected_identity)
    outcomes = await asyncio.gather(
        execute(rendering, selected_identity, idempotency_key="configuration-concurrent-one"),
        execute(rendering, selected_identity, idempotency_key="configuration-concurrent-two"),
        return_exceptions=True,
    )
    successes = [item for item in outcomes if not isinstance(item, BaseException)]
    failures = [item for item in outcomes if isinstance(item, BootstrapRepositoryError)]
    assert len(successes) == 1 and len(failures) == 1
    assert failures[0].code in {"bootstrap_phase_in_progress", "bootstrap_stale_revision"}


@pytest.mark.asyncio
async def test_expired_running_configuration_is_interrupted_on_lease_reclaim(
    tmp_path: Path,
) -> None:
    state, _, repository, selected_identity, _ = build_services(tmp_path)
    await claim_with_verified_artifact(
        state,
        repository,
        selected_identity,
        holder="session.configuration.original",
        lease_duration=timedelta(minutes=1),
    )
    current = await repository.get_current(
        organization_id=selected_identity.organization_id,
        environment_id=selected_identity.environment_id,
        site_id=selected_identity.site_id,
    )
    assert current is not None
    running = ConfigurationRenderingExecution(
        execution_id="phase-execution.configuration-interrupted",
        phase_id="phase.configure",
        release_id=selected_identity.release_id,
        profile=selected_identity.profile,
        configuration_schema_version="atlas.deployment-configuration.v1",
        configuration_digest=selected_identity.configuration_digest,
        state=ConfigurationRenderingState.RUNNING,
        result_code="bootstrap.configuration.running",
        started_at=NOW,
        completed_at=None,
        evidence=(),
        total_bytes=0,
    )
    begun = await repository.begin_configuration_rendering(
        run_id=current.run_id,
        plan_digest=selected_identity.plan_digest,
        resume_key=selected_identity.resume_key,
        execution=running,
        lease_holder_id="session.configuration.original",
        expected_version=3,
        idempotency_key="configuration-interrupted-begin",
        request_fingerprint="3" * 64,
        now=NOW,
    )
    reclaimed = await repository.claim(
        identity=selected_identity,
        lease_holder_id="session.configuration.recovery",
        lease_duration=timedelta(minutes=5),
        idempotency_key="configuration-recovery-claim",
        request_fingerprint="4" * 64,
        now=NOW + timedelta(minutes=2),
    )
    assert begun.record.version == 4 and reclaimed.record.version == 5
    assert reclaimed.reclaimed_expired_lease is True
    assert reclaimed.record.failed_phase_id == "phase.configure"
    assert reclaimed.record.configuration_rendering is not None
    assert reclaimed.record.configuration_rendering.state is ConfigurationRenderingState.FAILED
    assert reclaimed.record.configuration_rendering.result_code == (
        "bootstrap.configuration.interrupted"
    )


def test_api_requires_csrf_strict_input_and_returns_redacted_configuration_evidence(
    tmp_path: Path,
) -> None:
    settings = Settings(
        environment="test",
        development_identity_enabled=True,
        bootstrap_artifact_root=tmp_path / "artifacts",
        bootstrap_configuration_root=tmp_path / "configurations",
    )
    app = create_app(settings, identity_provider=IdentityProvider())
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/authentication/sessions",
            json={"username": "operator", "password": "valid-password"},
        )
        csrf = login.headers["X-CSRF-Token"]
        preview = client.post(
            "/api/v1/platform/deployment-configuration/preview",
            json={
                "schema_version": "atlas.deployment-configuration-request.v1",
                "release_id": "release.atlas.lab-0.1.0",
                "profile": "linux_lab",
                "organization_id": "organization.development",
                "environment_id": "environment.test",
                "site_id": "site.local",
                "overlay": {},
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert preview.status_code == 200, preview.text
        configuration_digest = preview.json()["data"]["configuration_digest"]
        claim = client.post(
            "/api/v1/platform/bootstrap-state/claims",
            json={
                "schema_version": "atlas.bootstrap-claim.v1",
                "release_id": "release.atlas.lab-0.1.0",
                "profile": "linux_lab",
                "organization_id": "organization.development",
                "environment_id": "environment.test",
                "site_id": "site.local",
                "plan_digest": "a" * 64,
                "resume_key": "resume.configuration-api-aaaaaaaaaaaa",
                "configuration_digest": configuration_digest,
                "phase_ids": ["phase.acquire", "phase.configure", "phase.trust"],
                "lease_minutes": 5,
            },
            headers={"Idempotency-Key": "api-configuration-claim", "X-CSRF-Token": csrf},
        )
        preflight = client.get(
            "/api/v1/platform/release-preflight?mode=offline&profile=linux_lab"
        ).json()["data"]
        run_id = claim.json()["data"]["run"]["run_id"]
        acquisition = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/acquire",
            json={
                "schema_version": "atlas.bootstrap-artifact-acquisition.v1",
                "organization_id": "organization.development",
                "environment_id": "environment.test",
                "site_id": "site.local",
                "expected_version": 1,
                "plan_digest": "a" * 64,
                "resume_key": "resume.configuration-api-aaaaaaaaaaaa",
                "phase_id": "phase.acquire",
                "release_id": "release.atlas.lab-0.1.0",
                "manifest_digest": preflight["manifest_digest"],
                "mode": "offline",
                "profile": "linux_lab",
                "preflight_report_id": preflight["report_id"],
                "preflight_state": preflight["state"],
                "warning_accepted": False,
                "justification": "Acquire artifacts before rendering configuration",
            },
            headers={"Idempotency-Key": "api-configuration-acquire", "X-CSRF-Token": csrf},
        )
        payload = {
            "schema_version": "atlas.bootstrap-configuration-rendering.v1",
            "organization_id": "organization.development",
            "environment_id": "environment.test",
            "site_id": "site.local",
            "expected_version": 3,
            "plan_digest": "a" * 64,
            "resume_key": "resume.configuration-api-aaaaaaaaaaaa",
            "phase_id": "phase.configure",
            "release_id": "release.atlas.lab-0.1.0",
            "profile": "linux_lab",
            "configuration_schema_version": "atlas.deployment-configuration.v1",
            "configuration_digest": configuration_digest,
            "overlay": {},
            "justification": "Render the approved effective API configuration",
        }
        denied = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/configure",
            json=payload,
            headers={"Idempotency-Key": "api-configuration-execute"},
        )
        malformed = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/configure",
            json={**payload, "unexpected": True},
            headers={
                "Idempotency-Key": "api-configuration-malformed",
                "X-CSRF-Token": csrf,
            },
        )
        completed = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/configure",
            json=payload,
            headers={
                "Idempotency-Key": "api-configuration-execute",
                "X-CSRF-Token": csrf,
            },
        )
        current = client.get("/api/v1/platform/bootstrap-state/current")

    assert login.status_code == 201 and preview.status_code == 200 and claim.status_code == 201
    assert acquisition.status_code == 200
    assert denied.status_code == 403 and denied.json()["code"] == "csrf_validation_failed"
    assert malformed.status_code == 422
    assert completed.status_code == 200 and completed.headers["Cache-Control"] == "no-store"
    data = completed.json()["data"]
    assert data["execution"]["state"] == "completed"
    assert data["run"]["version"] == 5
    assert data["configuration_storage_mutation_performed"] is True
    assert data["trust_mutation_authorized"] is False
    assert data["secret_mutation_authorized"] is False
    assert data["service_deployment_authorized"] is False
    assert data["infrastructure_mutation_authorized"] is False
    assert current.json()["data"]["run"]["configuration_rendering"]["file_count"] == 1
    forbidden = (
        "lease_holder",
        "valid-password",
        "path",
        "content",
        "secret.database.atlas",
    )
    assert not any(item in completed.text for item in forbidden)
