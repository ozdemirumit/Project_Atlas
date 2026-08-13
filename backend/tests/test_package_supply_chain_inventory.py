from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_validation_intake import service_fixture, validate, validator

from atlas.api.app import create_app
from atlas.core.persistence.models import ConnectorPackageSupplyChainInventoryModel
from atlas.modules.connectors.adapters.acquisition_archive_memory import (
    InMemoryAcquiredPackagePublisher,
)
from atlas.modules.connectors.adapters.supply_chain_inventory_memory import (
    InMemoryPackageSupplyChainInventoryRepository,
)
from atlas.modules.connectors.adapters.supply_chain_inventory_postgres import (
    PostgreSQLPackageSupplyChainInventoryRepository,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    INVENTORY_PROFILE,
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.supply_chain_inventory_ports import (
    PackageSupplyChainInventoryError,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
    InventoryOutcome,
)
from atlas.modules.connectors.domain.validation_intake import ConnectorPackageValidation
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


def inventory_operator(
    subject_id: str = "subject.supply-chain.inventory",
    *,
    method: AuthenticationMethod = AuthenticationMethod.LDAP,
    assurance: AssuranceLevel = AssuranceLevel.MULTI_FACTOR,
    kind: SubjectKind = SubjectKind.HUMAN,
) -> AuthenticatedSubject:
    return validator(subject_id, method=method, assurance=assurance, kind=kind)


async def inventory_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
    overrides: dict[str, str] | None = None,
    additions: dict[str, str] | None = None,
) -> tuple[
    PackageSupplyChainInventoryService,
    PackageValidationService,
    ConnectorPackageValidation,
    InMemoryPackageSupplyChainInventoryRepository,
]:
    validation_service, acquisition, _, _ = await service_fixture(
        overrides=overrides, additions=additions
    )
    validation = await validate(validation_service, acquisition)
    repository = InMemoryPackageSupplyChainInventoryRepository()
    service = PackageSupplyChainInventoryService(
        repository=repository,
        validation_source=validation_service.repository,
        acquisition_source=validation_service.acquisition_source,
        archive_source=validation_service.archive_source,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id="environment.development",
        clock=lambda: validation.validated_at,
    )
    return service, validation_service, validation, repository


async def inventory(
    service: PackageSupplyChainInventoryService,
    validation: ConnectorPackageValidation,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "package-inventory-test-001",
) -> ConnectorPackageSupplyChainInventory:
    return await service.create(
        actor=subject or inventory_operator(),
        source_validation_id=validation.validation_id,
        source_validation_digest=validation.canonical_digest,
        package_digest=validation.package_digest,
        inventory_profile=INVENTORY_PROFILE,
        acknowledged_untrusted_package_content=True,
        idempotency_key=key,
        correlation_id="cor_package_inventory_test",
    )


@pytest.mark.asyncio
async def test_inventories_content_and_dependencies_idempotently_without_authority() -> None:
    audit = CollectingAuditSink()
    service, _, validation, repository = await inventory_fixture(audit_sink=audit)

    first = await inventory(service, validation)
    second = await inventory(service, validation)

    assert first.outcome is InventoryOutcome.PASSED
    assert len(first.files) == 13
    assert first.build_dependency_count == 1
    assert first.runtime_dependency_count == 0
    assert second == replace(first, reused=True)
    assert (
        await repository.get_by_validation(source_validation_id=validation.validation_id) == first
    )
    assert not first.vulnerability_scan_completed
    assert not first.malware_scan_completed
    assert not first.connector_registered
    assert not first.runtime_trust_granted
    assert not first.execution_authorized
    assert not first.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == ["connector_package_inventory_passed"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "assurance"),
    [
        (AuthenticationMethod.DEVELOPMENT, AssuranceLevel.DEVELOPMENT),
        (AuthenticationMethod.LDAP, AssuranceLevel.SINGLE_FACTOR),
    ],
)
async def test_allows_human_inventory_operator_without_fixed_assurance(
    method: AuthenticationMethod,
    assurance: AssuranceLevel,
) -> None:
    service, _, validation, _ = await inventory_fixture()

    report = await inventory(
        service,
        validation,
        subject=inventory_operator(method=method, assurance=assurance),
    )

    assert report.outcome is InventoryOutcome.PASSED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "additions", "failed_check"),
    [
        (None, {"unexpected.bin": "bounded but unsupported"}, 2),
        ({"pyproject.toml": "[project\ninvalid = true"}, None, 3),
    ],
)
async def test_content_or_metadata_defect_creates_failed_report(
    overrides: dict[str, str] | None,
    additions: dict[str, str] | None,
    failed_check: int,
) -> None:
    service, _, validation, repository = await inventory_fixture(
        overrides=overrides, additions=additions
    )

    report = await inventory(service, validation)

    assert report.outcome is InventoryOutcome.FAILED
    assert report.checks[failed_check].state.value == "failed"
    assert (
        await repository.get_by_validation(source_validation_id=validation.validation_id) == report
    )


@pytest.mark.asyncio
async def test_archive_corruption_fails_without_creating_inventory() -> None:
    service, validation_service, validation, repository = await inventory_fixture()
    archive_source = cast(InMemoryAcquiredPackagePublisher, validation_service.archive_source)
    archive_source._archives[validation.package_digest] = b"changed"

    with pytest.raises(PackageSupplyChainInventoryError) as caught:
        await inventory(service, validation)

    assert caught.value.code == "package_inventory_archive_integrity_failed"
    assert await repository.get_by_validation(source_validation_id=validation.validation_id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subject",
    [
        inventory_operator("subject.package.validator"),
        inventory_operator("subject.registry.intake"),
        inventory_operator("subject.package.custodian"),
        inventory_operator("subject.domain.reviewer"),
        inventory_operator("subject.security.reviewer"),
        inventory_operator("subject.lab.operator"),
    ],
)
async def test_rejects_non_independent_operator(
    subject: AuthenticatedSubject,
) -> None:
    service, _, validation, _ = await inventory_fixture()

    with pytest.raises(PackageSupplyChainInventoryError):
        await inventory(service, validation, subject=subject)


@pytest.mark.asyncio
async def test_rejects_non_human_inventory_operator() -> None:
    service, _, validation, repository = await inventory_fixture()

    with pytest.raises(PackageSupplyChainInventoryError) as caught:
        await inventory(
            service,
            validation,
            subject=inventory_operator(kind=SubjectKind.SERVICE),
        )

    assert caught.value.code == "package_inventory_human_required"
    assert repository._records == {}


@pytest.mark.asyncio
async def test_audit_failure_does_not_create_inventory() -> None:
    service, _, validation, repository = await inventory_fixture(audit_sink=FailingAuditSink())

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await inventory(service, validation)

    assert await repository.get_by_validation(source_validation_id=validation.validation_id) is None


@pytest.mark.asyncio
async def test_concurrent_inventory_produces_one_report() -> None:
    service, _, validation, repository = await inventory_fixture()

    first, second = await asyncio.gather(
        inventory(service, validation), inventory(service, validation)
    )

    assert first.inventory_id == second.inventory_id
    assert {first.reused, second.reused} == {False, True}
    assert len(repository._records) == 1


@pytest.mark.asyncio
async def test_postgres_mapping_preserves_inventory() -> None:
    service, _, validation, _ = await inventory_fixture()
    report = await inventory(service, validation)
    row = ConnectorPackageSupplyChainInventoryModel(
        **PostgreSQLPackageSupplyChainInventoryRepository._values(report)
    )

    assert PostgreSQLPackageSupplyChainInventoryRepository._to_domain(row) == report


def test_inventory_api_requires_csrf_and_returns_safe_report(tmp_path: Path) -> None:
    service, validation_service, validation, _ = asyncio.run(inventory_fixture())
    subject = inventory_operator()
    provider = BasicTestIdentityProvider(subject)
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-supply-chain-inventory-request.v1",
        "source_validation_id": validation.validation_id,
        "source_validation_digest": validation.canonical_digest,
        "package_digest": validation.package_digest,
        "inventory_profile": INVENTORY_PROFILE,
        "acknowledged_untrusted_package_content": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=provider,
            package_validation_service=validation_service,
            package_supply_chain_inventory_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-supply-chain-inventories"
        denied = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "package-inventory-api-001"},
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "package-inventory-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        inventory_id = created.json()["data"]["inventory_id"]
        read = client.get(f"{endpoint}/{inventory_id}")

    assert denied.status_code == 403
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["outcome"] == "passed"
    assert len(data["files"]) == 13
    assert read.json()["data"]["canonical_digest"] == data["canonical_digest"]
    for field in (
        "vulnerability_scan_completed",
        "malware_scan_completed",
        "connector_registered",
        "connector_installed",
        "runtime_trust_granted",
        "execution_authorized",
        "infrastructure_mutation_performed",
    ):
        assert data[field] is False
