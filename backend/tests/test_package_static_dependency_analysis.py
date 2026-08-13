from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_authority_behavior_validation import (
    behavior_fixture,
    behavior_operator,
    compare,
    reviewed_package_overrides,
)
from test_package_schema_semantics_validation import schema_operator

from atlas.api.app import create_app
from atlas.core.persistence.models import ConnectorPackageStaticDependencyAnalysisModel
from atlas.modules.connectors.adapters.static_dependency_analysis_memory import (
    InMemoryPackageStaticDependencyAnalysisRepository,
)
from atlas.modules.connectors.adapters.static_dependency_analysis_postgres import (
    PostgreSQLPackageStaticDependencyAnalysisRepository,
)
from atlas.modules.connectors.application.authority_behavior_validation import (
    PackageAuthorityBehaviorValidationService,
)
from atlas.modules.connectors.application.schema_semantics_validation import (
    PackageSchemaSemanticsValidationService,
)
from atlas.modules.connectors.application.static_dependency_analysis import (
    STATIC_DEPENDENCY_PROFILE,
    PackageStaticDependencyAnalysisService,
)
from atlas.modules.connectors.application.static_dependency_analysis_ports import (
    PackageStaticDependencyAnalysisError,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.domain.authority_behavior_validation import (
    ConnectorPackageAuthorityBehaviorValidation,
)
from atlas.modules.connectors.domain.static_dependency_analysis import (
    ConnectorPackageStaticDependencyAnalysis,
    StaticDependencyCategory,
    StaticDependencyOutcome,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


def static_operator(
    subject_id: str = "subject.static-dependency.analyst",
) -> AuthenticatedSubject:
    return behavior_operator(subject_id)


async def static_fixture(
    *,
    overrides: dict[str, str] | None = None,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
) -> tuple[
    PackageStaticDependencyAnalysisService,
    PackageAuthorityBehaviorValidationService,
    PackageSchemaSemanticsValidationService,
    PackageSupplyChainInventoryService,
    ConnectorPackageAuthorityBehaviorValidation,
    InMemoryPackageStaticDependencyAnalysisRepository,
]:
    (
        behavior_service,
        semantics_service,
        inventory_service,
        schema_source,
        _,
    ) = await behavior_fixture(overrides=overrides or reviewed_package_overrides())
    source = await compare(behavior_service, schema_source)
    assert source.outcome.value == "passed"
    repository = InMemoryPackageStaticDependencyAnalysisRepository()
    service = PackageStaticDependencyAnalysisService(
        repository=repository,
        authority_behavior_source=behavior_service.repository,
        inventory_source=semantics_service.inventory_source,
        acquisition_source=semantics_service.acquisition_source,
        archive_source=semantics_service.archive_source,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id="environment.development",
        clock=lambda: source.validated_at,
    )
    return (
        service,
        behavior_service,
        semantics_service,
        inventory_service,
        source,
        repository,
    )


async def analyze(
    service: PackageStaticDependencyAnalysisService,
    source: ConnectorPackageAuthorityBehaviorValidation,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "static-dependency-test-001",
) -> ConnectorPackageStaticDependencyAnalysis:
    return await service.create(
        actor=subject or static_operator(),
        source_authority_behavior_validation_id=source.validation_id,
        source_authority_behavior_validation_digest=source.canonical_digest,
        package_digest=source.package_digest,
        analysis_profile=STATIC_DEPENDENCY_PROFILE,
        acknowledged_offline_static_dependency_limitations=True,
        idempotency_key=key,
        correlation_id="cor_static_dependency_test",
    )


@pytest.mark.asyncio
async def test_reviewed_source_and_empty_runtime_dependencies_pass_without_authority() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, source, repository = await static_fixture(audit_sink=audit)

    first = await analyze(service, source)
    second = await analyze(service, source)

    assert first.outcome is StaticDependencyOutcome.PASSED
    assert not first.promotion_blocked
    assert first.findings == ()
    assert first.source_summary.source_file_count > 0
    assert first.source_summary.unresolved_import_count == 0
    assert first.dependency_summary.runtime_dependency_count == 0
    assert not first.dependency_summary.dependency_lock_required
    assert first.dependency_summary.metadata_consistent
    assert first.dependency_summary.imports_reconciled
    assert first.dependency_summary.deterministic_constraints
    assert first.static_code_validation_completed
    assert not first.vulnerability_scan_completed
    assert not first.runtime_trust_granted
    assert not first.execution_authorized
    assert not first.infrastructure_mutation_performed
    assert second == replace(first, reused=True)
    assert len(repository._records) == 1
    assert [item.result_code for item in audit.records] == [
        "connector_static_dependency_analysis_passed"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "assurance"),
    [
        (AuthenticationMethod.DEVELOPMENT, AssuranceLevel.DEVELOPMENT),
        (AuthenticationMethod.LDAP, AssuranceLevel.SINGLE_FACTOR),
    ],
)
async def test_allows_human_static_analyst_without_fixed_assurance(
    method: AuthenticationMethod,
    assurance: AssuranceLevel,
) -> None:
    service, _, _, _, source, _ = await static_fixture()
    subject = replace(
        static_operator(),
        authentication_method=method,
        assurance_level=assurance,
    )

    report = await analyze(service, source, subject=subject)

    assert report.outcome is StaticDependencyOutcome.PASSED


@pytest.mark.asyncio
async def test_rejects_non_human_static_analyst() -> None:
    service, _, _, _, source, repository = await static_fixture()

    with pytest.raises(PackageStaticDependencyAnalysisError) as caught:
        await analyze(
            service,
            source,
            subject=replace(static_operator(), kind=SubjectKind.SERVICE),
        )

    assert caught.value.code == "package_static_dependency_human_required"
    assert repository._records == {}


@pytest.mark.asyncio
async def test_bare_exception_and_mutable_global_fail_without_source_disclosure() -> None:
    marker = "private-static-marker-should-not-leak"
    source_code = (
        '"""Reviewed bounded capability."""\n\n'
        "from typing import Any\n\n"
        f'STATE = ["{marker}"]\n'
        'CAPABILITY_ID = "capability.storage.health.read"\n'
        'CAPABILITY_CLASS = "C1"\n'
        'REQUIRED_PERMISSION = "storage.health.read"\n\n'
        "async def handle(_input: dict[str, Any]) -> dict[str, str]:\n"
        "    try:\n"
        '        return {"status": "healthy"}\n'
        "    except:\n"
        "        pass\n"
        '    return {"status": "unknown"}\n'
    )
    service, _, _, _, source, _ = await static_fixture(
        overrides=reviewed_package_overrides(source_code)
    )

    report = await analyze(service, source)

    assert report.outcome is StaticDependencyOutcome.FAILED
    assert report.promotion_blocked
    assert any(
        item.category is StaticDependencyCategory.EXCEPTION_HANDLING for item in report.findings
    )
    assert any(
        item.category is StaticDependencyCategory.STATE_MANAGEMENT for item in report.findings
    )
    assert marker not in repr(report)


@pytest.mark.asyncio
async def test_separation_audit_failure_and_concurrency_preserve_one_to_one() -> None:
    service, _, _, _, source, repository = await static_fixture()
    with pytest.raises(PackageStaticDependencyAnalysisError):
        await analyze(service, source, subject=schema_operator())
    assert repository._records == {}

    failing, _, _, _, failing_source, failing_repository = await static_fixture(
        audit_sink=FailingAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await analyze(failing, failing_source)
    assert failing_repository._records == {}

    concurrent, _, _, _, concurrent_source, concurrent_repository = await static_fixture()
    first, second = await asyncio.gather(
        analyze(concurrent, concurrent_source), analyze(concurrent, concurrent_source)
    )
    assert first.analysis_id == second.analysis_id
    assert {first.reused, second.reused} == {False, True}
    assert len(concurrent_repository._records) == 1


@pytest.mark.asyncio
async def test_postgres_mapping_preserves_static_dependency_report() -> None:
    service, _, _, _, source, _ = await static_fixture()
    report = await analyze(service, source)
    row = ConnectorPackageStaticDependencyAnalysisModel(
        **PostgreSQLPackageStaticDependencyAnalysisRepository._values(report)
    )
    assert PostgreSQLPackageStaticDependencyAnalysisRepository._to_domain(row) == report


def test_static_dependency_api_requires_csrf_and_returns_minimized_report(
    tmp_path: Path,
) -> None:
    service, behavior_service, semantics_service, inventory_service, source, _ = asyncio.run(
        static_fixture()
    )
    subject = static_operator()
    provider = BasicTestIdentityProvider(subject)
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-static-dependency-analysis-request.v1",
        "source_authority_behavior_validation_id": source.validation_id,
        "source_authority_behavior_validation_digest": source.canonical_digest,
        "package_digest": source.package_digest,
        "analysis_profile": STATIC_DEPENDENCY_PROFILE,
        "acknowledged_offline_static_dependency_limitations": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=provider,
            package_supply_chain_inventory_service=inventory_service,
            package_schema_semantics_validation_service=semantics_service,
            package_authority_behavior_validation_service=behavior_service,
            package_static_dependency_analysis_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-static-dependency-analyses"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "static-api-001"})
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "static-api-001",
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
    assert data["findings"] == []
    assert data["static_code_validation_completed"] is True
    assert all(
        key not in data
        for key in (
            "source",
            "source_code",
            "tokens",
            "imports",
            "dependencies",
            "constraints",
        )
    )
