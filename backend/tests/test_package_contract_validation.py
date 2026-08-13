from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_license_analysis import analyze as license_analyze
from test_package_license_analysis import license_fixture, license_operator
from test_package_malware_analysis import malware_operator

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.contract_validation_memory import (
    InMemoryPackageContractValidationRepository,
)
from atlas.modules.connectors.adapters.contract_validation_postgres import (
    PostgreSQLPackageContractValidationRepository,
)
from atlas.modules.connectors.application.authority_behavior_validation import (
    PackageAuthorityBehaviorValidationService,
)
from atlas.modules.connectors.application.contract_validation import (
    CONTRACT_VALIDATION_PROFILE,
    PackageContractValidationService,
)
from atlas.modules.connectors.application.contract_validation_ports import (
    PackageContractValidationError,
)
from atlas.modules.connectors.application.license_analysis import PackageLicenseAnalysisService
from atlas.modules.connectors.application.malware_analysis import PackageMalwareAnalysisService
from atlas.modules.connectors.application.schema_semantics_validation import (
    PackageSchemaSemanticsValidationService,
)
from atlas.modules.connectors.application.static_dependency_analysis import (
    PackageStaticDependencyAnalysisService,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.application.vulnerability_analysis import (
    PackageVulnerabilityAnalysisService,
)
from atlas.modules.connectors.domain.contract_validation import (
    ConnectorPackageContractValidation,
    ContractOutcome,
)
from atlas.modules.connectors.domain.license_analysis import ConnectorPackageLicenseAnalysis
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

ContractFixtureParts = tuple[
    PackageMalwareAnalysisService,
    PackageVulnerabilityAnalysisService,
    PackageStaticDependencyAnalysisService,
    PackageAuthorityBehaviorValidationService,
    PackageSchemaSemanticsValidationService,
    PackageSupplyChainInventoryService,
    object,
    object,
    PackageLicenseAnalysisService,
]


def contract_operator(subject_id: str = "subject.contract.validator") -> AuthenticatedSubject:
    return license_operator(subject_id)


async def contract_fixture(
    *, audit_sink: CollectingAuditSink | FailingAuditSink | None = None
) -> tuple[
    PackageContractValidationService,
    ContractFixtureParts,
    ConnectorPackageLicenseAnalysis,
]:
    license_service, malware_parts, malware_source = await license_fixture()
    source = await license_analyze(license_service, malware_source)
    semantics_service = malware_parts[4]
    service = PackageContractValidationService(
        repository=InMemoryPackageContractValidationRepository(),
        license_source=license_service.repository,
        inventory_source=semantics_service.inventory_source,
        acquisition_source=semantics_service.acquisition_source,
        archive_source=semantics_service.archive_source,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id="environment.development",
        clock=lambda: source.analyzed_at,
    )
    return service, (*malware_parts, license_service), source


async def validate(
    service: PackageContractValidationService,
    source: ConnectorPackageLicenseAnalysis,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "contract-test-001",
) -> ConnectorPackageContractValidation:
    return await service.create(
        actor=subject or contract_operator(),
        source_license_analysis_id=source.analysis_id,
        source_license_analysis_digest=source.canonical_digest,
        package_digest=source.package_digest,
        validation_profile=CONTRACT_VALIDATION_PROFILE,
        acknowledged_static_contract_only=True,
        idempotency_key=key,
        correlation_id="cor_contract_test",
    )


@pytest.mark.asyncio
async def test_exact_generated_contract_passes_without_execution_authority() -> None:
    audit = CollectingAuditSink()
    service, _, source = await contract_fixture(audit_sink=audit)

    first = await validate(service, source)
    second = await validate(service, source)

    assert first.outcome is ContractOutcome.PASSED
    assert not first.promotion_blocked
    assert first.contract_validation_completed
    assert not first.runner_validation_completed
    assert not first.runtime_trust_granted
    assert not first.execution_authorized
    assert not first.infrastructure_mutation_performed
    assert first.coverage.capability_count >= 1
    assert first.coverage.covered_capability_count == first.coverage.capability_count
    assert first.coverage.orphan_artifact_count == 0
    assert first.findings == ()
    assert second.validation_id == first.validation_id and second.reused
    assert audit.records[-1].event_type == "atlas.connector.package-contract-validation"
    exposed = asdict(first)
    for forbidden in (
        "source_code",
        "test_body",
        "fixture_payload",
        "schema_properties",
        "capability_ids",
        "paths",
        "parser_diagnostics",
    ):
        assert forbidden not in exposed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "assurance"),
    [
        (AuthenticationMethod.DEVELOPMENT, AssuranceLevel.DEVELOPMENT),
        (AuthenticationMethod.LDAP, AssuranceLevel.SINGLE_FACTOR),
    ],
)
async def test_human_eligibility_does_not_require_fixed_assurance(
    method: AuthenticationMethod,
    assurance: AssuranceLevel,
) -> None:
    service, _, source = await contract_fixture()
    subject = replace(contract_operator(), authentication_method=method, assurance_level=assurance)

    report = await validate(service, source, subject=subject)

    assert report.outcome is ContractOutcome.PASSED


@pytest.mark.asyncio
async def test_contract_validation_rejects_non_human_actor() -> None:
    service, _, source = await contract_fixture()
    subject = replace(contract_operator(), kind=SubjectKind.SERVICE)

    with pytest.raises(PackageContractValidationError, match="package_contract_human_required"):
        await validate(service, source, subject=subject)


@pytest.mark.asyncio
async def test_static_contract_families_fail_closed_for_tampering() -> None:
    service, parts, source = await contract_fixture()
    semantics_service = parts[4]
    inventory = await semantics_service.inventory_source.get_by_id(
        inventory_id=source.source_inventory_id
    )
    acquisition = await semantics_service.acquisition_source.get_by_id(
        acquisition_id=source.source_acquisition_id
    )
    assert inventory is not None and acquisition is not None
    archive = await semantics_service.archive_source.read(
        package_digest=source.package_digest, size_bytes=source.package_size_bytes
    )
    files, _ = PackageValidationService._verify_archive(acquisition, archive)

    valid_coverage, valid_findings, valid_results = service._analyze(files)
    assert valid_coverage.covered_capability_count == valid_coverage.capability_count
    assert valid_findings == () and all(valid_results.values())

    handler_path = next(
        path
        for path in files
        if path.startswith("src/atlas_generated_connector/capabilities/")
        and not path.endswith("/__init__.py")
    )
    tampered_handler = dict(files)
    tampered_handler[handler_path] += b"\nprint('must never execute')\n"
    _, findings, results = service._analyze(tampered_handler)
    assert not results["contract.handlers.binding"]
    assert findings and all("print" not in item.summary for item in findings)

    test_path = next(path for path in files if path.startswith("tests/contract/"))
    tampered_test = dict(files)
    tampered_test[test_path] += b"\nimport os\n"
    _, _, results = service._analyze(tampered_test)
    assert not results["contract.tests.synthetic"]

    fixture_path = next(path for path in files if path.startswith("tests/fixtures/"))
    tampered_fixture = dict(files)
    tampered_fixture[fixture_path] = b'{"target_connected":true}'
    _, _, results = service._analyze(tampered_fixture)
    assert not results["contract.tests.synthetic"]

    orphaned = dict(files)
    orphaned["schemas/inputs/orphan.schema.json"] = b"{}"
    coverage, _, results = service._analyze(orphaned)
    assert coverage.orphan_artifact_count == 1
    assert not results["contract.coverage.complete"]


@pytest.mark.asyncio
async def test_separation_audit_concurrency_and_postgres_equivalence() -> None:
    service, _, source = await contract_fixture()
    with pytest.raises(PackageContractValidationError):
        await validate(service, source, subject=malware_operator())

    failing, _, failing_source = await contract_fixture(audit_sink=FailingAuditSink())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await validate(failing, failing_source)
    assert failing.repository._records == {}  # type: ignore[attr-defined]

    concurrent, _, concurrent_source = await contract_fixture()
    first, second = await asyncio.gather(
        validate(concurrent, concurrent_source), validate(concurrent, concurrent_source)
    )
    assert first.validation_id == second.validation_id
    assert {first.reused, second.reused} == {False, True}

    payload = PackageContractValidationService._normalize(
        PackageContractValidationService._canonical_payload_with_internal_fields(first)
    )
    restored = PostgreSQLPackageContractValidationRepository._to_domain(
        cast(dict[str, object], payload)
    )
    assert restored == first


def test_contract_api_requires_csrf_and_returns_minimized_report(tmp_path: Path) -> None:
    service, parts, source = asyncio.run(contract_fixture())
    (
        malware_service,
        vulnerability_service,
        static_service,
        behavior_service,
        semantics_service,
        inventory_service,
        _,
        _,
        license_service,
    ) = parts
    subject = contract_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-contract-validation-request.v1",
        "source_license_analysis_id": source.analysis_id,
        "source_license_analysis_digest": source.canonical_digest,
        "package_digest": source.package_digest,
        "validation_profile": CONTRACT_VALIDATION_PROFILE,
        "acknowledged_static_contract_only": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_supply_chain_inventory_service=inventory_service,
            package_schema_semantics_validation_service=semantics_service,
            package_authority_behavior_validation_service=behavior_service,
            package_static_dependency_analysis_service=static_service,
            package_vulnerability_analysis_service=vulnerability_service,
            package_malware_analysis_service=malware_service,
            package_license_analysis_service=license_service,
            package_contract_validation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-contract-validations"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "contract-api-01"})
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "contract-api-01",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        validation_id = created.json()["data"]["validation_id"]
        read = client.get(f"{endpoint}/{validation_id}")

    assert denied.status_code == 403
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["outcome"] == "passed"
    assert data["license_scan_completed"] is True
    assert data["contract_validation_completed"] is True
    assert data["runner_validation_completed"] is False
    for forbidden in (
        "source_code",
        "test_body",
        "fixture_payload",
        "schema_properties",
        "capability_ids",
        "paths",
        "parser_diagnostics",
    ):
        assert forbidden not in data
