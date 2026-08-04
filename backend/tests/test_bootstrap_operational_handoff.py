from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_bootstrap_identity_handoff import NOW, IdentityProvider, actor
from test_bootstrap_integration_validation import prepare_integration_plan

from atlas.api.app import create_app
from atlas.core.config import Settings
from atlas.modules.platform.adapters.bootstrap_handoff_filesystem import (
    HANDOFF_REPORT_FILE_NAME,
    FilesystemBootstrapHandoffTarget,
)
from atlas.modules.platform.adapters.bootstrap_state_memory import (
    InMemoryBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_state_postgres import (
    PostgreSQLBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_verification_filesystem import (
    FilesystemBootstrapVerificationTarget,
)
from atlas.modules.platform.application.bootstrap_end_to_end_verification import (
    BootstrapVerificationPlanService,
)
from atlas.modules.platform.application.bootstrap_handoff_ports import (
    BootstrapHandoffError,
)
from atlas.modules.platform.application.bootstrap_identity_handoff import (
    BootstrapIdentityPlanService,
)
from atlas.modules.platform.application.bootstrap_integration_validation import (
    BootstrapIntegrationPlanService,
)
from atlas.modules.platform.application.bootstrap_operational_handoff import (
    BootstrapHandoffPlanService,
    BootstrapOperationalHandoffService,
)
from atlas.modules.platform.application.bootstrap_state import BootstrapStateService
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
from atlas.modules.platform.domain.bootstrap_data_initialization import (
    DataInitializationExecution,
    DataInitializationState,
    DataStateDisposition,
    DataStateEvidence,
)
from atlas.modules.platform.domain.bootstrap_end_to_end_verification import (
    EndToEndVerificationExecution,
    VerificationExecutionState,
)
from atlas.modules.platform.domain.bootstrap_identity_handoff import (
    IdentityHandoffExecution,
    IdentityHandoffState,
)
from atlas.modules.platform.domain.bootstrap_integration_validation import (
    IntegrationValidationExecution,
    IntegrationValidationState,
)
from atlas.modules.platform.domain.bootstrap_operational_handoff import (
    HandoffCheckState,
    HandoffExecutionState,
    HandoffReportDisposition,
    HandoffTargetState,
)
from atlas.modules.platform.domain.bootstrap_service_deployment import (
    ServiceDeploymentExecution,
    ServiceDeploymentState,
    ServiceRuntimeState,
    ServiceStateDisposition,
    ServiceStateEvidence,
    ServiceStatusEvidence,
)
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapPhaseCheckpoint,
    BootstrapRunIdentity,
)
from atlas.modules.platform.domain.bootstrap_trust_provisioning import (
    TrustFileDisposition,
    TrustFileEvidence,
    TrustProvisioningExecution,
    TrustProvisioningState,
)
from atlas.modules.platform.domain.release_preflight import AcquisitionMode


async def prepared_handoff(tmp_path: Path):  # type: ignore[no-untyped-def]
    prepared = await prepare_integration_plan(tmp_path / "prior")
    (
        sink,
        digest,
        trust_plan,
        data_plan,
        service_plan,
        identity_plan,
        identity_target,
        integration_target,
        _integration_plan_service,
        integration_plan,
    ) = prepared
    identity_receipt = await identity_target.publish(
        execution_id="phase-execution.handoff-identity",
        plan=identity_plan,
        state_document=BootstrapIdentityPlanService.render(identity_plan),
    )
    integration_receipt = await integration_target.publish(
        execution_id="phase-execution.handoff-integrations",
        plan=integration_plan,
        state_document=BootstrapIntegrationPlanService.render(integration_plan),
    )
    artifact = ArtifactAcquisitionExecution(
        execution_id="phase-execution.handoff-acquire",
        phase_id="phase.acquire",
        release_id=identity_plan.release_id,
        manifest_digest="1" * 64,
        mode=AcquisitionMode.OFFLINE,
        preflight_report_id="report.handoff-preflight",
        state=ArtifactAcquisitionState.COMPLETED,
        result_code="bootstrap.acquire.completed",
        started_at=NOW,
        completed_at=NOW,
        evidence=(
            VerifiedArtifactEvidence(
                artifact_id="artifact.handoff-release",
                sha256="2" * 64,
                size_bytes=256,
                disposition=ArtifactDisposition.PUBLISHED,
            ),
        ),
        total_bytes=256,
    )
    configuration = ConfigurationRenderingExecution(
        execution_id="phase-execution.handoff-configure",
        phase_id="phase.configure",
        release_id=identity_plan.release_id,
        profile=identity_plan.profile,
        configuration_schema_version="atlas.deployment-configuration.v1",
        configuration_digest=digest,
        state=ConfigurationRenderingState.COMPLETED,
        result_code="bootstrap.configuration.completed",
        started_at=NOW,
        completed_at=NOW,
        evidence=(
            RenderedConfigurationEvidence(
                file_id="configuration.handoff-effective",
                sha256="3" * 64,
                size_bytes=256,
                disposition=ConfigurationFileDisposition.PUBLISHED,
            ),
        ),
        total_bytes=256,
    )
    trust = TrustProvisioningExecution(
        execution_id="phase-execution.handoff-trust",
        phase_id="phase.trust",
        release_id=identity_plan.release_id,
        profile=identity_plan.profile,
        configuration_digest=digest,
        trust_schema_version=trust_plan.schema_version,
        trust_plan_digest=trust_plan.trust_plan_digest,
        state=TrustProvisioningState.COMPLETED,
        result_code="bootstrap.trust.completed",
        started_at=NOW,
        completed_at=NOW,
        anchor_count=len(trust_plan.anchors),
        workload_identity_count=len(trust_plan.workload_identities),
        evidence=(
            TrustFileEvidence(
                file_id="trust.handoff-anchors",
                sha256="4" * 64,
                size_bytes=128,
                disposition=TrustFileDisposition.PUBLISHED,
            ),
            TrustFileEvidence(
                file_id="trust.handoff-identities",
                sha256="5" * 64,
                size_bytes=128,
                disposition=TrustFileDisposition.PUBLISHED,
            ),
        ),
        total_bytes=256,
    )
    data = DataInitializationExecution(
        execution_id="phase-execution.handoff-data",
        phase_id="phase.data",
        release_id=identity_plan.release_id,
        profile=identity_plan.profile,
        configuration_digest=digest,
        trust_plan_digest=trust_plan.trust_plan_digest,
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
        backup_applicability=data_plan.backup_applicability,
        evidence=(
            DataStateEvidence(
                evidence_id="data.handoff-state",
                sha256="6" * 64,
                size_bytes=256,
                disposition=DataStateDisposition.PUBLISHED,
            ),
        ),
    )
    statuses = tuple(
        ServiceStatusEvidence(
            service_id=item.service_id,
            state=ServiceRuntimeState.READY,
            startup_passed=True,
            readiness_passed=True,
            liveness_passed=True,
        )
        for item in service_plan.services
    )
    services = ServiceDeploymentExecution(
        execution_id="phase-execution.handoff-services",
        phase_id="phase.services",
        release_id=identity_plan.release_id,
        profile=identity_plan.profile,
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
        deployed_service_count=len(statuses),
        ready_service_count=len(statuses),
        passed_probe_count=len(statuses) * 3,
        service_statuses=statuses,
        evidence=(
            ServiceStateEvidence(
                evidence_id="services.handoff-state",
                sha256="7" * 64,
                size_bytes=256,
                disposition=ServiceStateDisposition.PUBLISHED,
            ),
        ),
    )
    identity_execution = IdentityHandoffExecution(
        execution_id="phase-execution.handoff-identity",
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
    integration_execution = IntegrationValidationExecution(
        execution_id="phase-execution.handoff-integrations",
        phase_id="phase.integrations",
        release_id=identity_plan.release_id,
        profile=identity_plan.profile,
        configuration_digest=digest,
        trust_plan_digest=trust_plan.trust_plan_digest,
        data_plan_digest=data_plan.data_plan_digest,
        service_plan_digest=service_plan.service_plan_digest,
        identity_plan_digest=identity_plan.identity_plan_digest,
        integration_schema_version=integration_plan.schema_version,
        integration_plan_digest=integration_plan.integration_plan_digest,
        target_id=integration_plan.target_id,
        state=IntegrationValidationState.COMPLETED,
        result_code="bootstrap.integrations.completed",
        started_at=NOW,
        completed_at=NOW,
        model_check_count=8,
        integration_check_count=4,
        mandatory_pass_count=12,
        activation_count=0,
        network_request_count=0,
        secret_resolution_count=0,
        checks=integration_receipt.checks,
        evidence=integration_receipt.evidence,
    )
    repository = InMemoryBootstrapStateRepository()
    run_identity = BootstrapRunIdentity(
        release_id=identity_plan.release_id,
        profile=identity_plan.profile,
        organization_id=identity_plan.organization_id,
        environment_id=identity_plan.environment_id,
        site_id=identity_plan.site_id,
        plan_digest="a" * 64,
        resume_key="resume.handoff-aaaaaaaaaaaa",
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
        lease_holder_id="session.handoff.primary",
        lease_duration=timedelta(minutes=10),
        idempotency_key="handoff-claim-0001",
        request_fingerprint="8" * 64,
        now=NOW,
    )
    checkpoints = tuple(
        BootstrapPhaseCheckpoint(
            phase_id=phase_id,
            state=BootstrapCheckpointState.COMPLETED,
            safe_output_references=(f"result.seed.{index}",),
            recorded_at=NOW,
        )
        for index, phase_id in enumerate(run_identity.phase_ids[:7], start=1)
    )
    seeded = replace(
        claimed.record,
        version=15,
        checkpoints=checkpoints,
        artifact_acquisition=artifact,
        configuration_rendering=configuration,
        trust_provisioning=trust,
        data_initialization=data,
        service_deployment=services,
        identity_handoff=identity_execution,
        integration_validation=integration_execution,
    )
    repository._records[
        (run_identity.organization_id, run_identity.environment_id, run_identity.site_id)
    ] = seeded
    verification_target = FilesystemBootstrapVerificationTarget(
        root=tmp_path / "verification", max_report_bytes=1024 * 1024
    )
    verification_service = BootstrapVerificationPlanService(
        repository=repository,
        target=verification_target,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    verification_plan = await verification_service.prepare(
        actor=actor(),
        release_id=run_identity.release_id,
        profile=run_identity.profile,
        organization_id=run_identity.organization_id,
        environment_id=run_identity.environment_id,
        site_id=run_identity.site_id,
        source_run_id=seeded.run_id,
        source_run_version=seeded.version,
        configuration_digest=digest,
        trust_plan_digest=trust_plan.trust_plan_digest,
        data_plan_digest=data_plan.data_plan_digest,
        service_plan_digest=service_plan.service_plan_digest,
        identity_plan_digest=identity_plan.identity_plan_digest,
        integration_plan_digest=integration_plan.integration_plan_digest,
    )
    verification_receipt = await verification_target.publish(
        execution_id="phase-execution.handoff-verification",
        plan=verification_plan,
        report=verification_service.render(verification_plan),
    )
    verification_execution = EndToEndVerificationExecution(
        execution_id="phase-execution.handoff-verification",
        phase_id="phase.verify",
        release_id=run_identity.release_id,
        profile=run_identity.profile,
        configuration_digest=digest,
        trust_plan_digest=trust_plan.trust_plan_digest,
        data_plan_digest=data_plan.data_plan_digest,
        service_plan_digest=service_plan.service_plan_digest,
        identity_plan_digest=identity_plan.identity_plan_digest,
        integration_plan_digest=integration_plan.integration_plan_digest,
        verification_schema_version=verification_plan.schema_version,
        suite_version=verification_plan.suite_version,
        verification_plan_digest=verification_plan.verification_plan_digest,
        target_id=verification_plan.target_id,
        state=VerificationExecutionState.COMPLETED,
        result_code="bootstrap.verification.completed",
        started_at=NOW,
        completed_at=NOW,
        passed_count=12,
        failed_count=0,
        skipped_count=0,
        not_applicable_count=3,
        mandatory_pass_count=12,
        unresolved_mandatory_count=0,
        external_operation_count=0,
        checks=verification_receipt.checks,
        evidence=verification_receipt.evidence,
    )
    seeded = replace(
        seeded,
        version=17,
        checkpoints=(
            *checkpoints,
            BootstrapPhaseCheckpoint(
                phase_id="phase.verify",
                state=BootstrapCheckpointState.COMPLETED,
                safe_output_references=(
                    f"result.verification.{verification_plan.verification_plan_digest[:32]}",
                ),
                recorded_at=NOW,
            ),
        ),
        end_to_end_verification=verification_execution,
    )
    repository._records[
        (run_identity.organization_id, run_identity.environment_id, run_identity.site_id)
    ] = seeded
    target = FilesystemBootstrapHandoffTarget(
        root=tmp_path / "handoff", max_report_bytes=1024 * 1024
    )
    plan_service = BootstrapHandoffPlanService(
        repository=repository,
        target=target,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    inputs = {
        "actor": actor(),
        "release_id": run_identity.release_id,
        "profile": run_identity.profile,
        "organization_id": run_identity.organization_id,
        "environment_id": run_identity.environment_id,
        "site_id": run_identity.site_id,
        "source_run_id": seeded.run_id,
        "source_run_version": seeded.version,
        "configuration_digest": digest,
        "trust_plan_digest": trust_plan.trust_plan_digest,
        "data_plan_digest": data_plan.data_plan_digest,
        "service_plan_digest": service_plan.service_plan_digest,
        "identity_plan_digest": identity_plan.identity_plan_digest,
        "integration_plan_digest": integration_plan.integration_plan_digest,
        "verification_plan_digest": verification_plan.verification_plan_digest,
        "verification_report_digest": verification_receipt.evidence[0].sha256,
    }
    return sink, repository, seeded, target, plan_service, inputs


@pytest.mark.asyncio
async def test_handoff_plan_is_bounded_deterministic_and_offline(tmp_path: Path) -> None:
    _, _, _, _, service, inputs = await prepared_handoff(tmp_path)
    first = await service.prepare(**inputs)
    second = await service.prepare(**inputs)
    assert first.handoff_plan_digest == second.handoff_plan_digest
    assert first.target_state is HandoffTargetState.EMPTY
    assert len(first.checks) == 15
    assert sum(item.state is HandoffCheckState.PASSED for item in first.checks) == 12
    assert sum(item.state is HandoffCheckState.NOT_APPLICABLE for item in first.checks) == 3
    assert len(first.source_evidence_digest) == 64
    assert len(first.known_limitation_ids) == 7
    assert len(first.pending_action_ids) == 7
    assert len(first.missing_production_evidence_ids) == 7
    assert first.readiness_claims.production_ready is False
    report = service.render(first)
    payload = json.loads(report)
    assert payload["summary"] == {
        "failed": 0,
        "mandatory_passed": 12,
        "not_applicable": 3,
        "passed": 12,
        "skipped": 0,
        "unresolved_mandatory": 0,
    }
    assert all(value is False for key, value in payload.items() if key.endswith("_performed"))
    assert payload["source_evidence_digest"] == first.source_evidence_digest
    assert payload["readiness"]["classification"] == ("developer_linux_lab_bootstrap_complete")
    assert all(value is False for value in payload["readiness"]["claims"].values())
    lowered = report.decode().lower()
    assert "reader token" not in lowered
    assert "authorization:" not in lowered
    assert "bearer " not in lowered
    assert "password" not in lowered
    assert "prompt" not in lowered


@pytest.mark.asyncio
async def test_handoff_plan_rejects_changed_verification_evidence(tmp_path: Path) -> None:
    _, _, _, _, service, inputs = await prepared_handoff(tmp_path)
    with pytest.raises(BootstrapHandoffError, match="evidence_missing"):
        await service.prepare(**{**inputs, "verification_report_digest": "0" * 64})


@pytest.mark.asyncio
async def test_handoff_target_publishes_reuses_and_rejects_conflict(tmp_path: Path) -> None:
    _, _, _, target, service, inputs = await prepared_handoff(tmp_path)
    plan = await service.prepare(**inputs)
    report = service.render(plan)
    first = await target.publish(
        execution_id="phase-execution.handoff-first", plan=plan, report=report
    )
    assert first.evidence[0].disposition is HandoffReportDisposition.PUBLISHED
    reusable = await service.prepare(**inputs)
    assert reusable.target_state is HandoffTargetState.REUSABLE
    replay = await target.publish(
        execution_id="phase-execution.handoff-second", plan=reusable, report=report
    )
    assert replay.evidence[0].disposition is HandoffReportDisposition.REUSED
    state_file = await asyncio.to_thread(lambda: next(tmp_path.rglob(HANDOFF_REPORT_FILE_NAME)))
    await asyncio.to_thread(state_file.write_text, "unknown", encoding="utf-8")
    with pytest.raises(BootstrapHandoffError, match="existing_conflict"):
        await service.prepare(**inputs)


@pytest.mark.asyncio
async def test_handoff_execution_completes_replays_and_serializes(tmp_path: Path) -> None:
    sink, repository, seeded, target, plan_service, inputs = await prepared_handoff(tmp_path)
    plan = await plan_service.prepare(**inputs)
    service = BootstrapOperationalHandoffService(
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
            lease_holder_id="session.handoff.primary",
            run_id=seeded.run_id,
            organization_id=seeded.identity.organization_id,
            environment_id=seeded.identity.environment_id,
            site_id=seeded.identity.site_id,
            expected_version=seeded.version,
            plan_digest=seeded.identity.plan_digest,
            resume_key=seeded.identity.resume_key,
            release_id=seeded.identity.release_id,
            profile=seeded.identity.profile,
            configuration_digest=plan.configuration_digest,
            trust_plan_digest=plan.trust_plan_digest,
            data_plan_digest=plan.data_plan_digest,
            service_plan_digest=plan.service_plan_digest,
            identity_plan_digest=plan.identity_plan_digest,
            integration_plan_digest=plan.integration_plan_digest,
            verification_plan_digest=plan.verification_plan_digest,
            verification_report_digest=plan.verification_report_digest,
            source_evidence_digest=plan.source_evidence_digest,
            handoff_schema_version=plan.schema_version,
            suite_version=plan.suite_version,
            handoff_plan_digest=plan.handoff_plan_digest,
            target_id=plan.target_id,
            expected_target_state=plan.target_state,
            justification="Publish the reviewed developer and lab handoff evidence",
            idempotency_key="handoff-execution-0001",
            correlation_id="correlation.handoff.execution",
        )

    result = await execute()
    assert result.record.version == 19
    assert result.record.current_phase_id is None
    assert result.record.state.value == "completed"
    assert result.operational_handoff is not None
    assert result.operational_handoff.state is HandoffExecutionState.COMPLETED
    assert result.operational_handoff.passed_count == 12
    assert result.operational_handoff.not_applicable_count == 3
    assert result.operational_handoff.known_limitation_count == 7
    assert result.operational_handoff.missing_production_evidence_count == 7
    assert result.operational_handoff.readiness_claims.production_ready is False
    assert result.operational_handoff.external_operation_count == 0
    replay = await execute()
    assert replay.replayed is True
    restored = PostgreSQLBootstrapStateRepository._record_from_json(
        PostgreSQLBootstrapStateRepository._record_to_json(result.record)
    )
    assert restored.operational_handoff == result.operational_handoff
    assert all(record.idempotency_key == "handoff-execution-0001" for record in sink.records[-2:])


def test_handoff_plan_api_is_strict_and_redacted(tmp_path: Path) -> None:
    sink, repository, seeded, target, plan_service, inputs = asyncio.run(prepared_handoff(tmp_path))
    execution_service = BootstrapOperationalHandoffService(
        repository=repository,
        plan_service=plan_service,
        target=target,
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    state_service = BootstrapStateService(
        repository=repository,
        environment_id="environment.test",
        site_id="site.local",
        audit_sink=sink,
        clock=lambda: NOW,
    )
    settings = Settings(
        environment="test",
        development_identity_enabled=True,
        bootstrap_handoff_root=tmp_path / "app-handoff",
    )
    request = {
        "schema_version": "atlas.bootstrap-handoff-plan-request.v1",
        "release_id": seeded.identity.release_id,
        "profile": seeded.identity.profile.value,
        "organization_id": seeded.identity.organization_id,
        "environment_id": seeded.identity.environment_id,
        "site_id": seeded.identity.site_id,
        "source_run_id": seeded.run_id,
        "source_run_version": seeded.version,
        "configuration_digest": inputs["configuration_digest"],
        "trust_plan_digest": inputs["trust_plan_digest"],
        "data_plan_digest": inputs["data_plan_digest"],
        "service_plan_digest": inputs["service_plan_digest"],
        "identity_plan_digest": inputs["identity_plan_digest"],
        "integration_plan_digest": inputs["integration_plan_digest"],
        "verification_plan_digest": inputs["verification_plan_digest"],
        "verification_report_digest": inputs["verification_report_digest"],
    }
    authorization = "Basic " + base64.b64encode(b"handoff:anything").decode()
    with TestClient(
        create_app(
            settings,
            identity_provider=IdentityProvider(),
            bootstrap_state_service=state_service,
            bootstrap_handoff_plan_service=plan_service,
            bootstrap_operational_handoff_service=execution_service,
        )
    ) as client:
        response = client.post(
            "/api/v1/platform/bootstrap-handoff-plan/preview",
            headers={"Authorization": authorization},
            json=request,
        )
        malformed = client.post(
            "/api/v1/platform/bootstrap-handoff-plan/preview",
            headers={"Authorization": authorization},
            json={**request, "reader_token": "must-not-be-accepted"},
        )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload["checks"]) == 15
    assert payload["external_operations_authorized"] is False
    assert payload["source_run_version"] == 17
    assert payload["readiness_class"] == "developer_linux_lab_bootstrap_complete"
    assert all(value is False for value in payload["readiness_claims"].values())
    lowered = json.dumps(payload).lower()
    assert "reader_token" not in lowered
    assert "bearer " not in lowered
    assert malformed.status_code == 422
