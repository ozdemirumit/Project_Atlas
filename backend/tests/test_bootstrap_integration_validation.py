from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_bootstrap_identity_handoff import (
    NOW,
    IdentityProvider,
    actor,
    build_services,
    prepare_plans,
)

from atlas.api.app import create_app
from atlas.core.config import Settings
from atlas.modules.platform.adapters.bootstrap_integrations_filesystem import (
    INTEGRATION_STATE_FILE_NAME,
    FilesystemBootstrapIntegrationTarget,
)
from atlas.modules.platform.adapters.bootstrap_integrations_synthetic import (
    SyntheticBootstrapIntegrationCatalog,
)
from atlas.modules.platform.adapters.bootstrap_state_memory import (
    InMemoryBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_state_postgres import (
    PostgreSQLBootstrapStateRepository,
)
from atlas.modules.platform.application.bootstrap_identity_handoff import (
    BootstrapIdentityPlanService,
)
from atlas.modules.platform.application.bootstrap_integration_ports import (
    BootstrapIntegrationError,
)
from atlas.modules.platform.application.bootstrap_integration_validation import (
    BootstrapIntegrationPlanService,
    BootstrapIntegrationValidationService,
)
from atlas.modules.platform.domain.bootstrap_identity_handoff import (
    IdentityHandoffExecution,
    IdentityHandoffState,
)
from atlas.modules.platform.domain.bootstrap_integration_validation import (
    IntegrationActivationState,
    IntegrationStateDisposition,
    IntegrationTargetState,
    IntegrationValidationState,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapPhaseCheckpoint,
    BootstrapRunIdentity,
)
from atlas.modules.platform.domain.deployment_configuration import (
    DeploymentConfigurationOverlay,
)


async def prepare_integration_plan(tmp_path: Path):  # type: ignore[no-untyped-def]
    sink, configuration, trust, data, services, identity, _, identity_target = build_services(
        tmp_path
    )
    digest, trust_plan, data_plan, service_plan, identity_plan = await prepare_plans(
        configuration, trust, data, services, identity
    )
    target = FilesystemBootstrapIntegrationTarget(
        root=tmp_path / "integrations", max_state_bytes=1024 * 1024
    )
    plan_service = BootstrapIntegrationPlanService(
        catalog=SyntheticBootstrapIntegrationCatalog(),
        target=target,
        identity_plan_service=identity,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    plan = await plan_service.prepare(
        actor=actor(),
        release_id=identity_plan.release_id,
        profile=identity_plan.profile,
        organization_id=identity_plan.organization_id,
        environment_id=identity_plan.environment_id,
        site_id=identity_plan.site_id,
        configuration_digest=digest,
        overlay=DeploymentConfigurationOverlay(),
        trust_plan_digest=trust_plan.trust_plan_digest,
        data_plan_digest=data_plan.data_plan_digest,
        migration_artifact_digest=data_plan.migration_artifact_digest,
        service_plan_digest=service_plan.service_plan_digest,
        identity_plan_digest=identity_plan.identity_plan_digest,
    )
    return (
        sink,
        digest,
        trust_plan,
        data_plan,
        service_plan,
        identity_plan,
        identity_target,
        target,
        plan_service,
        plan,
    )


@pytest.mark.asyncio
async def test_integration_plan_is_deterministic_bounded_and_offline(tmp_path: Path) -> None:
    prepared = await prepare_integration_plan(tmp_path)
    plan_service, first = prepared[-2:]
    second = (await prepare_integration_plan(tmp_path / "second"))[-1]
    assert first.integration_plan_digest == second.integration_plan_digest
    assert first.target_state is IntegrationTargetState.EMPTY
    assert len(first.integrations) == 4
    assert len(first.checks) == 12
    assert all(
        item.activation_state is IntegrationActivationState.INACTIVE for item in first.integrations
    )
    document = plan_service.render(first)
    payload = json.loads(document)
    assert payload["actual_model_request_performed"] is False
    assert payload["network_request_performed"] is False
    assert payload["secret_resolution_performed"] is False
    assert payload["integration_activation_performed"] is False
    lowered = document.decode().lower()
    assert "reader token" not in lowered
    assert "authorization" not in lowered
    assert "prompt" not in lowered
    assert "response" not in lowered


@pytest.mark.asyncio
async def test_integration_target_publishes_reuses_and_rejects_unknown_state(
    tmp_path: Path,
) -> None:
    prepared = await prepare_integration_plan(tmp_path)
    target, plan_service, plan = prepared[-3:]
    document = plan_service.render(plan)
    first = await target.publish(
        execution_id="phase-execution.integrations-first",
        plan=plan,
        state_document=document,
    )
    assert first.evidence[0].disposition is IntegrationStateDisposition.PUBLISHED
    assert await target.inspect(plan=plan) is IntegrationTargetState.REUSABLE
    replay = await target.publish(
        execution_id="phase-execution.integrations-second",
        plan=plan,
        state_document=document,
    )
    assert replay.evidence[0].disposition is IntegrationStateDisposition.REUSED
    state_file = await asyncio.to_thread(lambda: next(tmp_path.rglob(INTEGRATION_STATE_FILE_NAME)))
    await asyncio.to_thread(state_file.write_text, "unknown", encoding="utf-8")
    with pytest.raises(BootstrapIntegrationError, match="existing_conflict"):
        await target.inspect(plan=plan)


@pytest.mark.asyncio
async def test_integration_execution_completes_replays_and_serializes(
    tmp_path: Path,
) -> None:
    prepared = await prepare_integration_plan(tmp_path)
    (
        sink,
        digest,
        trust_plan,
        data_plan,
        service_plan,
        identity_plan,
        identity_target,
        target,
        plan_service,
        integration_plan,
    ) = prepared
    identity_receipt = await identity_target.publish(
        execution_id="phase-execution.integration-seed-identity",
        plan=identity_plan,
        state_document=BootstrapIdentityPlanService.render(identity_plan),
    )
    identity_execution = IdentityHandoffExecution(
        execution_id="phase-execution.integration-seed-identity",
        phase_id="phase.identity",
        release_id=identity_plan.release_id,
        profile=identity_plan.profile,
        configuration_digest=digest,
        trust_plan_digest=trust_plan.trust_plan_digest,
        data_plan_digest=data_plan.data_plan_digest,
        service_plan_digest=service_plan.service_plan_digest,
        identity_schema_version=identity_plan.schema_version,
        identity_plan_digest=identity_plan.identity_plan_digest,
        target_id=identity_plan.target_id,
        state=IdentityHandoffState.COMPLETED,
        result_code="bootstrap.identity.completed",
        started_at=NOW,
        completed_at=NOW,
        group_mapping_count=len(identity_plan.group_mappings),
        validation_count=5,
        credential_replacement_required=True,
        recovery_identity_verified=True,
        bootstrap_material_sealed=True,
        pilot_identity_verified=True,
        enterprise_authentication_validated=True,
        evidence=identity_receipt.evidence,
    )
    repository = InMemoryBootstrapStateRepository()
    run_identity = BootstrapRunIdentity(
        release_id=identity_plan.release_id,
        profile=identity_plan.profile,
        organization_id=identity_plan.organization_id,
        environment_id=identity_plan.environment_id,
        site_id=identity_plan.site_id,
        plan_digest="a" * 64,
        resume_key="resume.integrations-aaaaaaaaaaaaaaaa",
        configuration_digest=digest,
        phase_ids=(
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
            "phase.verify",
            "phase.handoff",
        ),
    )
    claimed = await repository.claim(
        identity=run_identity,
        lease_holder_id="session.integrations.primary",
        lease_duration=timedelta(minutes=10),
        idempotency_key="integrations-claim-0001",
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
        for index, phase_id in enumerate(run_identity.phase_ids[:6], start=1)
    )
    seeded = replace(
        claimed.record,
        version=13,
        checkpoints=checkpoints,
        identity_handoff=identity_execution,
    )
    repository._records[
        (
            run_identity.organization_id,
            run_identity.environment_id,
            run_identity.site_id,
        )
    ] = seeded
    validation = BootstrapIntegrationValidationService(
        repository=repository,
        plan_service=plan_service,
        target=target,
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )

    async def execute() -> BootstrapMutationResult:
        return await validation.execute(
            actor=actor(),
            lease_holder_id="session.integrations.primary",
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
            identity_plan_digest=identity_plan.identity_plan_digest,
            integration_schema_version=integration_plan.schema_version,
            integration_plan_digest=integration_plan.integration_plan_digest,
            target_id=integration_plan.target_id,
            expected_target_state=integration_plan.target_state,
            justification="Validate the reviewed synthetic integration state",
            idempotency_key="integration-execution-0001",
            correlation_id="correlation.integration.execution",
        )

    result = await execute()
    assert result.record.version == 15
    assert result.record.current_phase_id == "phase.verify"
    assert result.integration_validation is not None
    assert result.integration_validation.state is IntegrationValidationState.COMPLETED
    assert result.integration_validation.mandatory_pass_count == 12
    assert result.integration_validation.activation_count == 0
    assert result.integration_validation.network_request_count == 0
    assert result.integration_validation.secret_resolution_count == 0
    replay = await execute()
    assert replay.replayed is True
    restored = PostgreSQLBootstrapStateRepository._record_from_json(
        PostgreSQLBootstrapStateRepository._record_to_json(result.record)
    )
    assert restored.integration_validation == result.integration_validation
    assert all(
        record.idempotency_key == "integration-execution-0001" for record in sink.records[-2:]
    )


def test_integration_plan_api_is_strict_and_redacted(tmp_path: Path) -> None:
    prepared = asyncio.run(prepare_integration_plan(tmp_path / "plans"))
    digest, trust_plan, data_plan, service_plan, identity_plan = prepared[1:6]
    settings = Settings(
        environment="test",
        development_identity_enabled=True,
        bootstrap_data_root=tmp_path / "app-data",
        bootstrap_service_root=tmp_path / "app-services",
        bootstrap_identity_root=tmp_path / "app-identity",
        bootstrap_integration_root=tmp_path / "app-integrations",
    )
    authorization = "Basic " + base64.b64encode(b"integrations:anything").decode()
    request = {
        "schema_version": "atlas.bootstrap-integration-plan-request.v1",
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
        "identity_plan_digest": identity_plan.identity_plan_digest,
    }
    with TestClient(create_app(settings, identity_provider=IdentityProvider())) as client:
        response = client.post(
            "/api/v1/platform/bootstrap-integration-plan/preview",
            headers={"Authorization": authorization},
            json=request,
        )
        malformed = client.post(
            "/api/v1/platform/bootstrap-integration-plan/preview",
            headers={"Authorization": authorization},
            json={**request, "reader_token": "must-not-be-accepted"},
        )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload["integrations"]) == 4
    assert len(payload["checks"]) == 12
    assert payload["actual_model_request_authorized"] is False
    assert payload["network_request_authorized"] is False
    assert payload["secret_resolution_authorized"] is False
    assert payload["integration_activation_authorized"] is False
    lowered = json.dumps(payload).lower()
    assert "reader_token" not in lowered
    assert "authorization" not in lowered
    assert malformed.status_code == 422
