from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_malware_analysis import analyze as malware_analyze
from test_package_malware_analysis import malware_fixture, malware_operator
from test_package_schema_semantics_validation import schema_operator

from atlas.api.app import create_app
from atlas.core.persistence.models import ConnectorPackageLicenseAnalysisModel
from atlas.modules.connectors.adapters.license_analysis_memory import (
    InMemoryPackageLicenseAnalysisRepository,
    StaticLicensePolicySnapshotProvider,
)
from atlas.modules.connectors.adapters.license_analysis_postgres import (
    PostgreSQLPackageLicenseAnalysisRepository,
)
from atlas.modules.connectors.application.authority_behavior_validation import (
    PackageAuthorityBehaviorValidationService,
)
from atlas.modules.connectors.application.license_analysis import (
    LICENSE_ANALYSIS_PROFILE,
    LICENSE_ANALYZER,
    LICENSE_POLICY_SNAPSHOT_SCHEMA,
    PackageLicenseAnalysisService,
)
from atlas.modules.connectors.application.license_analysis_ports import (
    PackageLicenseAnalysisError,
)
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
from atlas.modules.connectors.domain.license_analysis import (
    ConnectorPackageLicenseAnalysis,
    LicenseDisposition,
    LicenseOutcome,
    LicensePolicyRecord,
    LicensePolicySnapshot,
    LicenseSubjectScope,
)
from atlas.modules.connectors.domain.malware_analysis import ConnectorPackageMalwareAnalysis
from atlas.modules.identity.domain.models import AuthenticatedSubject


def license_operator(subject_id: str = "subject.license.analyst") -> AuthenticatedSubject:
    return schema_operator(subject_id)


async def represented_subjects(
    source: ConnectorPackageMalwareAnalysis,
    semantics_service: PackageSchemaSemanticsValidationService,
) -> tuple[tuple[LicenseSubjectScope, str], ...]:
    inventory_source = semantics_service.inventory_source
    acquisition_source = semantics_service.acquisition_source
    archive_source = semantics_service.archive_source
    inventory = await inventory_source.get_by_id(inventory_id=source.source_inventory_id)
    acquisition = await acquisition_source.get_by_id(acquisition_id=source.source_acquisition_id)
    assert inventory is not None and acquisition is not None
    content = await archive_source.read(
        package_digest=source.package_digest,
        size_bytes=source.package_size_bytes,
    )
    files, _ = PackageValidationService._verify_archive(acquisition, content)
    return PackageLicenseAnalysisService._subjects(inventory, files)


def policy_snapshot(
    source: ConnectorPackageMalwareAnalysis,
    subjects: tuple[tuple[LicenseSubjectScope, str], ...],
    *,
    disposition_for: dict[LicenseSubjectScope, LicenseDisposition] | None = None,
    obligations_for: dict[LicenseSubjectScope, tuple[str, ...]] | None = None,
    omit_scope: LicenseSubjectScope | None = None,
    expired: bool = False,
    signature_verified: bool = True,
    coverage_complete: bool = True,
) -> LicensePolicySnapshot:
    dispositions = disposition_for or {}
    obligations = obligations_for or {}
    records = tuple(
        sorted(
            (
                LicensePolicyRecord(
                    rule_id=f"LICENSE-{scope.value.upper()}-{index:04d}",
                    category="license-policy",
                    subject_scope=scope,
                    subject_fingerprint=fingerprint,
                    disposition=dispositions.get(scope, LicenseDisposition.PERMITTED),
                    obligations=obligations.get(scope, ()),
                )
                for index, (scope, fingerprint) in enumerate(subjects, start=1)
                if scope is not omit_scope
            ),
            key=lambda item: (item.subject_scope, item.subject_fingerprint, item.rule_id),
        )
    )
    issued_at = source.analyzed_at - timedelta(days=2)
    expires_at = (
        source.analyzed_at - timedelta(days=1)
        if expired
        else source.analyzed_at + timedelta(days=2)
    )
    snapshot = LicensePolicySnapshot(
        snapshot_id="license-policy-snapshot.test.v1",
        schema_version=LICENSE_POLICY_SNAPSHOT_SCHEMA,
        snapshot_version="snapshot.test.v1",
        organization_id=source.organization_id,
        environment_id=source.environment_id,
        analysis_profile=LICENSE_ANALYSIS_PROFILE,
        analyzer_version=LICENSE_ANALYZER,
        issued_at=issued_at,
        expires_at=expires_at,
        package_coverage_complete=coverage_complete,
        source_coverage_complete=coverage_complete,
        dependency_coverage_complete=coverage_complete,
        obligation_coverage_complete=coverage_complete,
        signing_key_id="signing-key.test.v1",
        signature_verified=signature_verified,
        records=records,
        canonical_digest="0" * 64,
    )
    return replace(
        snapshot,
        canonical_digest=PackageLicenseAnalysisService._digest(
            PackageLicenseAnalysisService._snapshot_payload(snapshot)
        ),
    )


async def license_fixture(
    *,
    snapshot_factory: Callable[
        [ConnectorPackageMalwareAnalysis, tuple[tuple[LicenseSubjectScope, str], ...]],
        LicensePolicySnapshot,
    ]
    | None = None,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
) -> tuple[
    PackageLicenseAnalysisService,
    tuple[
        PackageMalwareAnalysisService,
        PackageVulnerabilityAnalysisService,
        PackageStaticDependencyAnalysisService,
        PackageAuthorityBehaviorValidationService,
        PackageSchemaSemanticsValidationService,
        PackageSupplyChainInventoryService,
        object,
        object,
    ],
    ConnectorPackageMalwareAnalysis,
]:
    malware_parts = await malware_fixture()
    malware_service = malware_parts[0]
    vulnerability_source = malware_parts[6]
    source = await malware_analyze(malware_service, vulnerability_source)
    semantics_service = malware_parts[4]
    subjects = await represented_subjects(source, semantics_service)
    snapshot = (
        snapshot_factory(source, subjects)
        if snapshot_factory is not None
        else policy_snapshot(
            source,
            subjects,
            obligations_for={
                LicenseSubjectScope.PACKAGE: ("internal-use-only",),
                LicenseSubjectScope.SOURCE: ("internal-use-only",),
            },
        )
    )
    service = PackageLicenseAnalysisService(
        repository=InMemoryPackageLicenseAnalysisRepository(),
        malware_source=malware_service.repository,
        inventory_source=semantics_service.inventory_source,
        acquisition_source=semantics_service.acquisition_source,
        archive_source=semantics_service.archive_source,
        policy_provider=StaticLicensePolicySnapshotProvider(snapshot),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id="environment.development",
        clock=lambda: source.analyzed_at,
    )
    return service, malware_parts, source


async def analyze(
    service: PackageLicenseAnalysisService,
    source: ConnectorPackageMalwareAnalysis,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "license-test-001",
) -> ConnectorPackageLicenseAnalysis:
    return await service.create(
        actor=subject or license_operator(),
        source_malware_analysis_id=source.analysis_id,
        source_malware_analysis_digest=source.canonical_digest,
        package_digest=source.package_digest,
        analysis_profile=LICENSE_ANALYSIS_PROFILE,
        acknowledged_policy_not_legal_advice=True,
        idempotency_key=key,
        correlation_id="cor_license_test",
    )


@pytest.mark.asyncio
async def test_complete_permitted_policy_passes_without_runtime_authority() -> None:
    audit = CollectingAuditSink()
    service, _, source = await license_fixture(audit_sink=audit)

    first = await analyze(service, source)
    second = await analyze(service, source)

    assert first.outcome is LicenseOutcome.PASSED
    assert not first.promotion_blocked
    assert first.findings == ()
    assert first.policy_snapshot.fresh
    assert first.subject_summary.package_subject_count == 1
    assert first.subject_summary.source_subject_count == 1
    assert first.subject_summary.build_dependency_count >= 1
    assert first.subject_summary.permitted_count == first.subject_summary.scanned_subject_count
    assert first.subject_summary.unsatisfied_obligation_count == 0
    assert first.malware_scan_completed and first.license_scan_completed
    assert not first.contract_validation_completed
    assert not first.runtime_trust_granted
    assert not first.execution_authorized
    assert second == replace(first, reused=True)
    assert [item.result_code for item in audit.records] == ["connector_license_analysis_passed"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("factory", "count_field"),
    (
        (
            lambda source, subjects: policy_snapshot(
                source,
                subjects,
                disposition_for={LicenseSubjectScope.BUILD: LicenseDisposition.PROHIBITED},
            ),
            "prohibited_count",
        ),
        (
            lambda source, subjects: policy_snapshot(
                source, subjects, omit_scope=LicenseSubjectScope.BUILD
            ),
            "unknown_count",
        ),
        (
            lambda source, subjects: policy_snapshot(
                source,
                subjects,
                obligations_for={LicenseSubjectScope.BUILD: ("publish-source",)},
            ),
            "unsatisfied_obligation_count",
        ),
    ),
)
async def test_blocking_policy_results_are_minimized(
    factory: Callable[
        [ConnectorPackageMalwareAnalysis, tuple[tuple[LicenseSubjectScope, str], ...]],
        LicensePolicySnapshot,
    ],
    count_field: str,
) -> None:
    service, _, source = await license_fixture(snapshot_factory=factory)
    report = await analyze(service, source)

    assert report.outcome is LicenseOutcome.FAILED
    assert report.promotion_blocked
    assert getattr(report.subject_summary, count_field) > 0
    serialized = repr(report).lower()
    assert "setuptools" not in serialized
    assert "license_id" not in serialized
    assert "license body" not in serialized
    assert "reviewer_notes" not in serialized


@pytest.mark.asyncio
async def test_stale_policy_fails_but_untrusted_policy_creates_no_report() -> None:
    stale, _, stale_source = await license_fixture(
        snapshot_factory=lambda source, subjects: policy_snapshot(source, subjects, expired=True)
    )
    stale_report = await analyze(stale, stale_source)
    assert stale_report.outcome is LicenseOutcome.FAILED
    assert any(item.rule_id == "ATLAS-LICENSE-POLICY-EXPIRED" for item in stale_report.findings)

    untrusted, _, untrusted_source = await license_fixture(
        snapshot_factory=lambda source, subjects: policy_snapshot(
            source, subjects, signature_verified=False
        )
    )
    with pytest.raises(PackageLicenseAnalysisError, match="package_license_policy_untrusted"):
        await analyze(untrusted, untrusted_source)
    assert untrusted.repository._records == {}  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_separation_audit_concurrency_and_postgres_mapping() -> None:
    service, _, source = await license_fixture()
    with pytest.raises(PackageLicenseAnalysisError):
        await analyze(service, source, subject=malware_operator())

    failing, _, failing_source = await license_fixture(audit_sink=FailingAuditSink())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await analyze(failing, failing_source)
    assert failing.repository._records == {}  # type: ignore[attr-defined]

    concurrent, _, concurrent_source = await license_fixture()
    first, second = await asyncio.gather(
        analyze(concurrent, concurrent_source), analyze(concurrent, concurrent_source)
    )
    assert first.analysis_id == second.analysis_id
    assert {first.reused, second.reused} == {False, True}

    row = ConnectorPackageLicenseAnalysisModel(
        **PostgreSQLPackageLicenseAnalysisRepository._values(first)
    )
    assert PostgreSQLPackageLicenseAnalysisRepository._to_domain(row) == first


def test_license_api_requires_csrf_and_returns_minimized_report(tmp_path: Path) -> None:
    service, malware_parts, source = asyncio.run(license_fixture())
    (
        malware_service,
        vulnerability_service,
        static_service,
        behavior_service,
        semantics_service,
        inventory_service,
        _,
        _,
    ) = malware_parts
    subject = license_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-license-analysis-request.v1",
        "source_malware_analysis_id": source.analysis_id,
        "source_malware_analysis_digest": source.canonical_digest,
        "package_digest": source.package_digest,
        "analysis_profile": LICENSE_ANALYSIS_PROFILE,
        "acknowledged_policy_not_legal_advice": True,
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
            package_license_analysis_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-license-analyses"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "license-api-01"})
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "license-api-01",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        analysis_id = created.json()["data"]["analysis_id"]
        read = client.get(f"{endpoint}/{analysis_id}")

    assert denied.status_code == 403
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["outcome"] == "passed"
    assert data["malware_scan_completed"] is True
    assert data["license_scan_completed"] is True
    assert all(
        key not in data
        for key in (
            "license_text",
            "source_license_id",
            "dependency_names",
            "policy_records",
            "reviewer_notes",
            "exceptions",
            "paths",
        )
    )
