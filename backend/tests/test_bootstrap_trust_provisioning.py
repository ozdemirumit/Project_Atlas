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
from atlas.modules.platform.adapters.bootstrap_state_memory import (
    InMemoryBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_state_postgres import (
    PostgreSQLBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_trust_filesystem import (
    TRUST_BUNDLE_FILE_NAME,
    WORKLOAD_CATALOG_FILE_NAME,
    FilesystemBootstrapTrustPublisher,
)
from atlas.modules.platform.adapters.bootstrap_trust_synthetic import (
    SyntheticBootstrapTrustSource,
)
from atlas.modules.platform.application.bootstrap_state import BootstrapStateService
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError
from atlas.modules.platform.application.bootstrap_trust_ports import (
    BootstrapTrustError,
    BootstrapTrustSource,
)
from atlas.modules.platform.application.bootstrap_trust_provisioning import (
    BootstrapTrustPlanService,
    BootstrapTrustProvisioningService,
)
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
    RenderedConfigurationEvidence,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapRunIdentity,
)
from atlas.modules.platform.domain.bootstrap_trust_provisioning import (
    BootstrapTrustPlan,
    BootstrapWorkloadIdentitySpec,
    TrustAnchorSpec,
    TrustFileDisposition,
    TrustProvisioningExecution,
    TrustProvisioningState,
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
        self.fail_trust = False

    async def record(self, event: AuditRecord) -> None:
        if self.fail_trust and event.event_type.startswith("atlas.platform.bootstrap-trust"):
            raise RuntimeError("trust audit unavailable")
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
        display_name="Trust Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.development",
        role_ids=("role.development.operator",),
    )


def configuration_service(sink: AuditSink) -> DeploymentConfigurationService:
    return DeploymentConfigurationService(
        release_id="release.atlas.lab-0.1.0",
        environment_id="environment.test",
        site_id="site.local",
        audit_sink=sink,
        clock=lambda: NOW,
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


def trust_plan_service(
    sink: AuditSink,
    *,
    source: BootstrapTrustSource | None = None,
) -> BootstrapTrustPlanService:
    return BootstrapTrustPlanService(
        source=source or SyntheticBootstrapTrustSource(),
        configuration_service=configuration_service(sink),
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )


def prepare_plan(
    service: BootstrapTrustPlanService,
    configuration_digest: str,
    *,
    overlay: DeploymentConfigurationOverlay | None = None,
) -> BootstrapTrustPlan:
    return service.prepare(
        actor=actor(),
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        configuration_digest=configuration_digest,
        overlay=overlay or DeploymentConfigurationOverlay(),
    )


def identity(configuration_digest: str) -> BootstrapRunIdentity:
    return BootstrapRunIdentity(
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        plan_digest="a" * 64,
        resume_key="resume.trust-aaaaaaaaaaaaaaaaaaaaaaaaa",
        configuration_digest=configuration_digest,
        phase_ids=("phase.acquire", "phase.configure", "phase.trust", "phase.data"),
    )


def build_services(
    root: Path,
    *,
    sink: AuditSink | None = None,
) -> tuple[
    BootstrapStateService,
    BootstrapTrustPlanService,
    BootstrapTrustProvisioningService,
    InMemoryBootstrapStateRepository,
    BootstrapRunIdentity,
    AuditSink,
]:
    resolved_sink = sink or AuditSink()
    deployment = configuration_service(resolved_sink)
    configuration_digest = deployment.prepare(configuration_request()).configuration_digest
    selected_identity = identity(configuration_digest)
    repository = InMemoryBootstrapStateRepository()
    state = BootstrapStateService(
        repository=repository,
        environment_id="environment.test",
        site_id="site.local",
        audit_sink=resolved_sink,
        clock=lambda: NOW,
    )
    plans = trust_plan_service(resolved_sink)
    provisioning = BootstrapTrustProvisioningService(
        repository=repository,
        plan_service=plans,
        publisher=FilesystemBootstrapTrustPublisher(root=root, max_total_bytes=1024 * 1024),
        audit_sink=resolved_sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    return state, plans, provisioning, repository, selected_identity, resolved_sink


async def claim_with_completed_configuration(
    state: BootstrapStateService,
    repository: InMemoryBootstrapStateRepository,
    selected_identity: BootstrapRunIdentity,
    *,
    holder: str = "session.trust.primary",
    lease_duration: timedelta = timedelta(minutes=5),
) -> int:
    claimed = await state.claim(
        actor=actor(),
        lease_holder_id=holder,
        identity=selected_identity,
        lease_duration=lease_duration,
        idempotency_key="trust-claim-0001",
        correlation_id="correlation.trust.claim",
    )
    artifact_running = ArtifactAcquisitionExecution(
        execution_id="phase-execution.trust-artifact",
        phase_id="phase.acquire",
        release_id=selected_identity.release_id,
        manifest_digest="b" * 64,
        mode=AcquisitionMode.OFFLINE,
        preflight_report_id="preflight.trust-001",
        state=ArtifactAcquisitionState.RUNNING,
        result_code="bootstrap.artifact.running",
        started_at=NOW,
        completed_at=None,
        evidence=(),
        total_bytes=0,
    )
    artifact_begun = await repository.begin_artifact_acquisition(
        run_id=claimed.record.run_id,
        plan_digest=selected_identity.plan_digest,
        resume_key=selected_identity.resume_key,
        execution=artifact_running,
        lease_holder_id=holder,
        expected_version=1,
        idempotency_key="trust-artifact-begin",
        request_fingerprint="1" * 64,
        now=NOW,
    )
    artifact_finished = await repository.finish_artifact_acquisition(
        run_id=claimed.record.run_id,
        execution=replace(
            artifact_running,
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
        ),
        lease_holder_id=holder,
        expected_version=artifact_begun.record.version,
        idempotency_key="trust-artifact-finish",
        request_fingerprint="2" * 64,
        now=NOW,
    )
    configuration_running = ConfigurationRenderingExecution(
        execution_id="phase-execution.trust-configuration",
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
    configuration_begun = await repository.begin_configuration_rendering(
        run_id=claimed.record.run_id,
        plan_digest=selected_identity.plan_digest,
        resume_key=selected_identity.resume_key,
        execution=configuration_running,
        lease_holder_id=holder,
        expected_version=artifact_finished.record.version,
        idempotency_key="trust-configuration-begin",
        request_fingerprint="3" * 64,
        now=NOW,
    )
    configuration_finished = await repository.finish_configuration_rendering(
        run_id=claimed.record.run_id,
        execution=replace(
            configuration_running,
            state=ConfigurationRenderingState.COMPLETED,
            result_code="bootstrap.configuration.completed",
            completed_at=NOW,
            evidence=(
                RenderedConfigurationEvidence(
                    file_id="configuration.effective",
                    sha256="d" * 64,
                    size_bytes=128,
                    disposition=ConfigurationFileDisposition.PUBLISHED,
                ),
            ),
            total_bytes=128,
        ),
        lease_holder_id=holder,
        expected_version=configuration_begun.record.version,
        idempotency_key="trust-configuration-finish",
        request_fingerprint="4" * 64,
        now=NOW,
    )
    return configuration_finished.record.version


async def execute(
    service: BootstrapTrustProvisioningService,
    plan_service: BootstrapTrustPlanService,
    selected_identity: BootstrapRunIdentity,
    *,
    holder: str = "session.trust.primary",
    expected_version: int = 5,
    trust_plan_digest: str | None = None,
    idempotency_key: str = "trust-execute-0001",
    justification: str = "Publish the approved lab trust and workload catalog",
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
    plan = prepare_plan(plan_service, selected_identity.configuration_digest)
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
        configuration_digest=selected_identity.configuration_digest,
        overlay=DeploymentConfigurationOverlay(),
        trust_schema_version="atlas.bootstrap-trust-plan.v1",
        trust_plan_digest=trust_plan_digest or plan.trust_plan_digest,
        justification=justification,
        idempotency_key=idempotency_key,
        correlation_id="correlation.trust.execute",
    )


def published_root(root: Path, plan: BootstrapTrustPlan) -> Path:
    return (
        root
        / "deployments"
        / plan.organization_id
        / plan.environment_id
        / plan.site_id
        / plan.release_id
        / "trust-plans"
        / plan.trust_plan_digest
    )


def test_trust_plan_is_deterministic_validated_and_secret_reference_only() -> None:
    sink = AuditSink()
    deployment = configuration_service(sink)
    digest = deployment.prepare(configuration_request()).configuration_digest
    service = trust_plan_service(sink)
    first = prepare_plan(service, digest)
    second = prepare_plan(service, digest)
    trust_bundle, catalog_bytes = service.render(first)
    catalog = json.loads(catalog_bytes)

    assert first.trust_plan_digest == second.trust_plan_digest
    assert (
        first.anchors[0].sha256
        == sha256(
            __import__("ssl").PEM_cert_to_DER_cert(first.anchors[0].certificate_pem)
        ).hexdigest()
    )
    assert b"BEGIN CERTIFICATE" in trust_bundle and b"PRIVATE KEY" not in trust_bundle
    assert catalog["trust_plan_digest"] == first.trust_plan_digest
    assert catalog["workload_identities"][0]["secret_reference_ids"] == [
        "secret.workload.atlas-api"
    ]
    assert "token" not in catalog_bytes.decode().casefold()
    assert catalog_bytes == service.render(second)[1]


def test_trust_plan_rejects_expired_fingerprint_and_foreign_scope() -> None:
    sink = AuditSink()
    digest = configuration_service(sink).prepare(configuration_request()).configuration_digest
    anchors, identities = SyntheticBootstrapTrustSource().load(
        profile=DeploymentProfile.LINUX_LAB,
        environment_id="environment.test",
    )

    class Source:
        def __init__(self, anchor: TrustAnchorSpec) -> None:
            self.anchor = anchor

        def load(
            self, *, profile: DeploymentProfile, environment_id: str
        ) -> tuple[tuple[TrustAnchorSpec, ...], tuple[BootstrapWorkloadIdentitySpec, ...]]:
            del profile, environment_id
            return ((self.anchor,), identities)

    expired = trust_plan_service(sink, source=Source(replace(anchors[0], not_after=NOW)))
    with pytest.raises(BootstrapTrustError) as expired_error:
        prepare_plan(expired, digest)
    assert expired_error.value.code == "bootstrap_trust_plan_invalid"

    tampered = trust_plan_service(sink, source=Source(replace(anchors[0], sha256="f" * 64)))
    with pytest.raises(BootstrapTrustError) as fingerprint_error:
        prepare_plan(tampered, digest)
    assert fingerprint_error.value.code == "bootstrap_trust_plan_invalid"

    valid = trust_plan_service(sink)
    with pytest.raises(BootstrapTrustError) as foreign:
        valid.prepare(
            actor=actor(),
            release_id="release.atlas.lab-0.1.0",
            profile=DeploymentProfile.LINUX_LAB,
            organization_id="organization.foreign",
            environment_id="environment.test",
            site_id="site.local",
            configuration_digest=digest,
            overlay=DeploymentConfigurationOverlay(),
        )
    assert foreign.value.code == "bootstrap_trust_plan_unavailable"


@pytest.mark.asyncio
async def test_filesystem_publisher_atomically_publishes_reuses_and_rejects_conflict(
    tmp_path: Path,
) -> None:
    sink = AuditSink()
    digest = configuration_service(sink).prepare(configuration_request()).configuration_digest
    service = trust_plan_service(sink)
    plan = prepare_plan(service, digest)
    trust_bundle, catalog = service.render(plan)
    publisher = FilesystemBootstrapTrustPublisher(root=tmp_path, max_total_bytes=1024 * 1024)
    first = await publisher.publish(
        execution_id="phase-execution.trust-one",
        plan=plan,
        trust_bundle=trust_bundle,
        identity_catalog=catalog,
    )
    replay = await publisher.publish(
        execution_id="phase-execution.trust-two",
        plan=plan,
        trust_bundle=trust_bundle,
        identity_catalog=catalog,
    )

    assert all(item.disposition is TrustFileDisposition.PUBLISHED for item in first.evidence)
    assert all(item.disposition is TrustFileDisposition.REUSED for item in replay.evidence)
    destination = published_root(tmp_path, plan)
    assert (destination / TRUST_BUNDLE_FILE_NAME).read_bytes() == trust_bundle
    assert (destination / WORKLOAD_CATALOG_FILE_NAME).read_bytes() == catalog
    assert not any((tmp_path / ".staging").iterdir())

    (destination / "extra.txt").write_text("unknown")
    with pytest.raises(BootstrapTrustError) as conflict:
        await publisher.publish(
            execution_id="phase-execution.trust-conflict",
            plan=plan,
            trust_bundle=trust_bundle,
            identity_catalog=catalog,
        )
    assert conflict.value.code == "bootstrap_trust_existing_conflict"


@pytest.mark.asyncio
async def test_filesystem_publisher_rejects_private_key_size_and_symlink(tmp_path: Path) -> None:
    sink = AuditSink()
    digest = configuration_service(sink).prepare(configuration_request()).configuration_digest
    service = trust_plan_service(sink)
    plan = prepare_plan(service, digest)
    trust_bundle, catalog = service.render(plan)
    publisher = FilesystemBootstrapTrustPublisher(root=tmp_path, max_total_bytes=32)
    with pytest.raises(BootstrapTrustError) as oversized:
        await publisher.publish(
            execution_id="phase-execution.trust-oversized",
            plan=plan,
            trust_bundle=trust_bundle,
            identity_catalog=catalog,
        )
    assert oversized.value.code == "bootstrap_trust_content_invalid"

    unsafe_root = tmp_path / "unsafe"
    outside = tmp_path / "outside"
    unsafe_root.mkdir()
    outside.mkdir()
    try:
        os.symlink(outside, unsafe_root / ".staging", target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not available on this Windows host")
    unsafe = FilesystemBootstrapTrustPublisher(root=unsafe_root, max_total_bytes=1024 * 1024)
    with pytest.raises(BootstrapTrustError) as symlink_error:
        await unsafe.publish(
            execution_id="phase-execution.trust-symlink",
            plan=plan,
            trust_bundle=trust_bundle,
            identity_catalog=catalog,
        )
    assert symlink_error.value.code == "bootstrap_trust_path_unsafe"


@pytest.mark.asyncio
async def test_service_completes_checkpoint_replays_and_serializes(tmp_path: Path) -> None:
    state, plans, provisioning, repository, selected_identity, sink = build_services(tmp_path)
    assert await claim_with_completed_configuration(state, repository, selected_identity) == 5
    first = await execute(provisioning, plans, selected_identity)
    replay = await execute(provisioning, plans, selected_identity)

    assert first.record.version == 7
    assert first.record.completed_phase_ids == ("phase.acquire", "phase.configure", "phase.trust")
    assert first.record.current_phase_id == "phase.data"
    assert first.trust_provisioning is not None
    assert first.trust_provisioning.state is TrustProvisioningState.COMPLETED
    assert first.trust_provisioning.anchor_count == 1
    assert first.trust_provisioning.workload_identity_count == 1
    assert replay.replayed is True and replay.record.version == 7
    with pytest.raises(BootstrapRepositoryError) as changed:
        await execute(
            provisioning,
            plans,
            selected_identity,
            justification="Publish a differently justified governed trust catalog",
        )
    assert changed.value.code == "bootstrap_idempotency_conflict"
    assert (
        len(
            [
                item
                for item in sink.records
                if item.event_type == "atlas.platform.bootstrap-trust.execute"
            ]
        )
        >= 3
    )

    encoded = PostgreSQLBootstrapStateRepository._record_to_json(first.record)
    assert PostgreSQLBootstrapStateRepository._record_from_json(encoded) == first.record
    model = PostgreSQLBootstrapStateRepository._new_model(first.record)
    PostgreSQLBootstrapStateRepository._remember(
        model,
        "session.trust.primary",
        "trust-postgres-replay",
        "f" * 64,
        first,
    )
    durable = PostgreSQLBootstrapStateRepository._replay(
        model,
        "session.trust.primary",
        "trust-postgres-replay",
        "f" * 64,
    )
    assert durable is not None and durable.trust_provisioning == first.trust_provisioning
    assert "trust_provisioning" in Base.metadata.tables["platform_bootstrap_runs"].columns


@pytest.mark.asyncio
async def test_service_rejects_stale_foreign_drift_and_missing_configuration(
    tmp_path: Path,
) -> None:
    state, plans, provisioning, repository, selected_identity, _ = build_services(tmp_path)
    await claim_with_completed_configuration(state, repository, selected_identity)
    with pytest.raises(BootstrapRepositoryError) as stale:
        await execute(provisioning, plans, selected_identity, expected_version=6)
    assert stale.value.code == "bootstrap_stale_revision"
    with pytest.raises(BootstrapRepositoryError) as foreign:
        await execute(
            provisioning,
            plans,
            selected_identity,
            holder="session.trust.foreign",
            idempotency_key="trust-foreign-0001",
        )
    assert foreign.value.code == "bootstrap_lease_unavailable"
    with pytest.raises(BootstrapTrustError) as drift:
        await execute(
            provisioning,
            plans,
            selected_identity,
            trust_plan_digest="9" * 64,
            idempotency_key="trust-drift-0001",
        )
    assert drift.value.code == "bootstrap_trust_plan_digest_mismatch"

    missing_state, missing_plans, missing_service, missing_repository, missing_identity, _ = (
        build_services(tmp_path / "missing")
    )
    claimed = await missing_state.claim(
        actor=actor(),
        lease_holder_id="session.trust.primary",
        identity=missing_identity,
        lease_duration=timedelta(minutes=5),
        idempotency_key="trust-missing-claim",
        correlation_id="correlation.trust.missing",
    )
    acquired = await missing_repository.checkpoint(
        run_id=claimed.record.run_id,
        plan_digest=missing_identity.plan_digest,
        resume_key=missing_identity.resume_key,
        phase_id="phase.acquire",
        state=BootstrapCheckpointState.COMPLETED,
        safe_output_references=("artifact.receipt.missing",),
        lease_holder_id="session.trust.primary",
        expected_version=1,
        idempotency_key="trust-missing-artifact",
        request_fingerprint="6" * 64,
        now=NOW,
    )
    configured = await missing_repository.checkpoint(
        run_id=claimed.record.run_id,
        plan_digest=missing_identity.plan_digest,
        resume_key=missing_identity.resume_key,
        phase_id="phase.configure",
        state=BootstrapCheckpointState.COMPLETED,
        safe_output_references=("result.configuration.missing",),
        lease_holder_id="session.trust.primary",
        expected_version=acquired.record.version,
        idempotency_key="trust-missing-configuration",
        request_fingerprint="7" * 64,
        now=NOW,
    )
    with pytest.raises(BootstrapTrustError) as missing:
        await execute(
            missing_service,
            missing_plans,
            missing_identity,
            expected_version=configured.record.version,
        )
    assert missing.value.code == "bootstrap_configuration_evidence_missing"


@pytest.mark.asyncio
async def test_required_audit_failure_prevents_trust_file_and_state_mutation(
    tmp_path: Path,
) -> None:
    sink = AuditSink()
    state, plans, provisioning, repository, selected_identity, _ = build_services(
        tmp_path, sink=sink
    )
    await claim_with_completed_configuration(state, repository, selected_identity)
    sink.fail_trust = True
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await execute(provisioning, plans, selected_identity)
    current = await repository.get_current(
        organization_id=selected_identity.organization_id,
        environment_id=selected_identity.environment_id,
        site_id=selected_identity.site_id,
    )
    assert current is not None and current.version == 5
    assert not (tmp_path / "deployments").exists()


@pytest.mark.asyncio
async def test_concurrent_and_interrupted_trust_execution_are_fail_closed(tmp_path: Path) -> None:
    state, plans, provisioning, repository, selected_identity, _ = build_services(tmp_path)
    await claim_with_completed_configuration(state, repository, selected_identity)
    outcomes = await asyncio.gather(
        execute(provisioning, plans, selected_identity, idempotency_key="trust-concurrent-one"),
        execute(provisioning, plans, selected_identity, idempotency_key="trust-concurrent-two"),
        return_exceptions=True,
    )
    successes = [item for item in outcomes if not isinstance(item, BaseException)]
    failures = [item for item in outcomes if isinstance(item, BootstrapRepositoryError)]
    assert len(successes) == 1 and len(failures) == 1
    assert failures[0].code in {"bootstrap_phase_in_progress", "bootstrap_stale_revision"}

    recovery_root = tmp_path / "recovery"
    recovery_state, recovery_plans, _, recovery_repository, recovery_identity, _ = build_services(
        recovery_root
    )
    await claim_with_completed_configuration(
        recovery_state,
        recovery_repository,
        recovery_identity,
        holder="session.trust.original",
        lease_duration=timedelta(minutes=1),
    )
    plan = prepare_plan(recovery_plans, recovery_identity.configuration_digest)
    running = TrustProvisioningExecution(
        execution_id="phase-execution.trust-interrupted",
        phase_id="phase.trust",
        release_id=recovery_identity.release_id,
        profile=recovery_identity.profile,
        configuration_digest=recovery_identity.configuration_digest,
        trust_schema_version=plan.schema_version,
        trust_plan_digest=plan.trust_plan_digest,
        state=TrustProvisioningState.RUNNING,
        result_code="bootstrap.trust.running",
        started_at=NOW,
        completed_at=None,
        anchor_count=0,
        workload_identity_count=0,
        evidence=(),
        total_bytes=0,
    )
    begun = await recovery_repository.begin_trust_provisioning(
        run_id=(
            await recovery_repository.get_current(
                organization_id=recovery_identity.organization_id,
                environment_id=recovery_identity.environment_id,
                site_id=recovery_identity.site_id,
            )
        ).run_id,  # type: ignore[union-attr]
        plan_digest=recovery_identity.plan_digest,
        resume_key=recovery_identity.resume_key,
        execution=running,
        lease_holder_id="session.trust.original",
        expected_version=5,
        idempotency_key="trust-interrupted-begin",
        request_fingerprint="8" * 64,
        now=NOW,
    )
    reclaimed = await recovery_repository.claim(
        identity=recovery_identity,
        lease_holder_id="session.trust.recovery",
        lease_duration=timedelta(minutes=5),
        idempotency_key="trust-recovery-claim",
        request_fingerprint="9" * 64,
        now=NOW + timedelta(minutes=2),
    )
    assert begun.record.version == 6 and reclaimed.record.version == 7
    assert reclaimed.record.failed_phase_id == "phase.trust"
    assert reclaimed.record.trust_provisioning is not None
    assert reclaimed.record.trust_provisioning.result_code == "bootstrap.trust.interrupted"


def test_api_requires_csrf_strict_input_and_returns_redacted_trust_evidence(
    tmp_path: Path,
) -> None:
    settings = Settings(
        environment="test",
        development_identity_enabled=True,
        bootstrap_artifact_root=tmp_path / "artifacts",
        bootstrap_configuration_root=tmp_path / "configurations",
        bootstrap_trust_root=tmp_path / "trust",
    )
    app = create_app(settings, identity_provider=IdentityProvider())
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/authentication/sessions",
            json={"username": "operator", "password": "valid-password"},
        )
        csrf = login.headers["X-CSRF-Token"]
        configuration_preview = client.post(
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
        configuration_digest = configuration_preview.json()["data"]["configuration_digest"]
        trust_preview = client.post(
            "/api/v1/platform/bootstrap-trust-plan/preview",
            json={
                "schema_version": "atlas.bootstrap-trust-plan-request.v1",
                "release_id": "release.atlas.lab-0.1.0",
                "profile": "linux_lab",
                "organization_id": "organization.development",
                "environment_id": "environment.test",
                "site_id": "site.local",
                "configuration_digest": configuration_digest,
                "overlay": {},
            },
            headers={"X-CSRF-Token": csrf},
        )
        trust_plan_digest = trust_preview.json()["data"]["trust_plan_digest"]
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
                "resume_key": "resume.trust-api-aaaaaaaaaaaaaaaaa",
                "configuration_digest": configuration_digest,
                "phase_ids": ["phase.acquire", "phase.configure", "phase.trust", "phase.data"],
                "lease_minutes": 5,
            },
            headers={"Idempotency-Key": "api-trust-claim", "X-CSRF-Token": csrf},
        )
        run_id = claim.json()["data"]["run"]["run_id"]
        preflight = client.get(
            "/api/v1/platform/release-preflight?mode=offline&profile=linux_lab"
        ).json()["data"]
        acquisition = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/acquire",
            json={
                "schema_version": "atlas.bootstrap-artifact-acquisition.v1",
                "organization_id": "organization.development",
                "environment_id": "environment.test",
                "site_id": "site.local",
                "expected_version": 1,
                "plan_digest": "a" * 64,
                "resume_key": "resume.trust-api-aaaaaaaaaaaaaaaaa",
                "phase_id": "phase.acquire",
                "release_id": "release.atlas.lab-0.1.0",
                "manifest_digest": preflight["manifest_digest"],
                "mode": "offline",
                "profile": "linux_lab",
                "preflight_report_id": preflight["report_id"],
                "preflight_state": preflight["state"],
                "warning_accepted": False,
                "justification": "Acquire artifacts before trust provisioning",
            },
            headers={"Idempotency-Key": "api-trust-acquire", "X-CSRF-Token": csrf},
        )
        configuration = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/configure",
            json={
                "schema_version": "atlas.bootstrap-configuration-rendering.v1",
                "organization_id": "organization.development",
                "environment_id": "environment.test",
                "site_id": "site.local",
                "expected_version": 3,
                "plan_digest": "a" * 64,
                "resume_key": "resume.trust-api-aaaaaaaaaaaaaaaaa",
                "phase_id": "phase.configure",
                "release_id": "release.atlas.lab-0.1.0",
                "profile": "linux_lab",
                "configuration_schema_version": "atlas.deployment-configuration.v1",
                "configuration_digest": configuration_digest,
                "overlay": {},
                "justification": "Render configuration before trust provisioning",
            },
            headers={"Idempotency-Key": "api-trust-configure", "X-CSRF-Token": csrf},
        )
        payload = {
            "schema_version": "atlas.bootstrap-trust-provisioning.v1",
            "organization_id": "organization.development",
            "environment_id": "environment.test",
            "site_id": "site.local",
            "expected_version": 5,
            "plan_digest": "a" * 64,
            "resume_key": "resume.trust-api-aaaaaaaaaaaaaaaaa",
            "phase_id": "phase.trust",
            "release_id": "release.atlas.lab-0.1.0",
            "profile": "linux_lab",
            "configuration_digest": configuration_digest,
            "overlay": {},
            "trust_schema_version": "atlas.bootstrap-trust-plan.v1",
            "trust_plan_digest": trust_plan_digest,
            "justification": "Publish governed public trust and workload metadata",
        }
        denied = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/trust",
            json=payload,
            headers={"Idempotency-Key": "api-trust-execute"},
        )
        malformed = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/trust",
            json={**payload, "unexpected": True},
            headers={"Idempotency-Key": "api-trust-malformed", "X-CSRF-Token": csrf},
        )
        completed = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/trust",
            json=payload,
            headers={"Idempotency-Key": "api-trust-execute", "X-CSRF-Token": csrf},
        )
        current = client.get("/api/v1/platform/bootstrap-state/current")

    assert login.status_code == 201
    assert configuration_preview.status_code == 200 and trust_preview.status_code == 200
    assert claim.status_code == 201 and acquisition.status_code == 200
    assert configuration.status_code == 200
    assert denied.status_code == 403 and denied.json()["code"] == "csrf_validation_failed"
    assert malformed.status_code == 422
    assert completed.status_code == 200 and completed.headers["Cache-Control"] == "no-store"
    data = completed.json()["data"]
    assert data["execution"]["state"] == "completed"
    assert data["run"]["version"] == 7 and data["run"]["current_phase_id"] == "phase.data"
    assert data["trust_storage_mutation_performed"] is True
    assert data["private_key_mutation_performed"] is False
    assert data["secret_value_mutation_performed"] is False
    assert data["service_deployment_authorized"] is False
    assert data["infrastructure_mutation_authorized"] is False
    assert current.json()["data"]["run"]["trust_provisioning"]["file_count"] == 2
    forbidden = (
        "valid-password",
        "lease_holder",
        "PRIVATE KEY",
        "token_digest",
        "filesystem",
    )
    assert not any(item in completed.text for item in forbidden)
