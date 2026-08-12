from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_connector_upgrade_readiness import UpgradePackageSource, upgrade_package
from test_instance_creation import create_instance, instance_fixture, instance_operator
from test_package_acquisition import CollectingAuditSink
from test_target_configuration import bind_target, target_configuration_fixture

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.target_configuration_memory import (
    InMemoryConnectorTargetConfigurationRepository,
)
from atlas.modules.connectors.adapters.upgrade_approval_memory import (
    InMemoryConnectorUpgradeApprovalPolicySource,
    InMemoryConnectorUpgradeApprovalRepository,
    InMemoryConnectorUpgradeAuditReadinessSource,
)
from atlas.modules.connectors.adapters.upgrade_approval_postgres import (
    PostgreSQLConnectorUpgradeApprovalRepository,
)
from atlas.modules.connectors.application.instance_creation import (
    ConnectorInstanceCreationService,
)
from atlas.modules.connectors.application.package_installation import PackageInstallationService
from atlas.modules.connectors.application.package_registration import PackageRegistrationService
from atlas.modules.connectors.application.registry_publication import RegistryPublicationService
from atlas.modules.connectors.application.upgrade_approval import (
    ConnectorUpgradeApprovalService,
    build_development_connector_upgrade_approval_policy,
)
from atlas.modules.connectors.application.upgrade_approval_ports import (
    ConnectorUpgradeApprovalError,
)
from atlas.modules.connectors.application.upgrade_readiness import (
    ConnectorUpgradeReadinessService,
)
from atlas.modules.connectors.domain.instance_creation import ConnectorInstanceRecord
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationReceipt,
)
from atlas.modules.connectors.domain.upgrade_approval import (
    ConnectorUpgradeApprovalOutcome,
    ConnectorUpgradeApprovalState,
    ConnectorUpgradeAuditReadinessEvidence,
)


async def approval_fixture(
    *,
    clock: Callable[[], datetime] | None = None,
    audit_readiness_source: InMemoryConnectorUpgradeAuditReadinessSource | None = None,
) -> tuple[
    ConnectorUpgradeApprovalService,
    ConnectorUpgradeReadinessService,
    ConnectorInstanceCreationService,
    PackageInstallationService,
    PackageRegistrationService,
    RegistryPublicationService,
    tuple[ConnectorInstanceRecord, ConnectorPackageInstallationReceipt],
    CollectingAuditSink,
]:
    audit = CollectingAuditSink()
    (
        instance_service,
        package_service,
        registration_service,
        publication_service,
        installation,
        policy,
    ) = await instance_fixture()
    instance = await create_instance(instance_service, installation, policy)
    (
        current_receipt,
        _,
        current_registration,
        _,
    ) = await package_service.connector_instance_creation_source(receipt_id=installation.receipt_id)
    candidate_receipt, candidate_registration = upgrade_package(
        current_receipt, current_registration
    )
    now = installation.installed_at + timedelta(hours=2)
    resolved_clock = clock or (lambda: now)
    upgrade_service = ConnectorUpgradeReadinessService(
        instance_repository=instance_service.repository,
        target_repository=InMemoryConnectorTargetConfigurationRepository(),
        package_source=UpgradePackageSource(
            ((current_receipt, current_registration), (candidate_receipt, candidate_registration))
        ),
        audit_sink=audit,
        environment_id=instance.environment_id,
        clock=resolved_clock,
    )
    approval_policy = build_development_connector_upgrade_approval_policy(
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=1),
    )
    service = ConnectorUpgradeApprovalService(
        repository=InMemoryConnectorUpgradeApprovalRepository(),
        policy_source=InMemoryConnectorUpgradeApprovalPolicySource((approval_policy,)),
        upgrade_service=upgrade_service,
        audit_sink=audit,
        environment_id=instance.environment_id,
        audit_readiness_source=audit_readiness_source,
        clock=resolved_clock,
    )
    return (
        service,
        upgrade_service,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        (instance, candidate_receipt),
        audit,
    )


@pytest.mark.asyncio
async def test_upgrade_approval_request_binds_exact_plan_without_granting_authority() -> None:
    service, upgrade_service, _, _, _, _, sources, audit = await approval_fixture()
    instance, candidate_receipt = sources
    actor = instance_operator()
    plan = await upgrade_service.plan(
        actor=actor,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-plan-source",
    )

    request = await service.create(
        actor=actor,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        source_plan_digest=plan.canonical_digest,
        purpose="Submit this exact connector upgrade plan for independent human review.",
        acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
        idempotency_key="connector-upgrade-approval-001",
        correlation_id="correlation.connector-upgrade-approval",
    )
    replay = await service.create(
        actor=actor,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        source_plan_digest=plan.canonical_digest,
        purpose="Submit this exact connector upgrade plan for independent human review.",
        acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
        idempotency_key="connector-upgrade-approval-001",
        correlation_id="correlation.connector-upgrade-approval-replay",
    )

    assert request.plan_id == plan.plan_id and request.plan_digest == plan.canonical_digest
    assert request.candidate_receipt_digest == plan.candidate_receipt_digest
    assert request.state == "pending" and request.separation_of_duties_required
    assert not request.approval_granted and not request.decision_recorded
    assert not request.execution_authorized and not request.infrastructure_mutation_performed
    assert request.requested_by == actor.subject_id
    assert replay.request_id == request.request_id and replay.reused
    restored = PostgreSQLConnectorUpgradeApprovalRepository._to_domain(
        cast(
            dict[str, object],
            ConnectorUpgradeApprovalService._normalize(asdict(request)),
        )
    )
    assert restored == request
    assert [item.result_code for item in audit.records].count(
        "connector_upgrade_approval_request_created"
    ) == 1


@pytest.mark.asyncio
async def test_upgrade_approval_request_fails_closed_for_drift_and_configured_target() -> None:
    service, _upgrade_service, _, _, _, _, sources, _ = await approval_fixture()
    instance, candidate_receipt = sources
    actor = instance_operator()
    with pytest.raises(ConnectorUpgradeApprovalError, match="plan_not_eligible"):
        await service.create(
            actor=actor,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            source_plan_digest="0" * 64,
            purpose="Submit this exact connector upgrade plan for independent human review.",
            acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-approval-drift",
            correlation_id="correlation.connector-upgrade-approval-drift",
        )

    (
        target_service,
        configured_instance_service,
        package_service,
        _,
        configured_instance,
        profile,
        target_policy,
    ) = await target_configuration_fixture()
    await bind_target(target_service, configured_instance, profile, target_policy)
    (
        current_receipt,
        _,
        current_registration,
        _,
    ) = await package_service.connector_instance_creation_source(
        receipt_id=configured_instance.source_installation_receipt_id
    )
    configured_candidate, configured_registration = upgrade_package(
        current_receipt, current_registration
    )
    configured_upgrade_service = ConnectorUpgradeReadinessService(
        instance_repository=configured_instance_service.repository,
        target_repository=target_service.repository,
        package_source=UpgradePackageSource(
            (
                (current_receipt, current_registration),
                (configured_candidate, configured_registration),
            )
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=configured_instance.environment_id,
    )
    blocked_plan = await configured_upgrade_service.plan(
        actor=actor,
        record_id=configured_instance.record_id,
        candidate_receipt_id=configured_candidate.receipt_id,
        correlation_id="correlation.connector-upgrade-plan-blocked",
    )
    blocked_service = ConnectorUpgradeApprovalService(
        repository=InMemoryConnectorUpgradeApprovalRepository(),
        policy_source=InMemoryConnectorUpgradeApprovalPolicySource(()),
        upgrade_service=configured_upgrade_service,
        audit_sink=CollectingAuditSink(),
        environment_id=configured_instance.environment_id,
    )
    with pytest.raises(ConnectorUpgradeApprovalError, match="plan_not_eligible"):
        await blocked_service.create(
            actor=actor,
            record_id=configured_instance.record_id,
            candidate_receipt_id=configured_candidate.receipt_id,
            source_plan_digest=blocked_plan.canonical_digest,
            purpose="Submit this exact connector upgrade plan for independent human review.",
            acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-approval-blocked",
            correlation_id="correlation.connector-upgrade-approval-blocked",
        )


def test_upgrade_approval_api_is_no_store_and_hides_custody_metadata(tmp_path: Path) -> None:
    (
        approval_service,
        upgrade_service,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        sources,
        _,
    ) = asyncio.run(approval_fixture())
    instance, candidate_receipt = sources
    actor = instance_operator()
    plan = asyncio.run(
        upgrade_service.plan(
            actor=actor,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            correlation_id="correlation.connector-upgrade-plan-api",
        )
    )
    app = create_app(
        settings(
            development_subject_id=actor.subject_id,
            mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
        ),
        identity_provider=BasicTestIdentityProvider(actor),
        registry_publication_service=publication_service,
        package_registration_service=registration_service,
        package_installation_service=package_service,
        connector_instance_creation_service=instance_service,
        connector_upgrade_approval_service=approval_service,
    )
    with TestClient(app) as client:
        app.state.connector_upgrade_readiness_service = upgrade_service
        login_response = login(client)
        response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-plans/"
            f"{candidate_receipt.receipt_id}/approval-requests",
            headers={
                "Idempotency-Key": "connector-upgrade-approval-api",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
            json={
                "schema_version": "atlas.connector-upgrade-approval-create-input.v1",
                "source_plan_digest": plan.canonical_digest,
                "purpose": "Submit this exact connector upgrade plan for independent human review.",
                "acknowledged_request_is_not_approval_and_grants_no_execution_authority": True,
            },
        )
        assert response.status_code == 201, response.text
        request_id = response.json()["data"]["request_id"]
        read_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request_id}"
        )

    assert response.headers["Cache-Control"] == "no-store"
    assert read_response.status_code == 200 and read_response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["plan_digest"] == plan.canonical_digest and data["state"] == "pending"
    assert data["approval_granted"] is False and data["execution_authorized"] is False
    rendered = response.text.lower()
    for hidden in ("request_fingerprint", "idempotency_key", "credential", "target_endpoint"):
        assert hidden not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "state", "valid"),
    (
        (ConnectorUpgradeApprovalOutcome.APPROVE, ConnectorUpgradeApprovalState.APPROVED, True),
        (ConnectorUpgradeApprovalOutcome.REJECT, ConnectorUpgradeApprovalState.REJECTED, False),
        (
            ConnectorUpgradeApprovalOutcome.NEEDS_EVIDENCE,
            ConnectorUpgradeApprovalState.NEEDS_EVIDENCE,
            False,
        ),
        (ConnectorUpgradeApprovalOutcome.DEFER, ConnectorUpgradeApprovalState.DEFERRED, False),
    ),
)
async def test_upgrade_approval_decision_is_separated_exact_and_non_executable(
    outcome: ConnectorUpgradeApprovalOutcome,
    state: ConnectorUpgradeApprovalState,
    valid: bool,
) -> None:
    service, upgrade_service, _, _, _, _, sources, audit = await approval_fixture()
    instance, candidate_receipt = sources
    requester = instance_operator()
    approver = instance_operator("subject.connector-upgrade-independent-approver")
    plan = await upgrade_service.plan(
        actor=requester,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-decision-plan",
    )
    request = await service.create(
        actor=requester,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        source_plan_digest=plan.canonical_digest,
        purpose="Submit this exact connector upgrade plan for independent human review.",
        acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
        idempotency_key=f"connector-upgrade-request-{outcome.value}",
        correlation_id="correlation.connector-upgrade-decision-request",
    )
    with pytest.raises(ConnectorUpgradeApprovalError, match="separation_required"):
        await service.decide(
            actor=requester,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_request_version=request.version,
            expected_request_digest=request.canonical_digest,
            outcome=outcome,
            rationale="Record an accountable decision after reviewing the exact immutable plan.",
            acknowledged_decision_grants_no_execution_authority=True,
            idempotency_key=f"connector-upgrade-decision-self-{outcome.value}",
            correlation_id="correlation.connector-upgrade-decision-self",
        )

    record = await service.decide(
        actor=approver,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_request_version=request.version,
        expected_request_digest=request.canonical_digest,
        outcome=outcome,
        rationale="Record an accountable decision after reviewing the exact immutable plan.",
        acknowledged_decision_grants_no_execution_authority=True,
        idempotency_key=f"connector-upgrade-decision-{outcome.value}",
        correlation_id="correlation.connector-upgrade-decision",
    )
    replay = await service.decide(
        actor=approver,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_request_version=request.version,
        expected_request_digest=request.canonical_digest,
        outcome=outcome,
        rationale="Record an accountable decision after reviewing the exact immutable plan.",
        acknowledged_decision_grants_no_execution_authority=True,
        idempotency_key=f"connector-upgrade-decision-{outcome.value}",
        correlation_id="correlation.connector-upgrade-decision-replay",
    )

    assert record.state is state and record.approval_valid is valid
    assert record.approval_granted is valid and record.decision_recorded
    assert record.decision is not None and record.decision.decided_by == approver.subject_id
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert replay.decision is not None and replay.decision.reused
    restored = PostgreSQLConnectorUpgradeApprovalRepository._decision_to_domain(
        cast(
            dict[str, object],
            ConnectorUpgradeApprovalService._normalize(asdict(record.decision)),
        )
    )
    assert restored == record.decision
    assert [item.result_code for item in audit.records].count(
        f"connector_upgrade_approval_{outcome.value}"
    ) == 1


def test_upgrade_approval_decision_api_restores_plan_record_and_hides_authority(
    tmp_path: Path,
) -> None:
    (
        approval_service,
        upgrade_service,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        sources,
        _,
    ) = asyncio.run(approval_fixture())
    instance, candidate_receipt = sources
    requester = instance_operator()
    approver = instance_operator("subject.connector-upgrade-independent-approver")
    plan = asyncio.run(
        upgrade_service.plan(
            actor=requester,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            correlation_id="correlation.connector-upgrade-decision-api-plan",
        )
    )
    approval_request = asyncio.run(
        approval_service.create(
            actor=requester,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            source_plan_digest=plan.canonical_digest,
            purpose="Submit this exact connector upgrade plan for independent human review.",
            acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-decision-api-request",
            correlation_id="correlation.connector-upgrade-decision-api-request",
        )
    )
    app = create_app(
        settings(
            development_subject_id=approver.subject_id,
            mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
        ),
        identity_provider=BasicTestIdentityProvider(approver),
        registry_publication_service=publication_service,
        package_registration_service=registration_service,
        package_installation_service=package_service,
        connector_instance_creation_service=instance_service,
        connector_upgrade_approval_service=approval_service,
    )
    with TestClient(app) as client:
        app.state.connector_upgrade_readiness_service = upgrade_service
        login_response = login(client)
        read_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-plans/"
            f"{candidate_receipt.receipt_id}/approval-record"
        )
        response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{approval_request.request_id}/decisions",
            headers={
                "Idempotency-Key": "connector-upgrade-decision-api",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
            json={
                "schema_version": "atlas.connector-upgrade-approval-decision-input.v1",
                "expected_request_version": approval_request.version,
                "expected_request_digest": approval_request.canonical_digest,
                "outcome": "approve",
                "rationale": "Approve the exact immutable plan after independent evidence review.",
                "acknowledged_decision_grants_no_execution_authority": True,
            },
        )

    assert read_response.status_code == 200
    assert read_response.json()["data"]["state"] == "pending"
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["state"] == "approved" and data["approval_valid"] is True
    assert data["execution_authorized"] is False
    rendered = response.text.lower()
    for hidden in (
        "request_fingerprint",
        "decision_fingerprint",
        "idempotency_key",
        "credential",
        "target_endpoint",
    ):
        assert hidden not in rendered


@pytest.mark.asyncio
async def test_upgrade_approval_revalidation_requires_three_people_and_remains_non_executable() -> (
    None
):
    current_time: list[datetime] = []

    def clock() -> datetime:
        return current_time[0]

    bootstrap = await instance_fixture()
    current_time.append(bootstrap[4].installed_at + timedelta(hours=2))
    audit_readiness_source = InMemoryConnectorUpgradeAuditReadinessSource()
    service, upgrade_service, _, _, _, _, sources, audit = await approval_fixture(
        clock=clock,
        audit_readiness_source=audit_readiness_source,
    )
    instance, candidate_receipt = sources
    requester = instance_operator()
    approver = instance_operator("subject.connector-upgrade-independent-approver")
    verifier = instance_operator("subject.connector-upgrade-independent-verifier")
    plan = await upgrade_service.plan(
        actor=requester,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-revalidation-plan",
    )
    request = await service.create(
        actor=requester,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        source_plan_digest=plan.canonical_digest,
        purpose="Submit this exact connector upgrade plan for independent human review.",
        acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
        idempotency_key="connector-upgrade-revalidation-request",
        correlation_id="correlation.connector-upgrade-revalidation-request",
    )
    current_time[0] += timedelta(minutes=5)
    record = await service.decide(
        actor=approver,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_request_version=request.version,
        expected_request_digest=request.canonical_digest,
        outcome=ConnectorUpgradeApprovalOutcome.APPROVE,
        rationale="Approve the unchanged plan after independent evidence review.",
        acknowledged_decision_grants_no_execution_authority=True,
        idempotency_key="connector-upgrade-revalidation-decision",
        correlation_id="correlation.connector-upgrade-revalidation-decision",
    )
    assert record.decision is not None
    current_time[0] += timedelta(minutes=5)

    for actor in (requester, approver):
        with pytest.raises(ConnectorUpgradeApprovalError, match="separation_required"):
            await service.revalidate(
                actor=actor,
                record_id=instance.record_id,
                request_id=request.request_id,
                expected_request_digest=request.canonical_digest,
                expected_decision_digest=record.decision.canonical_digest,
                purpose="Revalidate the exact approved plan without granting handoff authority.",
                acknowledged_revalidation_grants_no_handoff_or_execution_authority=True,
                idempotency_key=f"connector-upgrade-revalidation-self-{actor.subject_id[-8:]}",
                correlation_id="correlation.connector-upgrade-revalidation-self",
            )

    revalidation = await service.revalidate(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_request_digest=request.canonical_digest,
        expected_decision_digest=record.decision.canonical_digest,
        purpose="Revalidate the exact approved plan without granting handoff authority.",
        acknowledged_revalidation_grants_no_handoff_or_execution_authority=True,
        idempotency_key="connector-upgrade-revalidation-001",
        correlation_id="correlation.connector-upgrade-revalidation",
    )
    replay = await service.revalidate(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_request_digest=request.canonical_digest,
        expected_decision_digest=record.decision.canonical_digest,
        purpose="Revalidate the exact approved plan without granting handoff authority.",
        acknowledged_revalidation_grants_no_handoff_or_execution_authority=True,
        idempotency_key="connector-upgrade-revalidation-001",
        correlation_id="correlation.connector-upgrade-revalidation-replay",
    )
    latest = await service.get_latest_revalidation(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        correlation_id="correlation.connector-upgrade-revalidation-read",
    )
    readiness = await service.assess_handoff_readiness(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        correlation_id="correlation.connector-upgrade-handoff-readiness",
    )
    audit_evidence_payload = {
        "schema_version": "atlas.connector-upgrade-audit-readiness-evidence.v1",
        "organization_id": instance.organization_id,
        "environment_id": instance.environment_id,
        "request_id": request.request_id,
        "request_digest": request.canonical_digest,
        "revalidation_id": revalidation.revalidation_id,
        "revalidation_digest": revalidation.canonical_digest,
        "ledger_id": "audit-ledger.primary",
        "ledger_generation": "generation.2026-08-12",
        "producer_coverage_digest": "1" * 64,
        "integrity_verification_digest": "2" * 64,
        "redaction_policy_digest": "3" * 64,
        "retention_policy_digest": "4" * 64,
        "verified_at": current_time[0].isoformat(),
        "valid_until": (current_time[0] + timedelta(minutes=10)).isoformat(),
        "durable_acceptance": True,
        "append_only": True,
        "integrity_verified": True,
        "gap_free": True,
        "redaction_current": True,
        "retention_current": True,
        "producer_coverage_complete": True,
        "consequential_blocking_enabled": True,
        "infrastructure_mutation_performed": False,
    }
    audit_evidence_digest = ConnectorUpgradeApprovalService._digest(audit_evidence_payload)
    audit_evidence = ConnectorUpgradeAuditReadinessEvidence(
        evidence_id=f"connector-upgrade-audit-readiness-evidence.{audit_evidence_digest[:24]}",
        schema_version="atlas.connector-upgrade-audit-readiness-evidence.v1",
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        request_id=request.request_id,
        request_digest=request.canonical_digest,
        revalidation_id=revalidation.revalidation_id,
        revalidation_digest=revalidation.canonical_digest,
        ledger_id="audit-ledger.primary",
        ledger_generation="generation.2026-08-12",
        producer_coverage_digest="1" * 64,
        integrity_verification_digest="2" * 64,
        redaction_policy_digest="3" * 64,
        retention_policy_digest="4" * 64,
        verified_at=current_time[0],
        valid_until=current_time[0] + timedelta(minutes=10),
        canonical_digest=audit_evidence_digest,
        durable_acceptance=True,
        append_only=True,
        integrity_verified=True,
        gap_free=True,
        redaction_current=True,
        retention_current=True,
        producer_coverage_complete=True,
        consequential_blocking_enabled=True,
    )
    draft = await service.create_change_context_draft(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_readiness_digest=readiness.canonical_digest,
        proposed_window_start=current_time[0] + timedelta(hours=2),
        proposed_window_end=current_time[0] + timedelta(hours=3),
        justification="Prepare a governed connector upgrade change-context draft for ITSM review.",
        acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority=True,
        idempotency_key="connector-upgrade-change-context-001",
        correlation_id="correlation.connector-upgrade-change-context",
    )
    replayed_draft = await service.create_change_context_draft(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_readiness_digest=readiness.canonical_digest,
        proposed_window_start=current_time[0] + timedelta(hours=2),
        proposed_window_end=current_time[0] + timedelta(hours=3),
        justification="Prepare a governed connector upgrade change-context draft for ITSM review.",
        acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority=True,
        idempotency_key="connector-upgrade-change-context-001",
        correlation_id="correlation.connector-upgrade-change-context-replay",
    )
    latest_draft = await service.get_latest_change_context_draft(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        correlation_id="correlation.connector-upgrade-change-context-read",
    )
    with pytest.raises(ConnectorUpgradeApprovalError, match="verifier_required"):
        await service.create_change_context_draft(
            actor=requester,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_readiness_digest=readiness.canonical_digest,
            proposed_window_start=current_time[0] + timedelta(hours=2),
            proposed_window_end=current_time[0] + timedelta(hours=3),
            justification="Prepare a governed connector upgrade change-context draft for review.",
            acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority=True,
            idempotency_key="connector-upgrade-change-context-requester",
            correlation_id="correlation.connector-upgrade-change-context-requester",
        )
    with pytest.raises(ConnectorUpgradeApprovalError, match="readiness_stale"):
        await service.create_change_context_draft(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_readiness_digest="0" * 64,
            proposed_window_start=current_time[0] + timedelta(hours=2),
            proposed_window_end=current_time[0] + timedelta(hours=3),
            justification="Prepare a governed connector upgrade change-context draft for review.",
            acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority=True,
            idempotency_key="connector-upgrade-change-context-stale",
            correlation_id="correlation.connector-upgrade-change-context-stale",
        )
    with pytest.raises(ConnectorUpgradeApprovalError, match="idempotency_conflict"):
        await service.create_change_context_draft(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_readiness_digest=readiness.canonical_digest,
            proposed_window_start=current_time[0] + timedelta(hours=3),
            proposed_window_end=current_time[0] + timedelta(hours=4),
            justification="Prepare a governed connector upgrade change-context draft for review.",
            acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority=True,
            idempotency_key="connector-upgrade-change-context-001",
            correlation_id="correlation.connector-upgrade-change-context-conflict",
        )

    assert revalidation.approval_current_at_revalidation
    assert revalidation.governance_ready and not revalidation.handoff_ready
    assert not revalidation.target_configured and not revalidation.package_rebound
    assert not revalidation.configuration_changed and not revalidation.target_contacted
    assert not revalidation.handoff_artifact_issued
    assert not revalidation.execution_authorized
    assert not revalidation.infrastructure_mutation_performed
    assert len(revalidation.check_ids) == 7
    assert replay.reused and latest.revalidation_id == revalidation.revalidation_id
    assert readiness.assessment_state == "blocked"
    assert readiness.applicability_policy_id == (
        "connector-upgrade-handoff-evidence-applicability.default"
    )
    assert readiness.applicability_policy_version == "v2026.08.12.1"
    assert len(readiness.required_check_ids) == 9
    assert len(readiness.satisfied_check_ids) == 6
    assert readiness.not_applicable_check_ids == (
        "connector.upgrade.handoff.target-binding-current",
        "connector.upgrade.handoff.service-impact-evidence-current",
        "connector.upgrade.handoff.runtime-health-evidence-current",
    )
    assert readiness.blocker_ids == (
        "connector.upgrade.handoff.blocked.itsm-change-missing",
        "connector.upgrade.handoff.blocked.maintenance-window-missing",
        "connector.upgrade.handoff.blocked.audit-readiness-evidence-missing",
    )
    assert readiness.audit_readiness_evidence_id is None
    assert not readiness.audit_readiness_evidence_current
    audit_readiness_source.replace((audit_evidence,))
    readiness_with_audit = await service.assess_handoff_readiness(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        correlation_id="correlation.connector-upgrade-handoff-readiness-with-audit",
    )
    assert readiness_with_audit.audit_readiness_evidence_id == audit_evidence.evidence_id
    assert readiness_with_audit.audit_readiness_evidence_digest == audit_evidence.canonical_digest
    assert readiness_with_audit.audit_readiness_evidence_current
    assert "connector.upgrade.handoff.audit-readiness-evidence-current" in (
        readiness_with_audit.satisfied_check_ids
    )
    assert readiness_with_audit.blocker_ids == (
        "connector.upgrade.handoff.blocked.itsm-change-missing",
        "connector.upgrade.handoff.blocked.maintenance-window-missing",
    )
    with pytest.raises(ConnectorUpgradeApprovalError, match="draft_not_current"):
        await service.get_latest_change_context_draft(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            correlation_id="correlation.connector-upgrade-change-context-evidence-drift",
        )
    audit_readiness_source.replace((replace(audit_evidence, canonical_digest="0" * 64),))
    with pytest.raises(ConnectorUpgradeApprovalError, match="integrity_invalid"):
        await service.assess_handoff_readiness(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            correlation_id="correlation.connector-upgrade-audit-evidence-integrity",
        )
    audit_readiness_source.replace((audit_evidence,))
    with pytest.raises(ValueError, match="authority boundary"):
        replace(
            readiness,
            not_applicable_check_ids=(readiness.required_check_ids[0],),
        )
    assert not readiness.handoff_ready and not readiness.handoff_artifact_issued
    assert not readiness.approval_consumed and not readiness.target_contacted
    assert not readiness.package_rebound and not readiness.configuration_changed
    assert not readiness.execution_authorized
    assert not readiness.infrastructure_mutation_performed
    assert draft.state == "draft" and replayed_draft.reused
    assert latest_draft.draft_id == draft.draft_id
    assert draft.readiness_digest == readiness.canonical_digest
    assert not draft.itsm_dispatched and not draft.window_approved
    assert not draft.handoff_ready and not draft.handoff_artifact_issued
    assert not draft.approval_consumed and not draft.execution_authorized
    assert not draft.target_contacted and not draft.package_rebound
    assert not draft.configuration_changed
    assert not draft.infrastructure_mutation_performed
    current_time[0] = draft.valid_until
    with pytest.raises(ConnectorUpgradeApprovalError, match="draft_not_current"):
        await service.get_latest_change_context_draft(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            correlation_id="correlation.connector-upgrade-change-context-expired",
        )
    restored_draft = PostgreSQLConnectorUpgradeApprovalRepository._change_context_to_domain(
        cast(dict[str, object], ConnectorUpgradeApprovalService._normalize(asdict(draft)))
    )
    assert restored_draft == draft
    restored = PostgreSQLConnectorUpgradeApprovalRepository._revalidation_to_domain(
        cast(
            dict[str, object],
            ConnectorUpgradeApprovalService._normalize(asdict(revalidation)),
        )
    )
    assert restored == revalidation
    assert [item.result_code for item in audit.records].count(
        "connector_upgrade_approval_revalidated"
    ) == 1
    assert [item.result_code for item in audit.records].count(
        "connector_upgrade_change_context_draft_created"
    ) == 1
    assert [item.result_code for item in audit.records].count(
        "connector_upgrade_change_context_draft_reused"
    ) == 1


def test_upgrade_approval_revalidation_api_is_no_store_and_hides_custody_metadata(
    tmp_path: Path,
) -> None:
    (
        approval_service,
        upgrade_service,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        sources,
        _,
    ) = asyncio.run(approval_fixture())
    instance, candidate_receipt = sources
    requester = instance_operator()
    approver = instance_operator("subject.connector-upgrade-independent-approver")
    verifier = instance_operator("subject.connector-upgrade-independent-verifier")
    plan = asyncio.run(
        upgrade_service.plan(
            actor=requester,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            correlation_id="correlation.connector-upgrade-revalidation-api-plan",
        )
    )
    request = asyncio.run(
        approval_service.create(
            actor=requester,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            source_plan_digest=plan.canonical_digest,
            purpose="Submit this exact connector upgrade plan for independent human review.",
            acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-revalidation-api-request",
            correlation_id="correlation.connector-upgrade-revalidation-api-request",
        )
    )
    approval = asyncio.run(
        approval_service.decide(
            actor=approver,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_request_version=request.version,
            expected_request_digest=request.canonical_digest,
            outcome=ConnectorUpgradeApprovalOutcome.APPROVE,
            rationale="Approve the exact immutable plan after independent evidence review.",
            acknowledged_decision_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-revalidation-api-decision",
            correlation_id="correlation.connector-upgrade-revalidation-api-decision",
        )
    )
    assert approval.decision is not None
    app = create_app(
        settings(
            development_subject_id=verifier.subject_id,
            mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
        ),
        identity_provider=BasicTestIdentityProvider(verifier),
        registry_publication_service=publication_service,
        package_registration_service=registration_service,
        package_installation_service=package_service,
        connector_instance_creation_service=instance_service,
        connector_upgrade_approval_service=approval_service,
    )
    with TestClient(app) as client:
        app.state.connector_upgrade_readiness_service = upgrade_service
        login_response = login(client)
        response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/revalidations",
            headers={
                "Idempotency-Key": "connector-upgrade-revalidation-api",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
            json={
                "schema_version": "atlas.connector-upgrade-approval-revalidation-input.v1",
                "expected_request_digest": request.canonical_digest,
                "expected_decision_digest": approval.decision.canonical_digest,
                "purpose": "Revalidate the exact approved plan without granting handoff authority.",
                "acknowledged_revalidation_grants_no_handoff_or_execution_authority": True,
            },
        )
        read_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/revalidations/latest"
        )
        readiness_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/handoff-readiness"
        )
        readiness_digest = readiness_response.json()["data"]["canonical_digest"]
        draft_response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/change-context-drafts",
            headers={
                "Idempotency-Key": "connector-upgrade-change-context-api",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
            json={
                "schema_version": "atlas.connector-upgrade-change-context-draft-input.v1",
                "expected_readiness_digest": readiness_digest,
                "proposed_window_start": (plan.generated_at + timedelta(hours=3)).isoformat(),
                "proposed_window_end": (plan.generated_at + timedelta(hours=4)).isoformat(),
                "justification": "Prepare the exact connector upgrade for governed ITSM review.",
                (
                    "acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority"
                ): True,
            },
        )
        draft_read_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/change-context-drafts/latest"
        )

    assert response.status_code == 201, response.text
    assert read_response.status_code == 200, read_response.text
    assert readiness_response.status_code == 200, readiness_response.text
    assert draft_response.status_code == 201, draft_response.text
    assert draft_read_response.status_code == 200, draft_read_response.text
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["governance_ready"] is True and data["handoff_ready"] is False
    assert data["execution_authorized"] is False
    readiness_data = readiness_response.json()["data"]
    assert readiness_data["schema_version"] == "atlas.connector-upgrade-handoff-readiness.v3"
    assert readiness_data["assessment_state"] == "blocked"
    assert readiness_data["handoff_ready"] is False
    assert readiness_data["handoff_artifact_issued"] is False
    assert readiness_data["approval_consumed"] is False
    assert len(readiness_data["required_check_ids"]) == 9
    assert len(readiness_data["not_applicable_check_ids"]) == 3
    assert len(readiness_data["blocker_ids"]) == 3
    assert readiness_data["applicability_policy_digest"]
    assert readiness_data["audit_readiness_evidence_id"] is None
    assert readiness_data["audit_readiness_evidence_digest"] is None
    assert readiness_data["audit_readiness_evidence_current"] is False
    draft_data = draft_response.json()["data"]
    assert draft_data["state"] == "draft"
    assert draft_data["readiness_digest"] == readiness_data["canonical_digest"]
    assert draft_data["itsm_dispatched"] is False
    assert draft_data["window_approved"] is False
    assert draft_data["handoff_ready"] is False
    assert draft_data["target_contacted"] is False
    assert draft_data["package_rebound"] is False
    assert draft_data["configuration_changed"] is False
    assert draft_data["execution_authorized"] is False
    assert draft_read_response.json()["data"]["draft_id"] == draft_data["draft_id"]
    assert draft_response.headers["Cache-Control"] == "no-store"
    rendered = f"{response.text} {draft_response.text} {draft_read_response.text}".lower()
    for hidden in (
        "revalidation_fingerprint",
        "idempotency_key",
        "credential",
        "target_endpoint",
        "request_fingerprint",
        "ledger_id",
        "ledger_generation",
        "integrity_verification_digest",
        "redaction_policy_digest",
        "retention_policy_digest",
    ):
        assert hidden not in rendered
