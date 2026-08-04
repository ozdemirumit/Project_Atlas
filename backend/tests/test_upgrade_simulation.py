from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_bootstrap_identity_handoff import NOW
from test_browser_sessions import BasicTestIdentityProvider, login, settings, subject
from test_logical_backup_restore import ALL_COMPONENTS, recovery_service

from atlas.api.app import create_app
from atlas.core.persistence.models import UpgradeSimulationModel
from atlas.modules.upgrade.adapters.memory import InMemoryUpgradeSimulationRepository
from atlas.modules.upgrade.adapters.postgres import PostgreSQLUpgradeSimulationRepository
from atlas.modules.upgrade.application.ports import UpgradeError
from atlas.modules.upgrade.application.service import TARGET_RELEASE_ID, UpgradeService


async def upgrade_context(tmp_path: Path):  # type: ignore[no-untyped-def]
    sink, bootstrap_repository, run, recovery_repository, _, recovery = await recovery_service(
        tmp_path
    )
    backup_preview = await recovery.preview(
        actor=subject(), source_run_id=run.run_id, component_ids=ALL_COMPONENTS
    )
    backup = await recovery.create_backup(
        actor=subject(),
        source_run_id=run.run_id,
        source_run_version=run.version,
        component_ids=ALL_COMPONENTS,
        preview_digest=backup_preview.preview_digest,
        archive_sha256=backup_preview.archive_sha256,
        target_id=backup_preview.target_id,
        expected_target_state=backup_preview.target_state,
        justification="Create reviewed logical recovery evidence before upgrade",
        confirmed=True,
        idempotency_key="upgrade-backup-create-0001",
        correlation_id="correlation.upgrade.backup",
    )
    validation = await recovery.validate_restore(
        actor=subject(),
        backup_id=backup.backup_id,
        archive_sha256=backup.archive_sha256,
        confirmed_isolated=True,
        idempotency_key="upgrade-restore-validation-0001",
        correlation_id="correlation.upgrade.restore",
    )
    simulation_repository = InMemoryUpgradeSimulationRepository()
    upgrade = UpgradeService(
        bootstrap_repository=bootstrap_repository,
        recovery_repository=recovery_repository,
        simulation_repository=simulation_repository,
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    return (
        sink,
        bootstrap_repository,
        run,
        recovery_repository,
        recovery,
        backup,
        validation,
        simulation_repository,
        upgrade,
    )


def simulation_request(plan, *, idempotency_key: str = "upgrade-simulation-0001"):  # type: ignore[no-untyped-def]
    return {
        "actor": subject(),
        "source_run_id": plan.source_run_id,
        "source_run_version": plan.source_run_version,
        "backup_id": plan.backup_id,
        "restore_validation_id": plan.restore_validation_id,
        "target_release_id": plan.target_release_id,
        "plan_id": plan.plan_id,
        "plan_digest": plan.plan_digest,
        "source_evidence_digest": plan.source_evidence_digest,
        "justification": "Review isolated upgrade abort and rollback behavior",
        "confirmed_isolated": True,
        "idempotency_key": idempotency_key,
        "correlation_id": "correlation.upgrade.simulation",
    }


@pytest.mark.asyncio
async def test_readiness_and_rollback_simulation_are_deterministic(tmp_path: Path) -> None:
    sink, _, run, _, _, backup, validation, _, service = await upgrade_context(tmp_path)
    first = await service.preview(
        actor=subject(),
        source_run_id=run.run_id,
        backup_id=backup.backup_id,
        restore_validation_id=validation.validation_id,
        target_release_id=TARGET_RELEASE_ID,
    )
    second = await service.preview(
        actor=subject(),
        source_run_id=run.run_id,
        backup_id=backup.backup_id,
        restore_validation_id=validation.validation_id,
        target_release_id=TARGET_RELEASE_ID,
    )
    assert first.plan_digest == second.plan_digest
    assert first.source_evidence_digest == second.source_evidence_digest
    assert len(first.readiness_checks) == 12
    assert len(first.migration_steps) == 3
    assert all(item.passed and item.mandatory for item in first.readiness_checks)
    assert first.production_authorized is False
    assert first.execution_authorized is False
    assert first.active_state_mutation_performed is False

    simulation = await service.simulate(**simulation_request(first))
    replay = await service.simulate(**simulation_request(first))
    assert simulation.state.value == "passed"
    assert replay.reused is True
    assert len(simulation.steps) == 8
    assert simulation.abort_injected_at_step_id == "simulation.deploy-target"
    assert simulation.rollback_decision == "rollback.decision.applicable"
    assert simulation.estimated_downtime_minutes == 10
    assert simulation.isolated_target is True
    safety = (
        simulation.production_authorized,
        simulation.artifact_acquisition_performed,
        simulation.database_migration_performed,
        simulation.service_restart_performed,
        simulation.traffic_switch_performed,
        simulation.active_restore_performed,
        simulation.secret_resolution_performed,
        simulation.network_request_performed,
        simulation.model_inference_performed,
        simulation.infrastructure_mutation_performed,
    )
    assert not any(safety)
    assert [item.result_code for item in sink.records[-2:]] == [
        "upgrade_rollback_simulation_authorized",
        "upgrade_rollback_simulation_completed",
    ]


@pytest.mark.asyncio
async def test_upgrade_fails_closed_for_unknown_stale_or_conflicting_evidence(
    tmp_path: Path,
) -> None:
    (
        sink,
        bootstrap_repository,
        run,
        recovery_repository,
        _,
        backup,
        validation,
        _,
        service,
    ) = await upgrade_context(tmp_path)
    with pytest.raises(UpgradeError, match="target_unsupported"):
        await service.preview(
            actor=subject(),
            source_run_id=run.run_id,
            backup_id=backup.backup_id,
            restore_validation_id=validation.validation_id,
            target_release_id="release.atlas.unknown-9.9.9",
        )
    plan = await service.preview(
        actor=subject(),
        source_run_id=run.run_id,
        backup_id=backup.backup_id,
        restore_validation_id=validation.validation_id,
        target_release_id=TARGET_RELEASE_ID,
    )
    stale = simulation_request(plan, idempotency_key="upgrade-stale-plan-0001")
    stale["plan_digest"] = "0" * 64
    with pytest.raises(UpgradeError, match="readiness_plan_stale"):
        await service.simulate(**stale)

    await service.simulate(**simulation_request(plan))
    conflict = simulation_request(plan)
    conflict["justification"] = "Review a materially different isolated simulation request"
    with pytest.raises(UpgradeError, match="idempotency_conflict"):
        await service.simulate(**conflict)

    expired_service = UpgradeService(
        bootstrap_repository=bootstrap_repository,
        recovery_repository=recovery_repository,
        simulation_repository=InMemoryUpgradeSimulationRepository(),
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW + timedelta(days=8),
    )
    with pytest.raises(UpgradeError, match="backup_evidence_invalid"):
        await expired_service.preview(
            actor=subject(),
            source_run_id=run.run_id,
            backup_id=backup.backup_id,
            restore_validation_id=validation.validation_id,
            target_release_id=TARGET_RELEASE_ID,
        )

    current_key = (run.identity.organization_id, run.identity.environment_id, run.identity.site_id)
    bootstrap_repository._records[current_key] = replace(run, version=run.version + 1)
    with pytest.raises(UpgradeError, match="backup_evidence_invalid"):
        await service.preview(
            actor=subject(),
            source_run_id=run.run_id,
            backup_id=backup.backup_id,
            restore_validation_id=validation.validation_id,
            target_release_id=TARGET_RELEASE_ID,
        )


@pytest.mark.asyncio
async def test_required_audit_failure_blocks_upgrade_simulation(tmp_path: Path) -> None:
    (
        _,
        bootstrap_repository,
        run,
        recovery_repository,
        _,
        backup,
        validation,
        _,
        _,
    ) = await upgrade_context(tmp_path)

    class FailingAuditSink:
        async def record(self, event) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("audit unavailable")

    repository = InMemoryUpgradeSimulationRepository()
    service = UpgradeService(
        bootstrap_repository=bootstrap_repository,
        recovery_repository=recovery_repository,
        simulation_repository=repository,
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    plan = await service.preview(
        actor=subject(),
        source_run_id=run.run_id,
        backup_id=backup.backup_id,
        restore_validation_id=validation.validation_id,
        target_release_id=TARGET_RELEASE_ID,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.simulate(**simulation_request(plan, idempotency_key="upgrade-audit-0001"))
    assert repository._records == {}


def test_postgres_upgrade_mapping_preserves_simulation_evidence(tmp_path: Path) -> None:
    context = asyncio.run(upgrade_context(tmp_path))
    run, backup, validation, mapping_service = context[2], context[5], context[6], context[8]
    plan = asyncio.run(
        mapping_service.preview(
            actor=subject(),
            source_run_id=run.run_id,
            backup_id=backup.backup_id,
            restore_validation_id=validation.validation_id,
            target_release_id=TARGET_RELEASE_ID,
        )
    )
    simulation = asyncio.run(mapping_service.simulate(**simulation_request(plan)))
    restored = PostgreSQLUpgradeSimulationRepository._to_domain(
        UpgradeSimulationModel(
            simulation_id=simulation.simulation_id,
            schema_version=simulation.schema_version,
            state=simulation.state.value,
            actor_id=simulation.actor_id,
            organization_id=simulation.organization_id,
            environment_id=simulation.environment_id,
            site_id=simulation.site_id,
            source_run_id=simulation.source_run_id,
            source_run_version=simulation.source_run_version,
            plan_id=simulation.plan_id,
            plan_digest=simulation.plan_digest,
            backup_id=simulation.backup_id,
            restore_validation_id=simulation.restore_validation_id,
            request_fingerprint=simulation.request_fingerprint,
            idempotency_key=simulation.idempotency_key,
            steps=[
                {
                    "step_id": item.step_id,
                    "sequence": item.sequence,
                    "state": item.state.value,
                    "result_code": item.result_code,
                    "rollback_applicable": item.rollback_applicable,
                    "simulated_minutes": item.simulated_minutes,
                }
                for item in simulation.steps
            ],
            impacted_service_ids=list(simulation.impacted_service_ids),
            post_verification_check_ids=list(simulation.post_verification_check_ids),
            abort_injected_at_step_id=simulation.abort_injected_at_step_id,
            rollback_decision=simulation.rollback_decision,
            estimated_downtime_minutes=simulation.estimated_downtime_minutes,
            simulation_digest=simulation.simulation_digest,
            created_at=simulation.created_at,
        )
    )
    assert restored.simulation_digest == simulation.simulation_digest
    assert restored.steps == simulation.steps


def test_upgrade_api_requires_session_csrf_and_strict_payload(tmp_path: Path) -> None:
    context = asyncio.run(upgrade_context(tmp_path))
    sink, run, recovery, backup, validation, upgrade = (
        context[0],
        context[2],
        context[4],
        context[5],
        context[6],
        context[8],
    )
    request = {
        "schema_version": "atlas.upgrade-readiness-request.v1",
        "source_run_id": run.run_id,
        "backup_id": backup.backup_id,
        "restore_validation_id": validation.validation_id,
        "target_release_id": TARGET_RELEASE_ID,
    }
    with TestClient(
        create_app(
            settings(logical_backup_root=tmp_path / "default-backups"),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
            recovery_service=recovery,
            upgrade_service=upgrade,
        )
    ) as client:
        denied = client.post("/api/v1/platform/upgrades/readiness-preview", json=request)
        session = login(client)
        csrf = session.headers["X-CSRF-Token"]
        missing_csrf = client.post("/api/v1/platform/upgrades/readiness-preview", json=request)
        malformed = client.post(
            "/api/v1/platform/upgrades/readiness-preview",
            headers={"X-CSRF-Token": csrf},
            json={**request, "execute": True},
        )
        preview_response = client.post(
            "/api/v1/platform/upgrades/readiness-preview",
            headers={"X-CSRF-Token": csrf},
            json=request,
        )
        assert preview_response.status_code == 200, preview_response.text
        plan = preview_response.json()["data"]
        simulation_response = client.post(
            f"/api/v1/platform/upgrades/{run.run_id}/simulations",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "upgrade-api-simulation-0001",
            },
            json={
                "schema_version": "atlas.upgrade-simulation-request.v1",
                "source_run_version": plan["source_run_version"],
                "backup_id": plan["backup_id"],
                "restore_validation_id": plan["restore_validation_id"],
                "target_release_id": plan["target_release_id"],
                "plan_id": plan["plan_id"],
                "plan_digest": plan["plan_digest"],
                "source_evidence_digest": plan["source_evidence_digest"],
                "justification": "Review isolated upgrade abort and rollback behavior",
                "confirmed_isolated": True,
            },
        )
    assert denied.status_code == 401
    assert missing_csrf.status_code == 403
    assert malformed.status_code == 422
    assert preview_response.status_code == 200
    assert simulation_response.status_code == 200, simulation_response.text
    assert simulation_response.json()["data"]["infrastructure_mutation_performed"] is False
