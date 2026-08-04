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
from atlas.modules.platform.adapters.bootstrap_data_filesystem import (
    FilesystemBootstrapDataTarget,
)
from atlas.modules.platform.adapters.bootstrap_data_synthetic import (
    SyntheticBootstrapDataCatalog,
)
from atlas.modules.platform.adapters.bootstrap_identity_filesystem import (
    IDENTITY_STATE_FILE_NAME,
    FilesystemBootstrapIdentityTarget,
)
from atlas.modules.platform.adapters.bootstrap_identity_synthetic import (
    SyntheticBootstrapIdentityCatalog,
)
from atlas.modules.platform.adapters.bootstrap_services_filesystem import (
    FilesystemBootstrapServiceTarget,
)
from atlas.modules.platform.adapters.bootstrap_services_synthetic import (
    SyntheticBootstrapServiceCatalog,
)
from atlas.modules.platform.adapters.bootstrap_state_memory import (
    InMemoryBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_state_postgres import (
    PostgreSQLBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_trust_synthetic import (
    SyntheticBootstrapTrustSource,
)
from atlas.modules.platform.application.bootstrap_data_initialization import (
    BootstrapDataPlanService,
)
from atlas.modules.platform.application.bootstrap_identity_handoff import (
    BootstrapIdentityHandoffService,
    BootstrapIdentityPlanService,
)
from atlas.modules.platform.application.bootstrap_identity_ports import BootstrapIdentityError
from atlas.modules.platform.application.bootstrap_service_deployment import (
    BootstrapServicePlanService,
)
from atlas.modules.platform.application.bootstrap_trust_provisioning import (
    BootstrapTrustPlanService,
)
from atlas.modules.platform.application.deployment_configuration import (
    DeploymentConfigurationService,
)
from atlas.modules.platform.domain.bootstrap_data_initialization import BootstrapDataPlan
from atlas.modules.platform.domain.bootstrap_identity_handoff import (
    BootstrapIdentityPlan,
    IdentityHandoffState,
    IdentityStateDisposition,
    IdentityTargetState,
)
from atlas.modules.platform.domain.bootstrap_service_deployment import (
    BootstrapServicePlan,
    ServiceDeploymentExecution,
    ServiceDeploymentState,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapPhaseCheckpoint,
    BootstrapRunIdentity,
)
from atlas.modules.platform.domain.bootstrap_trust_provisioning import BootstrapTrustPlan
from atlas.modules.platform.domain.deployment_configuration import (
    DeploymentConfigurationOverlay,
    DeploymentConfigurationRequest,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

NOW = datetime(2026, 8, 4, 22, 0, tzinfo=UTC)


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
        display_name="Identity Operator",
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
    BootstrapIdentityPlanService,
    FilesystemBootstrapServiceTarget,
    FilesystemBootstrapIdentityTarget,
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
    service_target = FilesystemBootstrapServiceTarget(
        root=root / "services", max_state_bytes=1024 * 1024
    )
    services = BootstrapServicePlanService(
        catalog=SyntheticBootstrapServiceCatalog(),
        target=service_target,
        data_plan_service=data,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    identity_target = FilesystemBootstrapIdentityTarget(
        root=root / "identity", max_state_bytes=1024 * 1024
    )
    identity = BootstrapIdentityPlanService(
        catalog=SyntheticBootstrapIdentityCatalog(),
        target=identity_target,
        service_plan_service=services,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    return (
        sink,
        configuration,
        trust,
        data,
        services,
        identity,
        service_target,
        identity_target,
    )


async def prepare_plans(
    configuration: DeploymentConfigurationService,
    trust: BootstrapTrustPlanService,
    data: BootstrapDataPlanService,
    services: BootstrapServicePlanService,
    identity: BootstrapIdentityPlanService,
) -> tuple[str, BootstrapTrustPlan, BootstrapDataPlan, BootstrapServicePlan, BootstrapIdentityPlan]:
    overlay = DeploymentConfigurationOverlay()
    configuration_digest = configuration.prepare(
        DeploymentConfigurationRequest(
            schema_version="atlas.deployment-configuration-request.v1",
            release_id="release.atlas.lab-0.1.0",
            profile=DeploymentProfile.LINUX_LAB,
            organization_id="organization.development",
            environment_id="environment.test",
            site_id="site.local",
            overlay=overlay,
        )
    ).configuration_digest
    trust_plan = trust.prepare(
        actor=actor(),
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        configuration_digest=configuration_digest,
        overlay=overlay,
    )
    data_plan = await data.prepare(
        actor=actor(),
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        configuration_digest=configuration_digest,
        overlay=overlay,
        trust_plan_digest=trust_plan.trust_plan_digest,
    )
    service_plan = await services.prepare(
        actor=actor(),
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        configuration_digest=configuration_digest,
        overlay=overlay,
        trust_plan_digest=trust_plan.trust_plan_digest,
        data_plan_digest=data_plan.data_plan_digest,
        migration_artifact_digest=data_plan.migration_artifact_digest,
    )
    identity_plan = await identity.prepare(
        actor=actor(),
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        configuration_digest=configuration_digest,
        overlay=overlay,
        trust_plan_digest=trust_plan.trust_plan_digest,
        data_plan_digest=data_plan.data_plan_digest,
        migration_artifact_digest=data_plan.migration_artifact_digest,
        service_plan_digest=service_plan.service_plan_digest,
    )
    return configuration_digest, trust_plan, data_plan, service_plan, identity_plan


@pytest.mark.asyncio
async def test_identity_plan_is_deterministic_bounded_and_secret_free(tmp_path: Path) -> None:
    _, configuration, trust, data, services, identity, _, _ = build_services(tmp_path)
    prepared = await prepare_plans(configuration, trust, data, services, identity)
    first = prepared[-1]
    second = (await prepare_plans(configuration, trust, data, services, identity))[-1]
    assert first.identity_plan_digest == second.identity_plan_digest
    assert first.target_state is IdentityTargetState.EMPTY
    assert first.provider_protocol == "ldaps"
    assert first.credential_replacement_required is True
    assert first.recovery_seal_required is True
    assert len(first.group_mappings) == 2
    payload = json.loads(identity.render(first))
    assert payload["credential_material_present"] is False
    assert payload["directory_mutation_performed"] is False
    assert payload["provider_activation_performed"] is False
    assert "password" not in identity.render(first).decode().lower()


@pytest.mark.asyncio
async def test_identity_target_publishes_reuses_and_rejects_unknown_state(tmp_path: Path) -> None:
    _, configuration, trust, data, services, identity, _, target = build_services(tmp_path)
    plan = (await prepare_plans(configuration, trust, data, services, identity))[-1]
    document = identity.render(plan)
    first = await target.publish(
        execution_id="phase-execution.identity-first", plan=plan, state_document=document
    )
    assert first.evidence[0].disposition is IdentityStateDisposition.PUBLISHED
    assert await target.inspect(plan=plan) is IdentityTargetState.REUSABLE
    replay = await target.publish(
        execution_id="phase-execution.identity-second", plan=plan, state_document=document
    )
    assert replay.evidence[0].disposition is IdentityStateDisposition.REUSED
    state_file = await asyncio.to_thread(lambda: next(tmp_path.rglob(IDENTITY_STATE_FILE_NAME)))
    await asyncio.to_thread(state_file.write_text, "unknown", encoding="utf-8")
    with pytest.raises(BootstrapIdentityError, match="bootstrap_identity_existing_conflict"):
        await target.inspect(plan=plan)


@pytest.mark.asyncio
async def test_identity_execution_completes_replays_and_serializes(tmp_path: Path) -> None:
    (
        sink,
        configuration,
        trust,
        data,
        services,
        identity_service,
        service_target,
        identity_target,
    ) = build_services(tmp_path)
    digest, trust_plan, data_plan, service_plan, identity_plan = await prepare_plans(
        configuration, trust, data, services, identity_service
    )
    service_receipt = await service_target.deploy(
        execution_id="phase-execution.identity-seed-services",
        plan=service_plan,
        state_document=services.render(service_plan),
    )
    service_execution = ServiceDeploymentExecution(
        execution_id="phase-execution.identity-seed-services",
        phase_id="phase.services",
        release_id=service_plan.release_id,
        profile=service_plan.profile,
        configuration_digest=digest,
        trust_plan_digest=trust_plan.trust_plan_digest,
        data_plan_digest=data_plan.data_plan_digest,
        migration_artifact_digest=data_plan.migration_artifact_digest,
        service_schema_version=service_plan.schema_version,
        service_plan_digest=service_plan.service_plan_digest,
        target_id=service_plan.target_id,
        state=ServiceDeploymentState.COMPLETED,
        result_code="bootstrap.services.completed",
        started_at=NOW,
        completed_at=NOW,
        deployed_service_count=len(service_receipt.service_statuses),
        ready_service_count=len(service_receipt.service_statuses),
        passed_probe_count=len(service_receipt.service_statuses) * 3,
        service_statuses=service_receipt.service_statuses,
        evidence=service_receipt.evidence,
    )
    repository = InMemoryBootstrapStateRepository()
    run_identity = BootstrapRunIdentity(
        release_id=service_plan.release_id,
        profile=service_plan.profile,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        plan_digest="a" * 64,
        resume_key="resume.identity-aaaaaaaaaaaaaaaaaaaaaa",
        configuration_digest=digest,
        phase_ids=(
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
        ),
    )
    claimed = await repository.claim(
        identity=run_identity,
        lease_holder_id="session.identity.primary",
        lease_duration=timedelta(minutes=10),
        idempotency_key="identity-claim-0001",
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
            ("phase.acquire", "phase.configure", "phase.trust", "phase.data", "phase.services"),
            start=1,
        )
    )
    seeded = replace(
        claimed.record,
        version=11,
        checkpoints=checkpoints,
        service_deployment=service_execution,
    )
    repository._records[("organization.development", "environment.test", "site.local")] = seeded
    handoff = BootstrapIdentityHandoffService(
        repository=repository,
        plan_service=identity_service,
        target=identity_target,
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )

    async def execute() -> BootstrapMutationResult:
        return await handoff.execute(
            actor=actor(),
            lease_holder_id="session.identity.primary",
            run_id=seeded.run_id,
            organization_id=run_identity.organization_id,
            environment_id=run_identity.environment_id,
            site_id=run_identity.site_id,
            expected_version=seeded.version,
            plan_digest=run_identity.plan_digest,
            resume_key=run_identity.resume_key,
            release_id=run_identity.release_id,
            profile=run_identity.profile,
            configuration_digest=digest,
            overlay=DeploymentConfigurationOverlay(),
            trust_plan_digest=trust_plan.trust_plan_digest,
            data_plan_digest=data_plan.data_plan_digest,
            migration_artifact_digest=data_plan.migration_artifact_digest,
            service_plan_digest=service_plan.service_plan_digest,
            identity_schema_version=identity_plan.schema_version,
            identity_plan_digest=identity_plan.identity_plan_digest,
            target_id=identity_plan.target_id,
            expected_target_state=identity_plan.target_state,
            justification="Publish the reviewed synthetic identity state",
            idempotency_key="identity-execution-0001",
            correlation_id="correlation.identity.execution",
        )

    result = await execute()
    assert result.record.version == 13
    assert result.record.current_phase_id == "phase.integrations"
    assert result.identity_handoff is not None
    assert result.identity_handoff.state is IdentityHandoffState.COMPLETED
    assert result.identity_handoff.group_mapping_count == 2
    assert result.identity_handoff.validation_count == 5
    replay = await execute()
    assert replay.replayed is True
    restored = PostgreSQLBootstrapStateRepository._record_from_json(
        PostgreSQLBootstrapStateRepository._record_to_json(result.record)
    )
    assert restored.identity_handoff == result.identity_handoff
    assert all(record.idempotency_key == "identity-execution-0001" for record in sink.records[-2:])


def test_identity_plan_api_is_strict_and_redacted(tmp_path: Path) -> None:
    _, configuration, trust, data, services, identity, _, _ = build_services(tmp_path)
    digest, trust_plan, data_plan, service_plan, _ = asyncio.run(
        prepare_plans(configuration, trust, data, services, identity)
    )
    settings = Settings(
        environment="test",
        development_identity_enabled=True,
        bootstrap_data_root=tmp_path / "app-data",
        bootstrap_service_root=tmp_path / "app-services",
        bootstrap_identity_root=tmp_path / "app-identity",
    )
    authorization = "Basic " + base64.b64encode(b"identity:anything").decode()
    request = {
        "schema_version": "atlas.bootstrap-identity-plan-request.v1",
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
        "service_plan_digest": service_plan.service_plan_digest,
    }
    with TestClient(create_app(settings, identity_provider=IdentityProvider())) as client:
        response = client.post(
            "/api/v1/platform/bootstrap-identity-plan/preview",
            headers={"Authorization": authorization},
            json=request,
        )
        malformed = client.post(
            "/api/v1/platform/bootstrap-identity-plan/preview",
            headers={"Authorization": authorization},
            json={**request, "password": "must-not-be-accepted"},
        )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider_protocol"] == "ldaps"
    assert payload["credential_material_present"] is False
    assert payload["directory_mutation_authorized"] is False
    assert payload["provider_activation_authorized"] is False
    assert payload["account_mutation_authorized"] is False
    assert payload["session_or_token_mutation_authorized"] is False
    assert "password" not in json.dumps(payload).lower()
    assert malformed.status_code == 422
