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
    DATA_STATE_FILE_NAME,
    FilesystemBootstrapDataTarget,
)
from atlas.modules.platform.adapters.bootstrap_data_synthetic import SyntheticBootstrapDataCatalog
from atlas.modules.platform.adapters.bootstrap_state_memory import InMemoryBootstrapStateRepository
from atlas.modules.platform.adapters.bootstrap_state_postgres import (
    PostgreSQLBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_trust_synthetic import SyntheticBootstrapTrustSource
from atlas.modules.platform.application.bootstrap_data_initialization import (
    BootstrapDataInitializationService,
    BootstrapDataPlanService,
)
from atlas.modules.platform.application.bootstrap_data_ports import BootstrapDataError
from atlas.modules.platform.application.bootstrap_trust_provisioning import (
    BootstrapTrustPlanService,
)
from atlas.modules.platform.application.deployment_configuration import (
    DeploymentConfigurationService,
)
from atlas.modules.platform.domain.bootstrap_data_initialization import (
    BootstrapDataPlan,
    DataInitializationState,
    DataStateDisposition,
    DataTargetState,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapRunIdentity,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.bootstrap_trust_provisioning import (
    BootstrapTrustPlan,
    TrustFileDisposition,
    TrustFileEvidence,
    TrustProvisioningExecution,
    TrustProvisioningState,
)
from atlas.modules.platform.domain.deployment_configuration import (
    DeploymentConfigurationOverlay,
    DeploymentConfigurationRequest,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

NOW = datetime(2026, 8, 4, 18, 0, tzinfo=UTC)


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
        display_name="Data Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.development",
        role_ids=("role.development.operator",),
    )


def services(
    root: Path,
) -> tuple[
    AuditSink,
    DeploymentConfigurationService,
    BootstrapTrustPlanService,
    BootstrapDataPlanService,
    FilesystemBootstrapDataTarget,
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
    target = FilesystemBootstrapDataTarget(root=root, max_state_bytes=1024 * 1024)
    data = BootstrapDataPlanService(
        catalog=SyntheticBootstrapDataCatalog(),
        target=target,
        configuration_service=configuration,
        trust_plan_service=trust,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    return sink, configuration, trust, data, target


def configuration_digest(service: DeploymentConfigurationService) -> str:
    return service.prepare(
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


async def prepare_plan(
    configuration: DeploymentConfigurationService,
    trust: BootstrapTrustPlanService,
    data: BootstrapDataPlanService,
) -> tuple[str, BootstrapTrustPlan, BootstrapDataPlan]:
    digest = configuration_digest(configuration)
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
    plan = await data.prepare(
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
    return digest, trust_plan, plan


@pytest.mark.asyncio
async def test_data_plan_is_deterministic_release_bound_and_secret_free(tmp_path: Path) -> None:
    _, configuration, trust, data, _ = services(tmp_path)
    digest, trust_plan, first = await prepare_plan(configuration, trust, data)
    _, _, second = await prepare_plan(configuration, trust, data)
    assert first.data_plan_digest == second.data_plan_digest
    assert first.target_state is DataTargetState.EMPTY
    assert first.configuration_digest == digest
    assert first.trust_plan_digest == trust_plan.trust_plan_digest
    assert [item.sequence for item in first.migrations] == [1, 2, 3]
    assert all(item.reversible and not item.destructive for item in first.migrations)
    rendered = data.render(first)
    payload = json.loads(rendered)
    assert payload["schema_revision"] == "schema.atlas-bootstrap.v1"
    assert payload["owner_id"] == "owner.project-atlas"
    assert not any(
        marker in rendered.lower()
        for marker in (b"password", b"database_url", b"private key", b"token")
    )


@pytest.mark.asyncio
async def test_data_target_publishes_reuses_and_rejects_unknown_state(tmp_path: Path) -> None:
    _, configuration, trust, data, target = services(tmp_path)
    _, _, plan = await prepare_plan(configuration, trust, data)
    document = data.render(plan)
    first = await target.initialize(
        execution_id="phase-execution.data-first", plan=plan, state_document=document
    )
    assert first.evidence[0].disposition is DataStateDisposition.PUBLISHED
    assert await target.inspect(plan=plan) is DataTargetState.REUSABLE
    second = await target.initialize(
        execution_id="phase-execution.data-second", plan=plan, state_document=document
    )
    assert second.evidence[0].disposition is DataStateDisposition.REUSED
    state_file = await asyncio.to_thread(lambda: next(tmp_path.rglob(DATA_STATE_FILE_NAME)))
    await asyncio.to_thread(state_file.write_text, "unknown", encoding="utf-8")
    with pytest.raises(BootstrapDataError, match="bootstrap_data_existing_conflict"):
        await target.inspect(plan=plan)


async def completed_trust_run(
    repository: InMemoryBootstrapStateRepository,
    *,
    configuration_digest_value: str,
    trust_plan_digest: str,
) -> tuple[BootstrapRunIdentity, BootstrapRunRecord]:
    identity = BootstrapRunIdentity(
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        plan_digest="a" * 64,
        resume_key="resume.data-aaaaaaaaaaaaaaaaaaaaaaaaaa",
        configuration_digest=configuration_digest_value,
        phase_ids=(
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
        ),
    )
    claimed = await repository.claim(
        identity=identity,
        lease_holder_id="session.data.primary",
        lease_duration=timedelta(minutes=10),
        idempotency_key="data-claim-0001",
        request_fingerprint="1" * 64,
        now=NOW,
    )
    current = claimed
    for index, phase_id in enumerate(("phase.acquire", "phase.configure"), start=2):
        current = await repository.checkpoint(
            run_id=claimed.record.run_id,
            plan_digest=identity.plan_digest,
            resume_key=identity.resume_key,
            phase_id=phase_id,
            state=BootstrapCheckpointState.COMPLETED,
            safe_output_references=(f"result.synthetic.{index}",),
            lease_holder_id="session.data.primary",
            expected_version=current.record.version,
            idempotency_key=f"data-prior-{index}",
            request_fingerprint=str(index) * 64,
            now=NOW,
        )
    trust_running = TrustProvisioningExecution(
        execution_id="phase-execution.data-trust",
        phase_id="phase.trust",
        release_id=identity.release_id,
        profile=identity.profile,
        configuration_digest=configuration_digest_value,
        trust_schema_version="atlas.bootstrap-trust-plan.v1",
        trust_plan_digest=trust_plan_digest,
        state=TrustProvisioningState.RUNNING,
        result_code="bootstrap.trust.running",
        started_at=NOW,
        completed_at=None,
        anchor_count=0,
        workload_identity_count=0,
        evidence=(),
        total_bytes=0,
    )
    begun = await repository.begin_trust_provisioning(
        run_id=claimed.record.run_id,
        plan_digest=identity.plan_digest,
        resume_key=identity.resume_key,
        execution=trust_running,
        lease_holder_id="session.data.primary",
        expected_version=current.record.version,
        idempotency_key="data-trust-begin",
        request_fingerprint="4" * 64,
        now=NOW,
    )
    completed = replace(
        trust_running,
        state=TrustProvisioningState.COMPLETED,
        result_code="bootstrap.trust.completed",
        completed_at=NOW,
        anchor_count=1,
        workload_identity_count=1,
        evidence=(
            TrustFileEvidence("trust.bundle", "b" * 64, 100, TrustFileDisposition.PUBLISHED),
            TrustFileEvidence(
                "trust.workload-identities", "c" * 64, 200, TrustFileDisposition.PUBLISHED
            ),
        ),
        total_bytes=300,
    )
    finished = await repository.finish_trust_provisioning(
        run_id=claimed.record.run_id,
        execution=completed,
        lease_holder_id="session.data.primary",
        expected_version=begun.record.version,
        idempotency_key="data-trust-finish",
        request_fingerprint="5" * 64,
        now=NOW,
    )
    return identity, finished.record


async def execute_data(
    service: BootstrapDataInitializationService,
    *,
    record: BootstrapRunRecord,
    identity: BootstrapRunIdentity,
    digest: str,
    trust_plan: BootstrapTrustPlan,
    plan: BootstrapDataPlan,
) -> BootstrapMutationResult:
    return await service.execute(
        actor=actor(),
        lease_holder_id="session.data.primary",
        run_id=record.run_id,
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        expected_version=record.version,
        plan_digest=identity.plan_digest,
        resume_key=identity.resume_key,
        release_id=identity.release_id,
        profile=identity.profile,
        configuration_digest=digest,
        overlay=DeploymentConfigurationOverlay(),
        trust_plan_digest=trust_plan.trust_plan_digest,
        data_schema_version=plan.schema_version,
        data_plan_digest=plan.data_plan_digest,
        migration_artifact_digest=plan.migration_artifact_digest,
        target_id=plan.target_id,
        expected_target_state=plan.target_state,
        justification="Initialize the clean synthetic Atlas data schema",
        idempotency_key="data-execution-0001",
        correlation_id="correlation.data.execution",
    )


@pytest.mark.asyncio
async def test_data_service_completes_checkpoint_replays_and_serializes(tmp_path: Path) -> None:
    sink, configuration, trust, data, target = services(tmp_path)
    digest, trust_plan, plan = await prepare_plan(configuration, trust, data)
    repository = InMemoryBootstrapStateRepository()
    identity, record = await completed_trust_run(
        repository,
        configuration_digest_value=digest,
        trust_plan_digest=trust_plan.trust_plan_digest,
    )
    service = BootstrapDataInitializationService(
        repository=repository,
        plan_service=data,
        target=target,
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    result = await execute_data(
        service,
        record=record,
        identity=identity,
        digest=digest,
        trust_plan=trust_plan,
        plan=plan,
    )
    assert result.record.version == 7
    assert result.record.current_phase_id == "phase.services"
    assert result.data_initialization is not None
    assert result.data_initialization.state is DataInitializationState.COMPLETED
    assert result.data_initialization.migration_count == 3
    assert result.data_initialization.verified_object_count == 14
    replay = await execute_data(
        service,
        record=record,
        identity=identity,
        digest=digest,
        trust_plan=trust_plan,
        plan=plan,
    )
    assert replay.replayed is True
    encoded = PostgreSQLBootstrapStateRepository._record_to_json(result.record)
    restored = PostgreSQLBootstrapStateRepository._record_from_json(encoded)
    assert restored.data_initialization == result.data_initialization


def test_data_plan_api_is_strict_and_redacted(tmp_path: Path) -> None:
    _, configuration, trust, _, _ = services(tmp_path)
    digest = configuration_digest(configuration)
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
        bootstrap_data_root=tmp_path,
    )
    authorization = "Basic " + base64.b64encode(b"data:anything").decode()
    with TestClient(create_app(settings, identity_provider=IdentityProvider())) as client:
        response = client.post(
            "/api/v1/platform/bootstrap-data-plan/preview",
            headers={"Authorization": authorization},
            json={
                "schema_version": "atlas.bootstrap-data-plan-request.v1",
                "release_id": "release.atlas.lab-0.1.0",
                "profile": "linux_lab",
                "organization_id": "organization.development",
                "environment_id": "environment.test",
                "site_id": "site.local",
                "configuration_digest": digest,
                "overlay": {},
                "trust_plan_digest": trust_plan.trust_plan_digest,
            },
        )
        malformed = client.post(
            "/api/v1/platform/bootstrap-data-plan/preview",
            headers={"Authorization": authorization},
            json={
                "schema_version": "atlas.bootstrap-data-plan-request.v1",
                "release_id": "release.atlas.lab-0.1.0",
                "profile": "linux_lab",
                "organization_id": "organization.development",
                "environment_id": "environment.test",
                "site_id": "site.local",
                "configuration_digest": digest,
                "overlay": {},
                "trust_plan_digest": trust_plan.trust_plan_digest,
                "database_url": "postgresql://hidden",
            },
        )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["database_url_present"] is False
    assert payload["credential_material_present"] is False
    assert payload["sql_text_present"] is False
    assert "postgresql" not in response.text.casefold()
    assert malformed.status_code == 422
