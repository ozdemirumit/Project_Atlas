from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_supply_chain_inventory import (
    inventory,
    inventory_fixture,
    inventory_operator,
)

from atlas.api.app import create_app
from atlas.core.persistence.models import ConnectorPackageContentPolicyScanModel
from atlas.modules.connectors.adapters.acquisition_archive_memory import (
    InMemoryAcquiredPackagePublisher,
)
from atlas.modules.connectors.adapters.content_policy_scan_memory import (
    InMemoryPackageContentPolicyScanRepository,
)
from atlas.modules.connectors.adapters.content_policy_scan_postgres import (
    PostgreSQLPackageContentPolicyScanRepository,
)
from atlas.modules.connectors.application.content_policy_scan import (
    CONTENT_POLICY_PROFILE,
    PackageContentPolicyScanService,
)
from atlas.modules.connectors.application.content_policy_scan_ports import (
    PackageContentPolicyScanError,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.domain.content_policy_scan import (
    ConnectorPackageContentPolicyScan,
    ContentPolicyFindingKind,
    ContentPolicyOutcome,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


def content_policy_operator(
    subject_id: str = "subject.content-policy.scanner",
    *,
    method: AuthenticationMethod = AuthenticationMethod.LDAP,
    assurance: AssuranceLevel = AssuranceLevel.MULTI_FACTOR,
    kind: SubjectKind = SubjectKind.HUMAN,
) -> AuthenticatedSubject:
    return inventory_operator(subject_id, method=method, assurance=assurance, kind=kind)


async def content_policy_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
    overrides: dict[str, str] | None = None,
) -> tuple[
    PackageContentPolicyScanService,
    PackageSupplyChainInventoryService,
    ConnectorPackageSupplyChainInventory,
    InMemoryPackageContentPolicyScanRepository,
]:
    inventory_service, _, validation, _ = await inventory_fixture(overrides=overrides)
    source_inventory = await inventory(inventory_service, validation)
    repository = InMemoryPackageContentPolicyScanRepository()
    service = PackageContentPolicyScanService(
        repository=repository,
        inventory_source=inventory_service.repository,
        acquisition_source=inventory_service.acquisition_source,
        archive_source=inventory_service.archive_source,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id="environment.development",
        clock=lambda: source_inventory.inventoried_at,
    )
    return service, inventory_service, source_inventory, repository


async def scan(
    service: PackageContentPolicyScanService,
    source_inventory: ConnectorPackageSupplyChainInventory,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "content-policy-scan-test-001",
) -> ConnectorPackageContentPolicyScan:
    return await service.create(
        actor=subject or content_policy_operator(),
        source_inventory_id=source_inventory.inventory_id,
        source_inventory_digest=source_inventory.canonical_digest,
        package_digest=source_inventory.package_digest,
        scan_profile=CONTENT_POLICY_PROFILE,
        acknowledged_untrusted_package_content=True,
        idempotency_key=key,
        correlation_id="cor_content_policy_test",
    )


@pytest.mark.asyncio
async def test_scans_clean_package_idempotently_without_authority() -> None:
    audit = CollectingAuditSink()
    service, _, source_inventory, repository = await content_policy_fixture(audit_sink=audit)

    first = await scan(service, source_inventory)
    second = await scan(service, source_inventory)

    assert first.outcome is ContentPolicyOutcome.PASSED
    assert first.scanned_file_count == 13
    assert first.findings == ()
    assert not first.promotion_blocked
    assert first.secret_content_scan_completed
    assert first.prohibited_content_scan_completed
    assert not first.malware_scan_completed
    assert not first.static_code_validation_completed
    assert not first.connector_rejected
    assert not first.connector_registered
    assert not first.runtime_trust_granted
    assert not first.execution_authorized
    assert not first.infrastructure_mutation_performed
    assert second == replace(first, reused=True)
    assert (
        await repository.get_by_inventory(source_inventory_id=source_inventory.inventory_id)
        == first
    )
    assert [item.result_code for item in audit.records] == ["connector_content_policy_scan_passed"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("readme", "kind", "rule"),
    [
        (
            "password = " + "Sup3r" + "SyntheticValue",
            ContentPolicyFindingKind.EMBEDDED_SECRET,
            "secret.embedded.sensitive-assignment",
        ),
        (
            "-----BEGIN " + "PRIVATE KEY-----\nsynthetic\n-----END PRIVATE KEY-----",
            ContentPolicyFindingKind.EMBEDDED_SECRET,
            "secret.embedded.private-key",
        ),
        (
            "PK\x03\x04synthetic nested content",
            ContentPolicyFindingKind.PROHIBITED_CONTENT,
            "content.prohibited.nested-archive",
        ),
    ],
)
async def test_secret_or_prohibited_content_creates_safe_failed_report(
    readme: str,
    kind: ContentPolicyFindingKind,
    rule: str,
) -> None:
    service, _, source_inventory, repository = await content_policy_fixture(
        overrides={"README.md": readme}
    )

    report = await scan(service, source_inventory)

    assert report.outcome is ContentPolicyOutcome.FAILED
    assert report.promotion_blocked
    assert any(item.kind is kind and item.rule_code == rule for item in report.findings)
    assert readme not in repr(report)
    assert (
        await repository.get_by_inventory(source_inventory_id=source_inventory.inventory_id)
        == report
    )


@pytest.mark.asyncio
async def test_secret_references_and_placeholders_are_not_secret_values() -> None:
    service, _, source_inventory, _ = await content_policy_fixture(
        overrides={
            "README.md": (
                "password = placeholder\n"
                "client_secret = secret.connector.runtime\n"
                "credential_ref = secret.connector.runtime\n"
            )
        }
    )

    report = await scan(service, source_inventory)

    assert report.outcome is ContentPolicyOutcome.PASSED
    assert report.findings == ()


@pytest.mark.asyncio
async def test_archive_corruption_fails_without_creating_scan() -> None:
    service, inventory_service, source_inventory, repository = await content_policy_fixture()
    archive_source = cast(InMemoryAcquiredPackagePublisher, inventory_service.archive_source)
    archive_source._archives[source_inventory.package_digest] = b"changed"

    with pytest.raises(PackageContentPolicyScanError) as caught:
        await scan(service, source_inventory)

    assert caught.value.code == "package_content_policy_archive_integrity_failed"
    assert (
        await repository.get_by_inventory(source_inventory_id=source_inventory.inventory_id) is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subject",
    [
        content_policy_operator("subject.package.validator"),
        content_policy_operator("subject.registry.intake"),
        content_policy_operator("subject.supply-chain.inventory"),
        content_policy_operator("subject.package.custodian"),
        content_policy_operator("subject.domain.reviewer"),
        content_policy_operator("subject.security.reviewer"),
        content_policy_operator("subject.lab.operator"),
        content_policy_operator(
            method=AuthenticationMethod.DEVELOPMENT,
            assurance=AssuranceLevel.DEVELOPMENT,
        ),
        content_policy_operator(kind=SubjectKind.SERVICE),
    ],
)
async def test_rejects_non_independent_or_non_enterprise_operator(
    subject: AuthenticatedSubject,
) -> None:
    service, _, source_inventory, _ = await content_policy_fixture()

    with pytest.raises(PackageContentPolicyScanError):
        await scan(service, source_inventory, subject=subject)


@pytest.mark.asyncio
async def test_audit_failure_does_not_create_scan() -> None:
    service, _, source_inventory, repository = await content_policy_fixture(
        audit_sink=FailingAuditSink()
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await scan(service, source_inventory)

    assert (
        await repository.get_by_inventory(source_inventory_id=source_inventory.inventory_id) is None
    )


@pytest.mark.asyncio
async def test_concurrent_scan_produces_one_report() -> None:
    service, _, source_inventory, repository = await content_policy_fixture()

    first, second = await asyncio.gather(
        scan(service, source_inventory), scan(service, source_inventory)
    )

    assert first.scan_id == second.scan_id
    assert {first.reused, second.reused} == {False, True}
    assert len(repository._records) == 1


@pytest.mark.asyncio
async def test_postgres_mapping_preserves_content_policy_scan() -> None:
    service, _, source_inventory, _ = await content_policy_fixture()
    report = await scan(service, source_inventory)
    row = ConnectorPackageContentPolicyScanModel(
        **PostgreSQLPackageContentPolicyScanRepository._values(report)
    )

    assert PostgreSQLPackageContentPolicyScanRepository._to_domain(row) == report


def test_content_policy_api_requires_csrf_and_returns_safe_report(tmp_path: Path) -> None:
    service, inventory_service, source_inventory, _ = asyncio.run(content_policy_fixture())
    subject = content_policy_operator()
    provider = BasicTestIdentityProvider(subject)
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-content-policy-scan-request.v1",
        "source_inventory_id": source_inventory.inventory_id,
        "source_inventory_digest": source_inventory.canonical_digest,
        "package_digest": source_inventory.package_digest,
        "scan_profile": CONTENT_POLICY_PROFILE,
        "acknowledged_untrusted_package_content": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=provider,
            package_supply_chain_inventory_service=inventory_service,
            package_content_policy_scan_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-content-policy-scans"
        denied = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "content-policy-api-001"},
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "content-policy-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        scan_id = created.json()["data"]["scan_id"]
        read = client.get(f"{endpoint}/{scan_id}")

    assert denied.status_code == 403
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["outcome"] == "passed"
    assert data["findings"] == []
    assert not data["promotion_blocked"]
    assert read.json()["data"]["canonical_digest"] == data["canonical_digest"]
    for field in (
        "vulnerability_scan_completed",
        "malware_scan_completed",
        "connector_rejected",
        "connector_registered",
        "runtime_trust_granted",
        "execution_authorized",
        "infrastructure_mutation_performed",
    ):
        assert data[field] is False


def test_failed_content_policy_api_never_returns_matched_value(tmp_path: Path) -> None:
    matched_value = "Synthetic" + "CredentialValue"
    service, inventory_service, source_inventory, _ = asyncio.run(
        content_policy_fixture(overrides={"README.md": f"password = {matched_value}"})
    )
    subject = content_policy_operator()
    provider = BasicTestIdentityProvider(subject)
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-content-policy-scan-request.v1",
        "source_inventory_id": source_inventory.inventory_id,
        "source_inventory_digest": source_inventory.canonical_digest,
        "package_digest": source_inventory.package_digest,
        "scan_profile": CONTENT_POLICY_PROFILE,
        "acknowledged_untrusted_package_content": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=provider,
            package_supply_chain_inventory_service=inventory_service,
            package_content_policy_scan_service=service,
        )
    ) as client:
        login_response = login(client)
        created = client.post(
            "/api/v1/connectors/package-content-policy-scans",
            json=payload,
            headers={
                "Idempotency-Key": "content-policy-secret-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )

    assert created.status_code == 201
    assert created.json()["data"]["outcome"] == "failed"
    assert created.json()["data"]["promotion_blocked"] is True
    assert matched_value not in created.text
