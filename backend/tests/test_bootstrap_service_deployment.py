from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.platform.adapters.bootstrap_data_filesystem import FilesystemBootstrapDataTarget
from atlas.modules.platform.adapters.bootstrap_data_synthetic import SyntheticBootstrapDataCatalog
from atlas.modules.platform.adapters.bootstrap_services_filesystem import (
    SERVICE_STATE_FILE_NAME,
    FilesystemBootstrapServiceTarget,
)
from atlas.modules.platform.adapters.bootstrap_services_synthetic import (
    SyntheticBootstrapServiceCatalog,
)
from atlas.modules.platform.adapters.bootstrap_state_memory import InMemoryBootstrapStateRepository
from atlas.modules.platform.adapters.bootstrap_state_postgres import (
    PostgreSQLBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_trust_synthetic import SyntheticBootstrapTrustSource
from atlas.modules.platform.application.bootstrap_data_initialization import (
    BootstrapDataPlanService,
)
from atlas.modules.platform.application.bootstrap_service_deployment import (
    BootstrapServiceDeploymentService,
    BootstrapServicePlanService,
)
from atlas.modules.platform.application.bootstrap_service_ports import BootstrapServiceError
from atlas.modules.platform.application.bootstrap_trust_provisioning import (
    BootstrapTrustPlanService,
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
from atlas.modules.platform.domain.bootstrap_data_initialization import (
    BackupApplicability,
    BootstrapDataPlan,
    DataInitializationExecution,
    DataInitializationState,
    DataStateDisposition,
    DataStateEvidence,
)
from atlas.modules.platform.domain.bootstrap_service_deployment import (
    BootstrapServicePlan,
    ServiceDeploymentState,
    ServiceStateDisposition,
    ServiceTargetState,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapPhaseCheckpoint,
    BootstrapRunIdentity,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.deployment_configuration import (
    DeploymentConfigurationOverlay,
    DeploymentConfigurationRequest,
)
from atlas.modules.platform.domain.release_preflight import AcquisitionMode, DeploymentProfile

NOW = datetime(2026, 8, 4, 20, 0, tzinfo=UTC)
BACKEND_DIGEST = "f010f237cc478705d8a92cab6c8988c30768af405d82630408782900e93cb75f"
FRONTEND_DIGEST = "1ed84304d7a465be45457bb43b5bb1a6dba86d1435b77cd1d168d26048536ace"


class AuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
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
        display_name="Service Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.development",
        role_ids=("role.development.operator",),
    )


def build_services(
    root: Path,
) -> tuple[
    AuditSink,
    DeploymentConfigurationService,
    BootstrapTrustPlanService,
    BootstrapDataPlanService,
    BootstrapServicePlanService,
    FilesystemBootstrapServiceTarget,
]:
    sink = AuditSink()
    configuration = DeploymentConfigurationService(
        release_id="release.atlas.lab-0.1.0",
        environment_id="environment.test",
        site_id="site.local",
        audit_sink=sink,
        clock=lambda: NOW,
    )
    trust = BootstrapTrustPlanService(
        source=SyntheticBootstrapTrustSource(),
        configuration_service=configuration,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    data = BootstrapDataPlanService(
        catalog=SyntheticBootstrapDataCatalog(),
        target=FilesystemBootstrapDataTarget(root=root / "data", max_state_bytes=1024 * 1024),
        configuration_service=configuration,
        trust_plan_service=trust,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    target = FilesystemBootstrapServiceTarget(root=root / "services", max_state_bytes=1024 * 1024)
    service = BootstrapServicePlanService(
        catalog=SyntheticBootstrapServiceCatalog(),
        target=target,
        data_plan_service=data,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    return sink, configuration, trust, data, service, target


async def prepare_plan(
    configuration: DeploymentConfigurationService,
    trust: BootstrapTrustPlanService,
    data: BootstrapDataPlanService,
    service: BootstrapServicePlanService,
) -> tuple[str, BootstrapDataPlan, BootstrapServicePlan]:
    digest = configuration.prepare(
        DeploymentConfigurationRequest(
            schema_version="atlas.deployment-configuration-request.v1",
            release_id="release.atlas.lab-0.1.0",
            profile=DeploymentProfile.LINUX_LAB,
            organization_id="organization.development",
            environment_id="environment.test",
            site_id="site.local",
            overlay=DeploymentConfigurationOverlay(),
        )
    ).configuration_digest
    trust_plan = trust.prepare(
        actor=actor(),
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        configuration_digest=digest,
        overlay=DeploymentConfigurationOverlay(),
    )
    data_plan = await data.prepare(
        actor=actor(),
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        configuration_digest=digest,
        overlay=DeploymentConfigurationOverlay(),
        trust_plan_digest=trust_plan.trust_plan_digest,
    )
    plan = await service.prepare(
        actor=actor(),
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        configuration_digest=digest,
        overlay=DeploymentConfigurationOverlay(),
        trust_plan_digest=trust_plan.trust_plan_digest,
        data_plan_digest=data_plan.data_plan_digest,
        migration_artifact_digest=data_plan.migration_artifact_digest,
    )
    return digest, data_plan, plan


@pytest.mark.asyncio
async def test_service_plan_is_ordered_bounded_and_real_runtime_safe(tmp_path: Path) -> None:
    _, configuration, trust, data, service, _ = build_services(tmp_path)
    digest, data_plan, first = await prepare_plan(configuration, trust, data, service)
    _, _, second = await prepare_plan(configuration, trust, data, service)
    assert first.service_plan_digest == second.service_plan_digest
    assert first.configuration_digest == digest
    assert first.data_plan_digest == data_plan.data_plan_digest
    assert first.target_state is ServiceTargetState.EMPTY
    assert [item.service_id for item in first.services] == [
        "service.atlas-api",
        "service.atlas-web",
    ]
    assert first.services[1].dependencies == ("service.atlas-api",)
    assert all(
        not item.run_as_root and not item.privileged and not item.arbitrary_public_egress
        for item in first.services
    )
    payload = json.loads(service.render(first))
    assert payload["real_runtime_mutation_performed"] is False
    assert all(item["runtime_state"] == "ready" for item in payload["services"])


@pytest.mark.asyncio
async def test_service_target_publishes_reuses_and_rejects_unknown_state(tmp_path: Path) -> None:
    _, configuration, trust, data, service, target = build_services(tmp_path)
    _, _, plan = await prepare_plan(configuration, trust, data, service)
    document = service.render(plan)
    first = await target.deploy(
        execution_id="phase-execution.services-first", plan=plan, state_document=document
    )
    assert first.evidence[0].disposition is ServiceStateDisposition.PUBLISHED
    assert len(first.service_statuses) == 2
    assert await target.inspect(plan=plan) is ServiceTargetState.REUSABLE
    replay = await target.deploy(
        execution_id="phase-execution.services-second", plan=plan, state_document=document
    )
    assert replay.evidence[0].disposition is ServiceStateDisposition.REUSED
    state_file = await asyncio.to_thread(lambda: next(tmp_path.rglob(SERVICE_STATE_FILE_NAME)))
    await asyncio.to_thread(state_file.write_text, "unknown", encoding="utf-8")
    with pytest.raises(BootstrapServiceError, match="bootstrap_service_existing_conflict"):
        await target.inspect(plan=plan)


async def seed_data_complete_run(
    repository: InMemoryBootstrapStateRepository,
    *,
    digest: str,
    data_plan: BootstrapDataPlan,
) -> tuple[BootstrapRunIdentity, BootstrapRunRecord]:
    identity = BootstrapRunIdentity(
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        plan_digest="a" * 64,
        resume_key="resume.services-aaaaaaaaaaaaaaaaaaaaaa",
        configuration_digest=digest,
        phase_ids=(
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
        ),
    )
    claimed = await repository.claim(
        identity=identity,
        lease_holder_id="session.services.primary",
        lease_duration=timedelta(minutes=10),
        idempotency_key="services-claim-0001",
        request_fingerprint="1" * 64,
        now=NOW,
    )
    checkpoints = tuple(
        BootstrapPhaseCheckpoint(
            phase_id=phase_id,
            state=BootstrapCheckpointState.COMPLETED,
            safe_output_references=(f"result.seed.{index}",),
            recorded_at=NOW,
        )
        for index, phase_id in enumerate(
            ("phase.acquire", "phase.configure", "phase.trust", "phase.data"), start=1
        )
    )
    acquisition = ArtifactAcquisitionExecution(
        execution_id="phase-execution.services-acquire",
        phase_id="phase.acquire",
        release_id=identity.release_id,
        manifest_digest="b" * 64,
        mode=AcquisitionMode.CONNECTED,
        preflight_report_id="preflight.services-reviewed",
        state=ArtifactAcquisitionState.COMPLETED,
        result_code="bootstrap.artifact.completed",
        started_at=NOW,
        completed_at=NOW,
        evidence=(
            VerifiedArtifactEvidence(
                "artifact.backend.image", BACKEND_DIGEST, 100, ArtifactDisposition.PUBLISHED
            ),
            VerifiedArtifactEvidence(
                "artifact.frontend.image", FRONTEND_DIGEST, 100, ArtifactDisposition.PUBLISHED
            ),
        ),
        total_bytes=200,
    )
    data_execution = DataInitializationExecution(
        execution_id="phase-execution.services-data",
        phase_id="phase.data",
        release_id=identity.release_id,
        profile=identity.profile,
        configuration_digest=digest,
        trust_plan_digest=data_plan.trust_plan_digest,
        data_schema_version=data_plan.schema_version,
        data_plan_digest=data_plan.data_plan_digest,
        migration_artifact_digest=data_plan.migration_artifact_digest,
        target_id=data_plan.target_id,
        from_revision=data_plan.current_revision,
        to_revision=data_plan.target_revision,
        state=DataInitializationState.COMPLETED,
        result_code="bootstrap.data.completed",
        started_at=NOW,
        completed_at=NOW,
        migration_count=len(data_plan.migrations),
        verified_object_count=sum(item.expected_object_count for item in data_plan.migrations),
        lock_acquired=True,
        backup_applicability=BackupApplicability.NOT_APPLICABLE_CLEAN_INSTALL,
        evidence=(
            DataStateEvidence("data.schema-state", "c" * 64, 100, DataStateDisposition.PUBLISHED),
        ),
    )
    seeded = replace(
        claimed.record,
        version=9,
        checkpoints=checkpoints,
        artifact_acquisition=acquisition,
        data_initialization=data_execution,
    )
    repository._records[(identity.organization_id, identity.environment_id, identity.site_id)] = (
        seeded
    )
    return identity, seeded


@pytest.mark.asyncio
async def test_service_execution_completes_replays_and_serializes(tmp_path: Path) -> None:
    sink, configuration, trust, data, plan_service, target = build_services(tmp_path)
    digest, data_plan, plan = await prepare_plan(configuration, trust, data, plan_service)
    repository = InMemoryBootstrapStateRepository()
    identity, record = await seed_data_complete_run(repository, digest=digest, data_plan=data_plan)
    service = BootstrapServiceDeploymentService(
        repository=repository,
        plan_service=plan_service,
        target=target,
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )

    async def execute() -> BootstrapMutationResult:
        return await service.execute(
            actor=actor(),
            lease_holder_id="session.services.primary",
            run_id=record.run_id,
            organization_id=identity.organization_id,
            environment_id=identity.environment_id,
            site_id=identity.site_id,
            expected_version=record.version,
            plan_digest=identity.plan_digest,
            resume_key=identity.resume_key,
            release_id=identity.release_id,
            profile=identity.profile,
            configuration_digest=digest,
            overlay=DeploymentConfigurationOverlay(),
            trust_plan_digest=data_plan.trust_plan_digest,
            data_plan_digest=data_plan.data_plan_digest,
            migration_artifact_digest=data_plan.migration_artifact_digest,
            service_schema_version=plan.schema_version,
            service_plan_digest=plan.service_plan_digest,
            target_id=plan.target_id,
            expected_target_state=plan.target_state,
            justification="Publish the reviewed synthetic service state",
            idempotency_key="services-execution-0001",
            correlation_id="correlation.services.execution",
        )

    result = await execute()
    assert result.record.version == 11
    assert result.record.current_phase_id == "phase.identity"
    assert result.service_deployment is not None
    assert result.service_deployment.state is ServiceDeploymentState.COMPLETED
    assert result.service_deployment.ready_service_count == 2
    assert result.service_deployment.passed_probe_count == 6
    replay = await execute()
    assert replay.replayed is True
    encoded = PostgreSQLBootstrapStateRepository._record_to_json(result.record)
    restored = PostgreSQLBootstrapStateRepository._record_from_json(encoded)
    assert restored.service_deployment == result.service_deployment


def test_service_plan_api_is_strict_and_runtime_redacted(tmp_path: Path) -> None:
    _, configuration, trust, data, service, _ = build_services(tmp_path)
    digest, data_plan, _ = asyncio.run(prepare_plan(configuration, trust, data, service))
    trust_plan = trust.prepare(
        actor=actor(),
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        configuration_digest=digest,
        overlay=DeploymentConfigurationOverlay(),
    )
    settings = Settings(
        environment="test",
        development_identity_enabled=True,
        bootstrap_data_root=tmp_path / "app-data",
        bootstrap_service_root=tmp_path / "app-services",
    )
    authorization = "Basic " + base64.b64encode(b"services:anything").decode()
    request = {
        "schema_version": "atlas.bootstrap-service-plan-request.v1",
        "release_id": "release.atlas.lab-0.1.0",
        "profile": "linux_lab",
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "configuration_digest": digest,
        "overlay": {},
        "trust_plan_digest": trust_plan.trust_plan_digest,
        "data_plan_digest": data_plan.data_plan_digest,
        "migration_artifact_digest": data_plan.migration_artifact_digest,
    }
    with TestClient(create_app(settings, identity_provider=IdentityProvider())) as client:
        response = client.post(
            "/api/v1/platform/bootstrap-service-plan/preview",
            headers={"Authorization": authorization},
            json=request,
        )
        malformed = client.post(
            "/api/v1/platform/bootstrap-service-plan/preview",
            headers={"Authorization": authorization},
            json={**request, "command": "start atlas-api"},
        )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["real_process_mutation_authorized"] is False
    assert payload["container_runtime_mutation_authorized"] is False
    assert payload["network_mutation_authorized"] is False
    assert payload["secret_mutation_authorized"] is False
    assert "command" not in response.text.casefold()
    assert malformed.status_code == 422
