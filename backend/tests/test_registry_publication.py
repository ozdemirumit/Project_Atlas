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
from test_package_final_validation import final_operator
from test_package_signing import sign_package, signing_fixture, signing_operator

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.modules.connectors.adapters.registry_publication_memory import (
    InMemoryNonProductionRegistryPublisher,
    InMemoryRegistryPublicationPolicySource,
    InMemoryRegistryPublicationRepository,
    NonProductionHmacPackageSignatureVerifier,
)
from atlas.modules.connectors.adapters.registry_publication_postgres import (
    PostgreSQLRegistryPublicationRepository,
)
from atlas.modules.connectors.application.final_validation import PackageFinalValidationService
from atlas.modules.connectors.application.package_approval import PackageApprovalService
from atlas.modules.connectors.application.publisher_attestation import PublisherAttestationService
from atlas.modules.connectors.application.registry_publication import (
    RegistryPublicationService,
    build_development_registry_publication_policy,
)
from atlas.modules.connectors.application.registry_publication_ports import (
    RegistryPublicationError,
)
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationReceipt,
    ConnectorRegistryPublicationPolicySnapshot,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


class FailSecondAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, record: AuditRecord) -> None:
        self.records.append(record)
        if len(self.records) == 2:
            raise RuntimeError("completion audit unavailable")


def publication_operator(
    subject_id: str = "subject.package-independent-registry-publisher",
) -> AuthenticatedSubject:
    return final_operator(subject_id)


async def publication_fixture(
    *, audit_sink: CollectingAuditSink | FailingAuditSink | FailSecondAuditSink | None = None
) -> tuple[
    RegistryPublicationService,
    ConnectorRegistryPublicationPolicySnapshot,
    InMemoryNonProductionRegistryPublisher,
    NonProductionHmacPackageSignatureVerifier,
]:
    signing_service, report, signing_policy, _ = await signing_fixture()
    signing = await sign_package(signing_service, report, signing_policy)
    attestation_service = cast(PublisherAttestationService, signing_service._attestation_source)
    approval_service = cast(PackageApprovalService, attestation_service._approval_source)
    final_service = cast(PackageFinalValidationService, approval_service._final_validation_source)
    policy = build_development_registry_publication_policy(
        organization_id=signing.organization_id,
        environment_id=signing.environment_id,
        issued_at=signing.signed_at - timedelta(hours=1),
        expires_at=signing.signed_at + timedelta(days=2),
    )
    publisher = InMemoryNonProductionRegistryPublisher(
        registry_profile_id=policy.registry_profile_id,
        publisher_workload_id=policy.publisher_workload_id,
    )
    verifier = NonProductionHmacPackageSignatureVerifier(
        key_material=b"nonproduction-package-signing-key-material",
        verifier_workload_id=policy.verifier_workload_id,
    )
    service = RegistryPublicationService(
        repository=InMemoryRegistryPublicationRepository(),
        signing_source=signing_service,
        approval_source=approval_service,
        final_source=final_service,
        policy_source=InMemoryRegistryPublicationPolicySource((policy,)),
        signature_verifier=verifier,
        publisher=publisher,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=signing.environment_id,
        clock=lambda: signing.signed_at,
    )
    return service, policy, publisher, verifier


async def publish_package(
    service: RegistryPublicationService,
    policy: ConnectorRegistryPublicationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "registry-publication-001",
) -> ConnectorInternalRegistryPublicationReceipt:
    signing_service = cast(object, service._signing_source)
    repository = signing_service.repository  # type: ignore[attr-defined]
    signing = next(iter(repository._receipts.values()))
    return await service.create(
        actor=actor or publication_operator(),
        source_signing_receipt_id=signing.receipt_id,
        source_signing_receipt_digest=signing.canonical_digest,
        package_digest=signing.envelope.package_digest,
        publication_policy_id=policy.policy_id,
        publication_policy_digest=policy.canonical_digest,
        purpose="Publish this exact signed package to the governed internal registry.",
        acknowledged_publication_grants_no_runtime_authority=True,
        idempotency_key=key,
        correlation_id="cor_registry_publication",
    )


@pytest.mark.asyncio
async def test_publication_grants_only_registration_governance_eligibility() -> None:
    audit = CollectingAuditSink()
    service, policy, publisher, verifier = await publication_fixture(audit_sink=audit)

    receipt = await publish_package(service, policy)
    repeated = await publish_package(service, policy)

    assert receipt.package_published and receipt.eligible_for_registration_governance
    assert receipt.package_signed and receipt.publisher_attested and not receipt.promotion_blocked
    assert receipt.verification.signature_valid and receipt.publication.integrity_verified
    assert repeated.reused and repeated.receipt_id == receipt.receipt_id
    assert publisher.invocation_count == verifier.invocation_count == 1
    assert not receipt.connector_registered and not receipt.connector_installed
    assert not receipt.connector_enabled and not receipt.target_configured
    assert not receipt.credentials_resolved and not receipt.runtime_trust_granted
    assert not receipt.execution_authorized and not receipt.deployment_approved
    assert not receipt.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == [
        "connector_registry_publication_requested",
        "connector_registry_publication_completed",
    ]


@pytest.mark.asyncio
async def test_publication_enforces_exact_binding_and_actor_separation() -> None:
    service, policy, _, _ = await publication_fixture()
    signing_service = service._signing_source
    signing = next(iter(signing_service.repository._receipts.values()))  # type: ignore[attr-defined]
    for subject_id in (
        signing_operator().subject_id,
        policy.signed_by,
        policy.verifier_workload_id,
        policy.publisher_workload_id,
        policy.registry_custodian_id,
    ):
        with pytest.raises(RegistryPublicationError, match="separation_required"):
            await publish_package(
                service,
                policy,
                actor=publication_operator(subject_id),
                key=f"publication-{subject_id}",
            )

    with pytest.raises(RegistryPublicationError, match="binding_invalid"):
        await service.create(
            actor=publication_operator(),
            source_signing_receipt_id=signing.receipt_id,
            source_signing_receipt_digest="f" * 64,
            package_digest=signing.envelope.package_digest,
            publication_policy_id=policy.policy_id,
            publication_policy_digest=policy.canonical_digest,
            purpose="Publish this exact signed package to the governed internal registry.",
            acknowledged_publication_grants_no_runtime_authority=True,
            idempotency_key="registry-publication-binding",
            correlation_id="cor_registry_publication",
        )


@pytest.mark.asyncio
async def test_required_audits_precede_publisher_and_receipt_persistence() -> None:
    first, policy, publisher, _ = await publication_fixture(audit_sink=FailingAuditSink())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await publish_package(first, policy)
    assert publisher.invocation_count == 0
    assert first.repository._receipts == {}  # type: ignore[attr-defined]

    second_audit = FailSecondAuditSink()
    second, policy, publisher, _ = await publication_fixture(audit_sink=second_audit)
    with pytest.raises(RuntimeError, match="completion audit unavailable"):
        await publish_package(second, policy)
    assert publisher.invocation_count == 1
    assert second.repository._receipts == {}  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_registry_publication_postgres_round_trip_preserves_internal_evidence() -> None:
    service, policy, _, _ = await publication_fixture()
    receipt = await publish_package(service, policy)
    raw = RegistryPublicationService._normalize(asdict(receipt))
    assert isinstance(raw, dict)
    restored = PostgreSQLRegistryPublicationRepository._to_domain(raw)
    assert restored == receipt
    assert restored.publication.artifact_reference == receipt.publication.artifact_reference


def test_registry_publication_api_requires_csrf_and_minimizes_response(tmp_path: Path) -> None:
    service, policy, _, _ = asyncio.run(publication_fixture())
    signing_service = service._signing_source
    signing = next(iter(signing_service.repository._receipts.values()))  # type: ignore[attr-defined]
    subject = publication_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-registry-publication-input.v1",
        "source_signing_receipt_id": signing.receipt_id,
        "source_signing_receipt_digest": signing.canonical_digest,
        "package_digest": signing.envelope.package_digest,
        "publication_policy_id": policy.policy_id,
        "publication_policy_digest": policy.canonical_digest,
        "purpose": "Publish this exact signed package to the governed internal registry.",
        "acknowledged_publication_grants_no_runtime_authority": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            registry_publication_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/registry-publication-receipts"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "publish-api-001"})
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "publish-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        receipt_id = created.json()["data"]["receipt_id"]
        read = client.get(f"{endpoint}/{receipt_id}")

    assert denied.status_code == 403 and read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["package_published"] is True and data["connector_registered"] is False
    assert data["execution_authorized"] is False
    rendered = created.text.lower()
    for forbidden in (
        "signature_value",
        "key_material",
        "private_key",
        "package_bytes",
        "registry_path",
        "request_fingerprint",
        "idempotency_key",
    ):
        assert forbidden not in rendered
