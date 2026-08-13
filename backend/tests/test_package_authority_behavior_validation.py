from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_content_policy_scan import content_policy_operator
from test_package_schema_semantics_validation import (
    canonical,
    reviewed_schema_overrides,
    schema_operator,
    semantics_fixture,
    validate,
)

from atlas.api.app import create_app
from atlas.core.persistence.models import ConnectorPackageAuthorityBehaviorValidationModel
from atlas.modules.connectors.adapters.authority_behavior_validation_memory import (
    InMemoryPackageAuthorityBehaviorValidationRepository,
)
from atlas.modules.connectors.adapters.authority_behavior_validation_postgres import (
    PostgreSQLPackageAuthorityBehaviorValidationRepository,
)
from atlas.modules.connectors.application.authority_behavior_validation import (
    AUTHORITY_BEHAVIOR_PROFILE,
    PackageAuthorityBehaviorValidationService,
)
from atlas.modules.connectors.application.authority_behavior_validation_ports import (
    PackageAuthorityBehaviorValidationError,
)
from atlas.modules.connectors.application.schema_semantics_validation import (
    PackageSchemaSemanticsValidationService,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.domain.authority_behavior_validation import (
    AuthorityBehaviorOutcome,
    BehaviorCategory,
    ConnectorPackageAuthorityBehaviorValidation,
)
from atlas.modules.connectors.domain.schema_semantics_validation import (
    ConnectorPackageSchemaSemanticsValidation,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

MODULE_PATH = "src/atlas_generated_connector/capabilities/capability_read.py"


def reviewed_source(body: str = '    return {"status": "healthy"}\n') -> str:
    return (
        '"""Reviewed bounded capability."""\n\n'
        "from typing import Any\n\n"
        'CAPABILITY_ID = "capability.storage.health.read"\n'
        'CAPABILITY_CLASS = "C1"\n'
        'REQUIRED_PERMISSION = "storage.health.read"\n\n'
        "async def handle(_input: dict[str, Any]) -> dict[str, str]:\n"
        f"{body}"
    )


def reviewed_package_overrides(source: str | None = None) -> dict[str, str]:
    return {
        **reviewed_schema_overrides(),
        MODULE_PATH: source or reviewed_source(),
        "tests/contract/test_capability_read.py": (
            "import json\nfrom pathlib import Path\n\n"
            "def test_capability_contract() -> None:\n"
            "    fixture = json.loads(\n"
            "        Path('tests/fixtures/capability_read.json').read_text(encoding='utf-8')\n"
            "    )\n"
            "    assert fixture['classification'] == 'synthetic'\n"
            "    assert fixture['target_connected'] is False\n"
            "    assert fixture['secret_values_present'] is False\n"
            "    assert fixture['schema_version'] == 'atlas.generated.capability-fixture.v1'\n"
        ),
        "tests/fixtures/capability_read.json": canonical(
            {
                "schema_version": "atlas.generated.capability-fixture.v1",
                "classification": "synthetic",
                "target_connected": False,
                "secret_values_present": False,
                "capability_id": "capability.storage.health.read",
                "input": {"target_id": "synthetic-target"},
                "expected_output": {"status": "healthy"},
            }
        ),
    }


def behavior_operator(
    subject_id: str = "subject.authority-behavior.validator",
) -> AuthenticatedSubject:
    return content_policy_operator(subject_id)


async def behavior_fixture(
    *,
    overrides: dict[str, str] | None = None,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
) -> tuple[
    PackageAuthorityBehaviorValidationService,
    PackageSchemaSemanticsValidationService,
    PackageSupplyChainInventoryService,
    ConnectorPackageSchemaSemanticsValidation,
    InMemoryPackageAuthorityBehaviorValidationRepository,
]:
    (
        semantics_service,
        _content_service,
        inventory_service,
        source_scan,
        _,
    ) = await semantics_fixture(overrides=overrides or reviewed_package_overrides())
    source = await validate(semantics_service, source_scan)
    assert source.outcome.value == "passed"
    repository = InMemoryPackageAuthorityBehaviorValidationRepository()
    service = PackageAuthorityBehaviorValidationService(
        repository=repository,
        schema_semantics_source=semantics_service.repository,
        inventory_source=semantics_service.inventory_source,
        acquisition_source=semantics_service.acquisition_source,
        archive_source=semantics_service.archive_source,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id="environment.development",
        clock=lambda: source.validated_at,
    )
    return service, semantics_service, inventory_service, source, repository


async def compare(
    service: PackageAuthorityBehaviorValidationService,
    source: ConnectorPackageSchemaSemanticsValidation,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "authority-behavior-test-001",
) -> ConnectorPackageAuthorityBehaviorValidation:
    return await service.create(
        actor=subject or behavior_operator(),
        source_schema_semantics_validation_id=source.validation_id,
        source_schema_semantics_validation_digest=source.canonical_digest,
        package_digest=source.package_digest,
        validation_profile=AUTHORITY_BEHAVIOR_PROFILE,
        acknowledged_static_analysis_limitations=True,
        idempotency_key=key,
        correlation_id="cor_authority_behavior_test",
    )


@pytest.mark.asyncio
async def test_reviewed_read_only_behavior_passes_without_authority() -> None:
    audit = CollectingAuditSink()
    service, _, _, source, repository = await behavior_fixture(audit_sink=audit)

    first = await compare(service, source)
    second = await compare(service, source)

    assert first.outcome is AuthorityBehaviorOutcome.PASSED
    assert not first.promotion_blocked
    assert first.findings == ()
    assert first.capabilities[0].observed_categories == (BehaviorCategory.READ,)
    assert first.capabilities[0].declaration_matches
    assert first.capabilities[0].permission_matches
    assert first.capabilities[0].behavior_compatible
    assert first.capabilities[0].statically_resolved
    assert first.permission_behavior_validation_completed
    assert not first.static_code_validation_completed
    assert not first.runtime_trust_granted
    assert not first.execution_authorized
    assert not first.infrastructure_mutation_performed
    assert second == replace(first, reused=True)
    assert len(repository._records) == 1
    assert [item.result_code for item in audit.records] == [
        "connector_authority_behavior_validation_passed"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "assurance"),
    [
        (AuthenticationMethod.DEVELOPMENT, AssuranceLevel.DEVELOPMENT),
        (AuthenticationMethod.LDAP, AssuranceLevel.SINGLE_FACTOR),
    ],
)
async def test_allows_human_behavior_validator_without_fixed_assurance(
    method: AuthenticationMethod,
    assurance: AssuranceLevel,
) -> None:
    service, _, _, source, _ = await behavior_fixture()
    subject = replace(
        behavior_operator(),
        authentication_method=method,
        assurance_level=assurance,
    )

    report = await compare(service, source, subject=subject)

    assert report.outcome is AuthorityBehaviorOutcome.PASSED


@pytest.mark.asyncio
async def test_rejects_non_human_behavior_validator() -> None:
    service, _, _, source, repository = await behavior_fixture()

    with pytest.raises(PackageAuthorityBehaviorValidationError) as caught:
        await compare(
            service,
            source,
            subject=replace(behavior_operator(), kind=SubjectKind.SERVICE),
        )

    assert caught.value.code == "package_authority_behavior_human_required"
    assert repository._records == {}


@pytest.mark.asyncio
async def test_unreviewed_network_and_dynamic_behavior_fail_without_source_disclosure() -> None:
    marker = "https://private-target.example.invalid:443/secret-path"
    source_code = reviewed_source(
        "    import httpx\n"
        f'    response = httpx.get("{marker}")\n'
        '    return {"status": str(response.status_code)}\n'
    )
    service, _, _, source, _ = await behavior_fixture(
        overrides=reviewed_package_overrides(source_code)
    )

    report = await compare(service, source)

    assert report.outcome is AuthorityBehaviorOutcome.FAILED
    assert report.promotion_blocked
    assert any(item.rule_code == "behavior.network.not-enabled" for item in report.findings)
    assert BehaviorCategory.NETWORK in report.capabilities[0].observed_categories
    assert marker not in repr(report)
    assert "private-target" not in repr(report)


@pytest.mark.asyncio
async def test_dynamic_execution_fails_closed() -> None:
    source_code = reviewed_source('    return {"status": str(eval("1 + 1"))}\n')
    service, _, _, source, _ = await behavior_fixture(
        overrides=reviewed_package_overrides(source_code)
    )

    report = await compare(service, source)

    assert report.outcome is AuthorityBehaviorOutcome.FAILED
    assert any(item.category is BehaviorCategory.DYNAMIC_EXECUTION for item in report.findings)
    assert not report.capabilities[0].behavior_compatible


@pytest.mark.asyncio
async def test_separation_audit_failure_and_concurrency_preserve_one_to_one() -> None:
    service, _, _, source, repository = await behavior_fixture()
    with pytest.raises(PackageAuthorityBehaviorValidationError):
        await compare(service, source, subject=schema_operator())
    assert repository._records == {}

    failing, _, _, failing_source, failing_repository = await behavior_fixture(
        audit_sink=FailingAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await compare(failing, failing_source)
    assert failing_repository._records == {}

    concurrent, _, _, concurrent_source, concurrent_repository = await behavior_fixture()
    first, second = await asyncio.gather(
        compare(concurrent, concurrent_source), compare(concurrent, concurrent_source)
    )
    assert first.validation_id == second.validation_id
    assert {first.reused, second.reused} == {False, True}
    assert len(concurrent_repository._records) == 1


@pytest.mark.asyncio
async def test_postgres_mapping_preserves_authority_behavior_report() -> None:
    service, _, _, source, _ = await behavior_fixture()
    report = await compare(service, source)
    row = ConnectorPackageAuthorityBehaviorValidationModel(
        **PostgreSQLPackageAuthorityBehaviorValidationRepository._values(report)
    )
    assert PostgreSQLPackageAuthorityBehaviorValidationRepository._to_domain(row) == report


def test_authority_behavior_api_requires_csrf_and_returns_minimized_report(
    tmp_path: Path,
) -> None:
    service, semantics_service, inventory_service, source, _ = asyncio.run(behavior_fixture())
    subject = behavior_operator()
    provider = BasicTestIdentityProvider(subject)
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-authority-behavior-validation-request.v1",
        "source_schema_semantics_validation_id": source.validation_id,
        "source_schema_semantics_validation_digest": source.canonical_digest,
        "package_digest": source.package_digest,
        "validation_profile": AUTHORITY_BEHAVIOR_PROFILE,
        "acknowledged_static_analysis_limitations": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=provider,
            package_supply_chain_inventory_service=inventory_service,
            package_schema_semantics_validation_service=semantics_service,
            package_authority_behavior_validation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-authority-behavior-validations"
        denied = client.post(
            endpoint, json=payload, headers={"Idempotency-Key": "authority-api-001"}
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "authority-api-001",
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
    assert data["findings"] == []
    assert data["permission_behavior_validation_completed"] is True
    assert all(
        key not in data
        for key in ("source", "source_code", "source_snippet", "destinations", "arguments")
    )
