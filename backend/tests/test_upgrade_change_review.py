from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_bootstrap_identity_handoff import NOW
from test_browser_sessions import BasicTestIdentityProvider, login, settings, subject
from test_upgrade_simulation import simulation_request, upgrade_context

from atlas.api.app import create_app
from atlas.core.persistence.models import UpgradeChangeReviewPacketModel
from atlas.modules.change_review.adapters.memory import InMemoryChangeReviewPacketRepository
from atlas.modules.change_review.adapters.postgres import (
    PostgreSQLChangeReviewPacketRepository,
)
from atlas.modules.change_review.application.ports import ChangeReviewError
from atlas.modules.change_review.application.service import ChangeReviewService
from atlas.modules.upgrade.application.service import TARGET_RELEASE_ID


async def change_review_context(tmp_path: Path) -> tuple[Any, ...]:
    context = await upgrade_context(tmp_path)
    sink, run, backup, validation, simulation_repository, upgrade = (
        context[0],
        context[2],
        context[5],
        context[6],
        context[7],
        context[8],
    )
    plan = await upgrade.preview(
        actor=subject(),
        source_run_id=run.run_id,
        backup_id=backup.backup_id,
        restore_validation_id=validation.validation_id,
        target_release_id=TARGET_RELEASE_ID,
    )
    simulation = await upgrade.simulate(**simulation_request(plan))
    repository = InMemoryChangeReviewPacketRepository()
    service = ChangeReviewService(
        upgrade_service=upgrade,
        simulation_repository=simulation_repository,
        packet_repository=repository,
        audit_sink=sink,
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    return context, plan, simulation, repository, service


def preview_request(plan: Any, simulation: Any) -> dict[str, Any]:
    return {
        "actor": subject(),
        "source_run_id": plan.source_run_id,
        "source_run_version": plan.source_run_version,
        "backup_id": plan.backup_id,
        "restore_validation_id": plan.restore_validation_id,
        "target_release_id": plan.target_release_id,
        "plan_id": plan.plan_id,
        "plan_digest": plan.plan_digest,
        "simulation_id": simulation.simulation_id,
        "simulation_digest": simulation.simulation_digest,
    }


def packet_request(
    preview: Any,
    plan: Any,
    simulation: Any,
    *,
    key: str = "change-review-0001",
) -> dict[str, Any]:
    return {
        **preview_request(plan, simulation),
        "preview_id": preview.preview_id,
        "preview_digest": preview.preview_digest,
        "preview_expires_at": preview.expires_at,
        "proposed_window_start": NOW + timedelta(hours=1),
        "proposed_window_end": NOW + timedelta(hours=2),
        "justification": "Prepare an evidence-bound upgrade packet for human change review",
        "confirmed": True,
        "acknowledged_no_authority": True,
        "idempotency_key": key,
        "correlation_id": "correlation.change-review.create",
    }


@pytest.mark.asyncio
async def test_change_review_packet_is_deterministic_complete_and_non_operational(
    tmp_path: Path,
) -> None:
    context, plan, simulation, _, service = await change_review_context(tmp_path)
    first = await service.preview(**preview_request(plan, simulation))
    second = await service.preview(**preview_request(plan, simulation))
    assert first.preview_digest == second.preview_digest
    assert len(first.migration_step_ids) == 3
    assert len(first.abort_criterion_ids) == 4
    assert len(first.rollback_step_ids) == 4
    assert len(first.post_verification_check_ids) == 6
    assert len(first.evidence_digests) == 4

    packet = await service.create_packet(**packet_request(first, plan, simulation))
    replay = await service.create_packet(**packet_request(first, plan, simulation))
    assert replay.packet_id == packet.packet_id
    assert replay.reused is True
    assert packet.migration_step_ids == first.migration_step_ids
    assert packet.abort_criterion_ids == first.abort_criterion_ids
    assert packet.rollback_step_ids == first.rollback_step_ids
    assert packet.post_verification_check_ids == first.post_verification_check_ids
    assert packet.evidence_digests == first.evidence_digests
    assert not any(
        (
            packet.approval_granted,
            packet.execution_authorized,
            packet.itsm_dispatched,
            packet.notification_sent,
            packet.workflow_executed,
            packet.infrastructure_mutation_performed,
        )
    )
    assert [item.result_code for item in context[0].records[-2:]] == [
        "upgrade_change_review_packet_authorized",
        "upgrade_change_review_packet_completed",
    ]


@pytest.mark.asyncio
async def test_change_review_fails_closed_for_stale_evidence_window_and_conflict(
    tmp_path: Path,
) -> None:
    _, plan, simulation, _, service = await change_review_context(tmp_path)
    stale = preview_request(plan, simulation)
    stale["source_run_version"] = plan.source_run_version + 1
    with pytest.raises(ChangeReviewError, match="source_stale"):
        await service.preview(**stale)

    invalid_simulation = preview_request(plan, simulation)
    invalid_simulation["simulation_digest"] = "0" * 64
    with pytest.raises(ChangeReviewError, match="simulation_invalid"):
        await service.preview(**invalid_simulation)

    preview = await service.preview(**preview_request(plan, simulation))
    invalid_window = packet_request(preview, plan, simulation, key="change-window-0001")
    invalid_window["proposed_window_start"] = NOW + timedelta(minutes=5)
    with pytest.raises(ChangeReviewError, match="window_invalid"):
        await service.create_packet(**invalid_window)

    expired = packet_request(preview, plan, simulation, key="change-expired-0001")
    expired["preview_expires_at"] = NOW - timedelta(seconds=1)
    with pytest.raises(ChangeReviewError, match="preview_stale"):
        await service.create_packet(**expired)

    await service.create_packet(**packet_request(preview, plan, simulation))
    conflict = packet_request(preview, plan, simulation)
    conflict["justification"] = "Prepare a materially different packet for another review purpose"
    with pytest.raises(ChangeReviewError, match="idempotency_conflict"):
        await service.create_packet(**conflict)


@pytest.mark.asyncio
async def test_change_review_rejects_simulation_owned_by_another_actor(tmp_path: Path) -> None:
    _, plan, simulation, _, service = await change_review_context(tmp_path)
    other = replace(subject(), subject_id="human.other-operator")
    request = preview_request(plan, simulation)
    request["actor"] = other
    with pytest.raises(ChangeReviewError, match="source_evidence_invalid"):
        await service.preview(**request)


@pytest.mark.asyncio
async def test_required_audit_failure_leaves_no_change_review_packet(tmp_path: Path) -> None:
    context, plan, simulation, _, _ = await change_review_context(tmp_path)

    class FailingAuditSink:
        async def record(self, event) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("audit unavailable")

    repository = InMemoryChangeReviewPacketRepository()
    service = ChangeReviewService(
        upgrade_service=context[8],
        simulation_repository=context[7],
        packet_repository=repository,
        audit_sink=FailingAuditSink(),
        environment_id="environment.test",
        site_id="site.local",
        clock=lambda: NOW,
    )
    preview = await service.preview(**preview_request(plan, simulation))
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.create_packet(**packet_request(preview, plan, simulation))
    assert repository._records == {}


def test_postgres_change_review_mapping_preserves_all_evidence(tmp_path: Path) -> None:
    context, plan, simulation, _, service = asyncio.run(change_review_context(tmp_path))
    preview = asyncio.run(service.preview(**preview_request(plan, simulation)))
    packet = asyncio.run(service.create_packet(**packet_request(preview, plan, simulation)))
    row = UpgradeChangeReviewPacketModel(
        **{
            column.name: (
                list(getattr(packet, column.name))
                if column.name.endswith("_ids") or column.name == "evidence_digests"
                else packet.state.value
                if column.name == "state"
                else getattr(packet, column.name)
            )
            for column in UpgradeChangeReviewPacketModel.__table__.columns
        }
    )
    restored = PostgreSQLChangeReviewPacketRepository._to_domain(row)
    assert restored.packet_digest == packet.packet_digest
    assert restored.migration_step_ids == packet.migration_step_ids
    assert restored.evidence_digests == packet.evidence_digests
    asyncio.run(context[8].close())


def test_change_review_api_requires_session_csrf_and_exact_payload(tmp_path: Path) -> None:
    context, plan, simulation, _, service = asyncio.run(change_review_context(tmp_path))
    upgrade_context_data = context
    request = {
        "schema_version": "atlas.upgrade-change-review-preview-request.v1",
        **{
            key: value for key, value in preview_request(plan, simulation).items() if key != "actor"
        },
    }
    with TestClient(
        create_app(
            settings(logical_backup_root=tmp_path / "default-backups"),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=upgrade_context_data[0],
            recovery_service=upgrade_context_data[4],
            upgrade_service=upgrade_context_data[8],
            change_review_service=service,
        )
    ) as client:
        denied = client.post("/api/v1/platform/upgrade-change-reviews/preview", json=request)
        session = login(client)
        csrf = session.headers["X-CSRF-Token"]
        malformed = client.post(
            "/api/v1/platform/upgrade-change-reviews/preview",
            headers={"X-CSRF-Token": csrf},
            json={**request, "execute": True},
        )
        preview_response = client.post(
            "/api/v1/platform/upgrade-change-reviews/preview",
            headers={"X-CSRF-Token": csrf},
            json=request,
        )
        data = preview_response.json()["data"]
        packet_response = client.post(
            f"/api/v1/platform/upgrade-change-reviews/{plan.source_run_id}/packets",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "change-review-api-0001",
            },
            json={
                **request,
                "schema_version": "atlas.upgrade-change-review-create-request.v1",
                "preview_id": data["preview_id"],
                "preview_digest": data["preview_digest"],
                "preview_expires_at": data["expires_at"],
                "proposed_window_start": (NOW + timedelta(hours=1)).isoformat(),
                "proposed_window_end": (NOW + timedelta(hours=2)).isoformat(),
                "justification": "Prepare an evidence-bound packet for human change review",
                "confirmed": True,
                "acknowledged_no_authority": True,
            },
        )
    assert denied.status_code == 401
    assert malformed.status_code == 422
    assert preview_response.status_code == 200, preview_response.text
    assert packet_response.status_code == 200, packet_response.text
    assert packet_response.json()["data"]["approval_granted"] is False
    assert packet_response.json()["data"]["itsm_dispatched"] is False
