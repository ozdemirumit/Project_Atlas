from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_approval import (
    approval_fixture,
    approval_operator,
    decide,
    request_approval,
)
from test_package_final_validation import final_operator

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.publisher_attestation_memory import (
    InMemoryPublisherAttestationPolicySource,
    InMemoryPublisherAttestationRepository,
    InMemoryPublisherClaimSource,
)
from atlas.modules.connectors.adapters.publisher_attestation_postgres import (
    PostgreSQLPublisherAttestationRepository,
)
from atlas.modules.connectors.application.publisher_attestation import (
    PublisherAttestationService,
    build_development_publisher_attestation_policy,
)
from atlas.modules.connectors.application.publisher_attestation_ports import (
    PublisherAttestationError,
)
from atlas.modules.connectors.domain.package_approval import ConnectorPackageApprovalRecord
from atlas.modules.connectors.domain.publisher_attestation import (
    ConnectorPublisherAttestationPolicySnapshot,
    ConnectorPublisherAttestationReport,
    ConnectorPublisherClaimSnapshot,
    PublisherAttestationOutcome,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


def attestation_operator(
    subject_id: str = "subject.publisher-independent-verifier",
) -> AuthenticatedSubject:
    return final_operator(subject_id)


def claim_for(
    approved: ConnectorPackageApprovalRecord,
    *,
    ownership: bool = True,
    support: bool = True,
) -> ConnectorPublisherClaimSnapshot:
    now = approved.decision.decided_at if approved.decision else approved.request.created_at
    claim = ConnectorPublisherClaimSnapshot(
        claim_id="connector-publisher-claim.development",
        schema_version="atlas.connector-publisher-claim.v1",
        version=1,
        organization_id=approved.request.organization_id,
        environment_id=approved.request.environment_id,
        publisher_id="publisher.atlas-labs",
        publisher_display_name="Atlas Labs",
        connector_id="connector.hitachi-ops-center",
        release_version="version.1.0.0",
        package_digest=approved.request.package_digest,
        provenance_digest="7" * 64,
        ownership_asserted=ownership,
        support_responsibility_asserted=support,
        support_contact_ref="support-contact.atlas-labs",
        support_expires_at=now + timedelta(days=365),
        issued_by="subject.publisher-claim-authority",
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=365),
        signature_verified=True,
        grants_no_runtime_authority=True,
        canonical_digest="0" * 64,
    )
    payload = asdict(claim)
    payload.pop("canonical_digest")
    return replace(
        claim,
        canonical_digest=PublisherAttestationService._digest(
            PublisherAttestationService._normalize(payload)
        ),
    )


async def attestation_fixture(
    *,
    ownership: bool = True,
    support: bool = True,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
) -> tuple[
    PublisherAttestationService,
    ConnectorPackageApprovalRecord,
    ConnectorPublisherClaimSnapshot,
    ConnectorPublisherAttestationPolicySnapshot,
]:
    approval_service, _, final, approval_policy = await approval_fixture()
    pending = await request_approval(approval_service, final, approval_policy)
    approved = await decide(approval_service, pending)
    claim = claim_for(approved, ownership=ownership, support=support)
    now = approved.decision.decided_at if approved.decision else approved.request.created_at
    policy = build_development_publisher_attestation_policy(
        organization_id=approved.request.organization_id,
        environment_id=approved.request.environment_id,
        issued_at=now - timedelta(hours=2),
        expires_at=now + timedelta(days=2),
    )
    service = PublisherAttestationService(
        repository=InMemoryPublisherAttestationRepository(),
        approval_source=approval_service,
        claim_source=InMemoryPublisherClaimSource((claim,)),
        policy_source=InMemoryPublisherAttestationPolicySource((policy,)),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=approved.request.environment_id,
        clock=lambda: now,
    )
    return service, approved, claim, policy


async def attest(
    service: PublisherAttestationService,
    approved: ConnectorPackageApprovalRecord,
    claim: ConnectorPublisherClaimSnapshot,
    policy: ConnectorPublisherAttestationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "publisher-attestation-001",
) -> ConnectorPublisherAttestationReport:
    return await service.create(
        actor=actor or attestation_operator(),
        source_approval_request_id=approved.request.request_id,
        source_approval_request_digest=approved.request.canonical_digest,
        package_digest=approved.request.package_digest,
        publisher_claim_id=claim.claim_id,
        publisher_claim_digest=claim.canonical_digest,
        attestation_policy_id=policy.policy_id,
        attestation_policy_digest=policy.canonical_digest,
        purpose="Independently verify publisher identity and package provenance evidence.",
        acknowledged_attestation_grants_no_lifecycle_authority=True,
        idempotency_key=key,
        correlation_id="cor_publisher_attestation",
    )


@pytest.mark.asyncio
async def test_verified_attestation_grants_only_signing_governance_eligibility() -> None:
    audit = CollectingAuditSink()
    service, approved, claim, policy = await attestation_fixture(audit_sink=audit)

    report = await attest(service, approved, claim, policy)
    repeated = await attest(service, approved, claim, policy)

    assert report.outcome is PublisherAttestationOutcome.VERIFIED
    assert report.publisher_attested and report.eligible_for_package_signing_governance
    assert not report.promotion_blocked and repeated.reused
    assert not report.package_signed and not report.connector_registered
    assert not report.connector_installed and not report.connector_enabled
    assert not report.target_configured and not report.credentials_resolved
    assert not report.runtime_trust_granted and not report.execution_authorized
    assert not report.deployment_approved and not report.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == [
        "connector_publisher_attestation_verified"
    ]


@pytest.mark.asyncio
async def test_missing_publisher_assertions_create_rejected_evidence() -> None:
    service, approved, claim, policy = await attestation_fixture(ownership=False, support=False)
    report = await attest(service, approved, claim, policy)

    assert report.outcome is PublisherAttestationOutcome.REJECTED
    assert report.reason_codes == (
        "reason.ownership.not_asserted",
        "reason.support.not_asserted",
    )
    assert report.promotion_blocked and not report.publisher_attested


@pytest.mark.asyncio
async def test_attestation_enforces_separation_binding_and_audit_before_persist() -> None:
    service, approved, claim, policy = await attestation_fixture()
    for actor in (
        final_operator(),
        approval_operator(),
        attestation_operator(claim.issued_by),
        attestation_operator(claim.publisher_id),
        attestation_operator(policy.signed_by),
    ):
        with pytest.raises(PublisherAttestationError, match="separation_required"):
            await attest(
                service, approved, claim, policy, actor=actor, key=f"key-{actor.subject_id}"
            )

    with pytest.raises(PublisherAttestationError, match="binding_invalid"):
        await service.create(
            actor=attestation_operator(),
            source_approval_request_id=approved.request.request_id,
            source_approval_request_digest="f" * 64,
            package_digest=approved.request.package_digest,
            publisher_claim_id=claim.claim_id,
            publisher_claim_digest=claim.canonical_digest,
            attestation_policy_id=policy.policy_id,
            attestation_policy_digest=policy.canonical_digest,
            purpose="Independently verify publisher identity and package provenance evidence.",
            acknowledged_attestation_grants_no_lifecycle_authority=True,
            idempotency_key="publisher-attestation-binding",
            correlation_id="cor_publisher_attestation",
        )

    failing, approved, claim, policy = await attestation_fixture(audit_sink=FailingAuditSink())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await attest(failing, approved, claim, policy)
    assert failing.repository._reports == {}  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_attestation_postgres_round_trip_mapping() -> None:
    service, approved, claim, policy = await attestation_fixture()
    report = await attest(service, approved, claim, policy)
    raw = PublisherAttestationService._normalize(asdict(report))
    assert isinstance(raw, dict)
    assert PostgreSQLPublisherAttestationRepository._to_domain(raw) == report


def test_publisher_attestation_api_requires_csrf_and_minimizes_report(tmp_path: Path) -> None:
    service, approved, claim, policy = asyncio.run(attestation_fixture())
    subject = attestation_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-publisher-attestation-input.v1",
        "source_approval_request_id": approved.request.request_id,
        "source_approval_request_digest": approved.request.canonical_digest,
        "package_digest": approved.request.package_digest,
        "publisher_claim_id": claim.claim_id,
        "publisher_claim_digest": claim.canonical_digest,
        "attestation_policy_id": policy.policy_id,
        "attestation_policy_digest": policy.canonical_digest,
        "purpose": "Independently verify publisher identity and package provenance evidence.",
        "acknowledged_attestation_grants_no_lifecycle_authority": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            publisher_attestation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/publisher-attestations"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "attest-api-001"})
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "attest-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        report_id = created.json()["data"]["report_id"]
        read = client.get(f"{endpoint}/{report_id}")

    assert denied.status_code == 403 and read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["outcome"] == "verified" and data["publisher_attested"] is True
    assert data["package_signed"] is False and data["execution_authorized"] is False
    for forbidden in (
        "request_fingerprint",
        "idempotency_key",
        "forbidden_actor_ids",
        "private_key",
        "credential",
        "command",
        "payload",
    ):
        assert forbidden not in data
