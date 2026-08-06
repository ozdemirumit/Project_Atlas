from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_final_validation import (
    final_fixture,
    final_operator,
    final_validate,
)

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.package_approval_memory import (
    InMemoryPackageApprovalPolicySource,
    InMemoryPackageApprovalRepository,
)
from atlas.modules.connectors.adapters.package_approval_postgres import (
    PostgreSQLPackageApprovalRepository,
)
from atlas.modules.connectors.application.final_validation import PackageFinalValidationService
from atlas.modules.connectors.application.package_approval import (
    PackageApprovalService,
    build_development_package_approval_policy,
)
from atlas.modules.connectors.application.package_approval_ports import PackageApprovalError
from atlas.modules.connectors.domain.final_validation import ConnectorPackageFinalValidation
from atlas.modules.connectors.domain.package_approval import (
    ConnectorPackageApprovalPolicySnapshot,
    ConnectorPackageApprovalRecord,
    PackageApprovalOutcome,
    PackageApprovalState,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


def approval_operator(
    subject_id: str = "subject.package-independent-approver",
) -> AuthenticatedSubject:
    return final_operator(subject_id)


async def approval_fixture(
    *, audit_sink: CollectingAuditSink | FailingAuditSink | None = None
) -> tuple[
    PackageApprovalService,
    PackageFinalValidationService,
    ConnectorPackageFinalValidation,
    ConnectorPackageApprovalPolicySnapshot,
]:
    final_service, lab, final_policy = await final_fixture()
    final = await final_validate(final_service, lab, final_policy)
    policy = build_development_package_approval_policy(
        organization_id=final.organization_id,
        environment_id=final.environment_id,
        issued_at=final.validated_at - timedelta(hours=1),
        expires_at=final.validated_at + timedelta(days=2),
    )
    service = PackageApprovalService(
        repository=InMemoryPackageApprovalRepository(),
        final_validation_source=final_service,
        policy_source=InMemoryPackageApprovalPolicySource((policy,)),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=final.environment_id,
        clock=lambda: final.validated_at,
    )
    return service, final_service, final, policy


async def request_approval(
    service: PackageApprovalService,
    final: ConnectorPackageFinalValidation,
    policy: ConnectorPackageApprovalPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "package-approval-request-001",
) -> ConnectorPackageApprovalRecord:
    return await service.create_request(
        actor=actor or final_operator(),
        source_final_validation_id=final.validation_id,
        source_final_validation_digest=final.canonical_digest,
        package_digest=final.package_digest,
        approval_policy_id=policy.policy_id,
        approval_policy_digest=policy.canonical_digest,
        purpose="Approve this exact validated package for publisher governance review.",
        acknowledged_request_is_not_approval=True,
        idempotency_key=key,
        correlation_id="cor_package_approval_request",
    )


async def decide(
    service: PackageApprovalService,
    record: ConnectorPackageApprovalRecord,
    *,
    outcome: PackageApprovalOutcome = PackageApprovalOutcome.APPROVE,
    actor: AuthenticatedSubject | None = None,
    key: str = "package-approval-decision-001",
) -> ConnectorPackageApprovalRecord:
    return await service.decide(
        actor=actor or approval_operator(),
        request_id=record.request.request_id,
        expected_request_version=record.request.version,
        request_digest=record.request.canonical_digest,
        outcome=outcome,
        rationale="The exact evidence is complete and satisfies the signed approval policy.",
        acknowledged_decision_grants_no_runtime_authority=True,
        idempotency_key=key,
        correlation_id="cor_package_approval_decision",
    )


@pytest.mark.asyncio
async def test_approved_record_grants_only_publisher_governance_eligibility() -> None:
    audit = CollectingAuditSink()
    service, _, final, policy = await approval_fixture(audit_sink=audit)

    pending = await request_approval(service, final, policy)
    repeated = await request_approval(service, final, policy)
    approved = await decide(service, pending)
    repeated_decision = await decide(service, pending)

    assert pending.state is PackageApprovalState.PENDING and pending.promotion_blocked
    assert repeated.request.reused
    assert approved.state is PackageApprovalState.APPROVED and approved.approval_valid
    assert approved.connector_approved and approved.eligible_for_publisher_governance
    assert not approved.promotion_blocked and repeated_decision.decision is not None
    assert repeated_decision.decision.reused
    assert not approved.package_signed and not approved.publisher_attested
    assert not approved.connector_registered and not approved.connector_installed
    assert not approved.runtime_trust_granted and not approved.execution_authorized
    assert not approved.deployment_approved and not approved.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == [
        "connector_package_approval_requested",
        "connector_package_approval_approve",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "state"),
    (
        (PackageApprovalOutcome.REJECT, PackageApprovalState.REJECTED),
        (PackageApprovalOutcome.NEEDS_EVIDENCE, PackageApprovalState.NEEDS_EVIDENCE),
        (PackageApprovalOutcome.DEFER, PackageApprovalState.DEFERRED),
    ),
)
async def test_neutral_terminal_outcomes_remain_blocked(
    outcome: PackageApprovalOutcome, state: PackageApprovalState
) -> None:
    service, _, final, policy = await approval_fixture()
    record = await request_approval(service, final, policy)
    result = await decide(service, record, outcome=outcome, key=f"decision-{outcome.value}-001")

    assert result.state is state and result.promotion_blocked
    assert not result.approval_valid and not result.connector_approved
    assert result.connector_rejected is (outcome is PackageApprovalOutcome.REJECT)


@pytest.mark.asyncio
async def test_decision_requires_separation_and_exact_packet_binding() -> None:
    service, final_service, final, policy = await approval_fixture()
    record = await request_approval(service, final, policy)
    _, forbidden = await final_service.approval_source(validation_id=final.validation_id)
    upstream_actor = next(
        actor_id
        for actor_id in forbidden
        if actor_id not in {record.request.requested_by, policy.signed_by}
    )

    for actor in (
        final_operator(),
        approval_operator(policy.signed_by),
        approval_operator(upstream_actor),
    ):
        with pytest.raises(PackageApprovalError, match="package_approval_separation_required"):
            await decide(service, record, actor=actor, key=f"decision-{actor.subject_id}")

    with pytest.raises(PackageApprovalError, match="package_approval_decision_binding_invalid"):
        await service.decide(
            actor=approval_operator(),
            request_id=record.request.request_id,
            expected_request_version=1,
            request_digest="f" * 64,
            outcome=PackageApprovalOutcome.APPROVE,
            rationale="The exact evidence is complete and independently reviewed as required.",
            acknowledged_decision_grants_no_runtime_authority=True,
            idempotency_key="decision-binding-001",
            correlation_id="cor_package_approval_decision",
        )


@pytest.mark.asyncio
async def test_decision_is_concurrency_safe_and_audit_before_persist() -> None:
    failing, _, final, policy = await approval_fixture(audit_sink=FailingAuditSink())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await request_approval(failing, final, policy)
    assert cast(InMemoryPackageApprovalRepository, failing.repository)._requests == {}

    service, _, final, policy = await approval_fixture()
    record = await request_approval(service, final, policy)
    results = await asyncio.gather(
        decide(service, record),
        decide(service, record),
    )
    assert {item.decision.reused for item in results if item.decision} == {False, True}

    request_payload = PackageApprovalService._normalize(asdict(record.request))
    first_decision = results[0].decision
    assert first_decision is not None
    decision_payload = PackageApprovalService._normalize(asdict(first_decision))
    assert isinstance(request_payload, dict) and isinstance(decision_payload, dict)
    assert PostgreSQLPackageApprovalRepository._request_to_domain(request_payload) == record.request
    assert PostgreSQLPackageApprovalRepository._decision_to_domain(decision_payload) in (
        results[0].decision,
        results[1].decision,
    )


@pytest.mark.asyncio
async def test_expired_request_cannot_be_decided() -> None:
    service, _, final, policy = await approval_fixture()
    record = await request_approval(service, final, policy)
    service._clock = lambda: record.request.expires_at + timedelta(seconds=1)

    projected = await service.get(
        actor=approval_operator(),
        request_id=record.request.request_id,
        correlation_id="cor_package_approval_read",
    )
    assert projected.state is PackageApprovalState.EXPIRED
    assert projected.promotion_blocked and not projected.approval_valid
    with pytest.raises(PackageApprovalError, match="package_approval_request_expired"):
        await decide(service, record)


def test_package_approval_api_requires_csrf_and_minimizes_record(tmp_path: Path) -> None:
    service, final_service, final, policy = asyncio.run(approval_fixture())
    subject = final_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-approval-request-input.v1",
        "source_final_validation_id": final.validation_id,
        "source_final_validation_digest": final.canonical_digest,
        "package_digest": final.package_digest,
        "approval_policy_id": policy.policy_id,
        "approval_policy_digest": policy.canonical_digest,
        "purpose": "Approve this exact validated package for publisher governance review.",
        "acknowledged_request_is_not_approval": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_final_validation_service=final_service,
            package_approval_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-approval-requests"
        denied = client.post(
            endpoint, json=payload, headers={"Idempotency-Key": "approval-api-001"}
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "approval-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        request_id = created.json()["data"]["request"]["request_id"]
        read = client.get(f"{endpoint}/{request_id}")

    assert denied.status_code == 403 and read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["state"] == "pending" and data["promotion_blocked"] is True
    assert data["connector_approved"] is False and data["execution_authorized"] is False
    assert data["decision"] is None
    for forbidden in (
        "request_fingerprint",
        "idempotency_key",
        "forbidden_actor_ids",
        "credential_handle",
        "endpoint",
        "request_payload",
        "response_payload",
    ):
        assert forbidden not in data and forbidden not in data["request"]
