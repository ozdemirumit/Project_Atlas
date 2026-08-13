from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_final_validation import final_operator
from test_publisher_attestation import attest, attestation_fixture, attestation_operator

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.modules.connectors.adapters.package_signing_memory import (
    InMemoryPackageSigningPolicySource,
    InMemoryPackageSigningRepository,
    NonProductionHmacPackageSigner,
)
from atlas.modules.connectors.adapters.package_signing_postgres import (
    PostgreSQLPackageSigningRepository,
)
from atlas.modules.connectors.application.package_signing import (
    PackageSigningService,
    build_development_package_signing_policy,
)
from atlas.modules.connectors.application.package_signing_ports import PackageSigningError
from atlas.modules.connectors.domain.package_signing import (
    ConnectorPackageSigningPolicySnapshot,
    ConnectorPackageSigningReceipt,
)
from atlas.modules.connectors.domain.publisher_attestation import (
    ConnectorPublisherAttestationReport,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


class FailSecondAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, record: AuditRecord) -> None:
        self.records.append(record)
        if len(self.records) == 2:
            raise RuntimeError("completion audit unavailable")


def signing_operator(
    subject_id: str = "subject.package-independent-signing-requester",
) -> AuthenticatedSubject:
    return final_operator(subject_id)


async def signing_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | FailSecondAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    PackageSigningService,
    ConnectorPublisherAttestationReport,
    ConnectorPackageSigningPolicySnapshot,
    NonProductionHmacPackageSigner,
]:
    attestation_service, approved, claim, attestation_policy = await attestation_fixture()
    report = await attest(attestation_service, approved, claim, attestation_policy)
    policy = build_development_package_signing_policy(
        organization_id=report.organization_id,
        environment_id=report.environment_id,
        issued_at=report.verified_at - timedelta(hours=1),
        expires_at=report.verified_at + timedelta(days=2),
    )
    if required_assurance_level is not policy.required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        payload = asdict(policy)
        payload.pop("canonical_digest")
        policy = replace(
            policy,
            canonical_digest=PackageSigningService._digest(
                PackageSigningService._normalize(payload)
            ),
        )
    signer = NonProductionHmacPackageSigner(
        key_material=b"nonproduction-package-signing-key-material",
        signer_workload_id=policy.signer_workload_id,
    )
    service = PackageSigningService(
        repository=InMemoryPackageSigningRepository(),
        attestation_source=attestation_service,
        policy_source=InMemoryPackageSigningPolicySource((policy,)),
        signer=signer,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=report.environment_id,
        clock=lambda: report.verified_at,
    )
    return service, report, policy, signer


async def sign_package(
    service: PackageSigningService,
    report: ConnectorPublisherAttestationReport,
    policy: ConnectorPackageSigningPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "package-signing-001",
) -> ConnectorPackageSigningReceipt:
    return await service.create(
        actor=actor or signing_operator(),
        source_attestation_report_id=report.report_id,
        source_attestation_report_digest=report.canonical_digest,
        package_digest=report.package_digest,
        signing_policy_id=policy.policy_id,
        signing_policy_digest=policy.canonical_digest,
        purpose="Sign this exact attested package for later registry governance review.",
        acknowledged_signing_grants_no_runtime_authority=True,
        idempotency_key=key,
        correlation_id="cor_package_signing",
    )


@pytest.mark.asyncio
async def test_package_signature_grants_only_registry_governance_eligibility() -> None:
    audit = CollectingAuditSink()
    service, report, policy, signer = await signing_fixture(audit_sink=audit)

    receipt = await sign_package(service, report, policy)
    repeated = await sign_package(service, report, policy)

    assert receipt.publisher_attested and receipt.package_signed
    assert receipt.eligible_for_registry_governance and not receipt.promotion_blocked
    assert receipt.signature.signature_verified and signer.invocation_count == 1
    assert (
        repeated.reused
        and repeated.signature.signature_digest == receipt.signature.signature_digest
    )
    assert not receipt.connector_registered and not receipt.connector_installed
    assert not receipt.connector_enabled and not receipt.target_configured
    assert not receipt.credentials_resolved and not receipt.runtime_trust_granted
    assert not receipt.execution_authorized and not receipt.deployment_approved
    assert not receipt.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == [
        "connector_package_signing_requested",
        "connector_package_signing_completed",
    ]


@pytest.mark.asyncio
async def test_signing_optional_step_up_policy_and_human_boundary() -> None:
    service, report, policy, _ = await signing_fixture()
    development_actor = replace(
        signing_operator(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    receipt = await sign_package(service, report, policy, actor=development_actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert receipt.requested_by == development_actor.subject_id

    hardware_service, hardware_report, hardware_policy, _ = await signing_fixture(
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED
    )
    with pytest.raises(PackageSigningError, match="binding_invalid"):
        await sign_package(
            hardware_service,
            hardware_report,
            hardware_policy,
            actor=development_actor,
        )

    non_human_service, non_human_report, non_human_policy, _ = await signing_fixture()
    with pytest.raises(PackageSigningError, match="human_required"):
        await sign_package(
            non_human_service,
            non_human_report,
            non_human_policy,
            actor=replace(
                signing_operator(),
                kind=SubjectKind.SERVICE,
                authentication_method=AuthenticationMethod.WORKLOAD_TOKEN,
            ),
        )


@pytest.mark.asyncio
async def test_signing_enforces_binding_and_complete_actor_separation() -> None:
    service, report, policy, _ = await signing_fixture()
    for subject_id in (
        attestation_operator().subject_id,
        report.publisher_id,
        report.claim_issued_by,
        policy.signed_by,
        policy.signer_workload_id,
        policy.key_custodian_id,
    ):
        with pytest.raises(PackageSigningError, match="separation_required"):
            await sign_package(
                service,
                report,
                policy,
                actor=signing_operator(subject_id),
                key=f"signing-{subject_id}",
            )

    with pytest.raises(PackageSigningError, match="binding_invalid"):
        await service.create(
            actor=signing_operator(),
            source_attestation_report_id=report.report_id,
            source_attestation_report_digest="f" * 64,
            package_digest=report.package_digest,
            signing_policy_id=policy.policy_id,
            signing_policy_digest=policy.canonical_digest,
            purpose="Sign this exact attested package for later registry governance review.",
            acknowledged_signing_grants_no_runtime_authority=True,
            idempotency_key="package-signing-binding",
            correlation_id="cor_package_signing",
        )


@pytest.mark.asyncio
async def test_required_audits_surround_signer_and_precede_persistence() -> None:
    first_fails, report, policy, signer = await signing_fixture(audit_sink=FailingAuditSink())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await sign_package(first_fails, report, policy)
    assert signer.invocation_count == 0
    assert first_fails.repository._receipts == {}  # type: ignore[attr-defined]

    second_audit = FailSecondAuditSink()
    second_fails, report, policy, signer = await signing_fixture(audit_sink=second_audit)
    with pytest.raises(RuntimeError, match="completion audit unavailable"):
        await sign_package(second_fails, report, policy)
    assert signer.invocation_count == 1
    assert second_fails.repository._receipts == {}  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_signing_postgres_round_trip_preserves_internal_signature() -> None:
    service, report, policy, _ = await signing_fixture()
    receipt = await sign_package(service, report, policy)
    raw = PackageSigningService._normalize(asdict(receipt))
    assert isinstance(raw, dict)
    restored = PostgreSQLPackageSigningRepository._to_domain(raw)
    assert restored == receipt
    assert restored.signature.signature_value == receipt.signature.signature_value


def test_package_signing_api_requires_csrf_and_hides_signature_value(tmp_path: Path) -> None:
    service, report, policy, _ = asyncio.run(signing_fixture())
    subject = signing_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-signing-input.v1",
        "source_attestation_report_id": report.report_id,
        "source_attestation_report_digest": report.canonical_digest,
        "package_digest": report.package_digest,
        "signing_policy_id": policy.policy_id,
        "signing_policy_digest": policy.canonical_digest,
        "purpose": "Sign this exact attested package for later registry governance review.",
        "acknowledged_signing_grants_no_runtime_authority": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_signing_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-signing-receipts"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "sign-api-001"})
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "sign-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        receipt_id = created.json()["data"]["receipt_id"]
        read = client.get(f"{endpoint}/{receipt_id}")

    assert denied.status_code == 403 and read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["package_signed"] is True and data["connector_registered"] is False
    assert data["execution_authorized"] is False
    assert "signature_value" not in data["signature"]
    rendered = created.text.lower()
    for forbidden in (
        "key_material",
        "private_key",
        "secret",
        "signature_value",
        "request_fingerprint",
        "idempotency_key",
    ):
        assert forbidden not in rendered
