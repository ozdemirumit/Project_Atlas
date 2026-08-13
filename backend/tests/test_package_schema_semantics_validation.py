from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_content_policy_scan import (
    content_policy_fixture,
    content_policy_operator,
    scan,
)

from atlas.api.app import create_app
from atlas.core.persistence.models import ConnectorPackageSchemaSemanticsValidationModel
from atlas.modules.connectors.adapters.acquisition_archive_memory import (
    InMemoryAcquiredPackagePublisher,
)
from atlas.modules.connectors.adapters.schema_semantics_validation_memory import (
    InMemoryPackageSchemaSemanticsValidationRepository,
)
from atlas.modules.connectors.adapters.schema_semantics_validation_postgres import (
    PostgreSQLPackageSchemaSemanticsValidationRepository,
)
from atlas.modules.connectors.application.content_policy_scan import PackageContentPolicyScanService
from atlas.modules.connectors.application.schema_semantics_validation import (
    SCHEMA_SEMANTICS_PROFILE,
    PackageSchemaSemanticsValidationService,
)
from atlas.modules.connectors.application.schema_semantics_validation_ports import (
    PackageSchemaSemanticsValidationError,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.domain.content_policy_scan import ConnectorPackageContentPolicyScan
from atlas.modules.connectors.domain.schema_semantics_validation import (
    ConnectorPackageSchemaSemanticsValidation,
    SchemaSemanticsOutcome,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def reviewed_schema_overrides() -> dict[str, str]:
    capability_id = "capability.storage.health.read"
    return {
        "schemas/config/config.schema.json": canonical(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "atlas://generated/config.schema.json",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "endpoint": {
                        "type": "string",
                        "format": "uri",
                        "minLength": 1,
                        "maxLength": 500,
                        "x-atlas-sensitive": False,
                    },
                    "credential_ref": {
                        "type": "string",
                        "format": "atlas-secret-reference",
                        "x-atlas-secret-value": False,
                    },
                },
                "required": ["credential_ref", "endpoint"],
            }
        ),
        "schemas/inputs/capability_read.schema.json": canonical(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": f"atlas://generated/{capability_id}/input.schema.json",
                "type": "object",
                "additionalProperties": False,
                "properties": {"target_id": {"type": "string", "minLength": 1, "maxLength": 120}},
                "required": ["target_id"],
                "x-atlas-parameter-evidence-count": 1,
                "x-atlas-generation-status": "reviewed",
            }
        ),
        "schemas/outputs/capability_read.schema.json": canonical(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": f"atlas://generated/{capability_id}/output.schema.json",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["healthy", "degraded", "unknown"],
                        "minLength": 1,
                        "maxLength": 20,
                    }
                },
                "required": ["status"],
                "x-atlas-response-code-evidence": ["200"],
                "x-atlas-generation-status": "reviewed",
            }
        ),
    }


def schema_operator(
    subject_id: str = "subject.schema-semantics.validator",
) -> AuthenticatedSubject:
    return content_policy_operator(subject_id)


async def semantics_fixture(
    *,
    overrides: dict[str, str] | None = None,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
) -> tuple[
    PackageSchemaSemanticsValidationService,
    PackageContentPolicyScanService,
    PackageSupplyChainInventoryService,
    ConnectorPackageContentPolicyScan,
    InMemoryPackageSchemaSemanticsValidationRepository,
]:
    content_service, inventory_service, source_inventory, _ = await content_policy_fixture(
        overrides=overrides
    )
    source_scan = await scan(content_service, source_inventory)
    assert source_scan.outcome.value == "passed"
    repository = InMemoryPackageSchemaSemanticsValidationRepository()
    service = PackageSchemaSemanticsValidationService(
        repository=repository,
        content_policy_source=content_service.repository,
        inventory_source=content_service.inventory_source,
        acquisition_source=content_service.acquisition_source,
        archive_source=content_service.archive_source,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id="environment.development",
        clock=lambda: source_scan.scanned_at,
    )
    return service, content_service, inventory_service, source_scan, repository


async def validate(
    service: PackageSchemaSemanticsValidationService,
    source_scan: ConnectorPackageContentPolicyScan,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "schema-semantics-test-001",
) -> ConnectorPackageSchemaSemanticsValidation:
    return await service.create(
        actor=subject or schema_operator(),
        source_content_policy_scan_id=source_scan.scan_id,
        source_content_policy_scan_digest=source_scan.canonical_digest,
        package_digest=source_scan.package_digest,
        validation_profile=SCHEMA_SEMANTICS_PROFILE,
        acknowledged_untrusted_schema_content=True,
        idempotency_key=key,
        correlation_id="cor_schema_semantics_test",
    )


@pytest.mark.asyncio
async def test_generated_draft_fails_semantics_without_lifecycle_authority() -> None:
    service, _, _, source_scan, repository = await semantics_fixture()

    report = await validate(service, source_scan)

    assert report.outcome is SchemaSemanticsOutcome.FAILED
    assert report.promotion_blocked
    assert len(report.schemas) == 3
    assert any(item.rule_code == "schema.capability.placeholder" for item in report.findings)
    assert any(item.rule_code == "schema.review.unresolved" for item in report.findings)
    assert not report.connector_rejected
    assert not report.connector_registered
    assert not report.runtime_trust_granted
    assert not report.execution_authorized
    assert not report.infrastructure_mutation_performed
    assert (
        await repository.get_by_source_scan(source_content_policy_scan_id=source_scan.scan_id)
        == report
    )


@pytest.mark.asyncio
async def test_reviewed_bounded_schemas_pass_idempotently_and_audit() -> None:
    audit = CollectingAuditSink()
    service, _, _, source_scan, _ = await semantics_fixture(
        overrides=reviewed_schema_overrides(), audit_sink=audit
    )

    first = await validate(service, source_scan)
    second = await validate(service, source_scan)

    assert first.outcome is SchemaSemanticsOutcome.PASSED
    assert not first.promotion_blocked
    assert first.findings == ()
    assert all(item.closed_object and item.semantically_complete for item in first.schemas)
    assert second == replace(first, reused=True)
    assert [item.result_code for item in audit.records] == [
        "connector_schema_semantics_validation_passed"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "assurance"),
    [
        (AuthenticationMethod.DEVELOPMENT, AssuranceLevel.DEVELOPMENT),
        (AuthenticationMethod.LDAP, AssuranceLevel.SINGLE_FACTOR),
    ],
)
async def test_allows_human_schema_validator_without_fixed_assurance(
    method: AuthenticationMethod,
    assurance: AssuranceLevel,
) -> None:
    service, _, _, source_scan, _ = await semantics_fixture(overrides=reviewed_schema_overrides())
    subject = replace(
        schema_operator(),
        authentication_method=method,
        assurance_level=assurance,
    )

    report = await validate(service, source_scan, subject=subject)

    assert report.outcome is SchemaSemanticsOutcome.PASSED


@pytest.mark.asyncio
async def test_rejects_non_human_schema_validator() -> None:
    service, _, _, source_scan, repository = await semantics_fixture(
        overrides=reviewed_schema_overrides()
    )

    with pytest.raises(PackageSchemaSemanticsValidationError) as caught:
        await validate(
            service,
            source_scan,
            subject=replace(schema_operator(), kind=SubjectKind.SERVICE),
        )

    assert caught.value.code == "package_schema_semantics_human_required"
    assert repository._records == {}


@pytest.mark.asyncio
async def test_unsafe_schema_details_are_not_retained() -> None:
    marker = "SyntheticSchemaDefaultThatMustNotEscape"
    overrides = reviewed_schema_overrides()
    config = json.loads(overrides["schemas/config/config.schema.json"])
    config["properties"]["endpoint"]["default"] = marker
    overrides["schemas/config/config.schema.json"] = canonical(config)
    service, _, _, source_scan, _ = await semantics_fixture(overrides=overrides)

    report = await validate(service, source_scan)

    assert report.outcome is SchemaSemanticsOutcome.FAILED
    assert any(item.rule_code == "schema.configuration.default" for item in report.findings)
    assert marker not in repr(report)


@pytest.mark.asyncio
async def test_rejects_prior_stage_actor_and_archive_corruption() -> None:
    service, content_service, _, source_scan, repository = await semantics_fixture(
        overrides=reviewed_schema_overrides()
    )
    with pytest.raises(PackageSchemaSemanticsValidationError):
        await validate(service, source_scan, subject=content_policy_operator())

    archive_source = cast(InMemoryAcquiredPackagePublisher, content_service.archive_source)
    archive_source._archives[source_scan.package_digest] = b"changed"
    with pytest.raises(PackageSchemaSemanticsValidationError) as caught:
        await validate(service, source_scan)

    assert caught.value.code == "package_schema_semantics_archive_integrity_failed"
    assert repository._records == {}


@pytest.mark.asyncio
async def test_audit_failure_and_concurrency_preserve_one_to_one_report() -> None:
    failing, _, _, source_scan, repository = await semantics_fixture(
        overrides=reviewed_schema_overrides(), audit_sink=FailingAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await validate(failing, source_scan)
    assert repository._records == {}

    service, _, _, source_scan, repository = await semantics_fixture(
        overrides=reviewed_schema_overrides()
    )
    first, second = await asyncio.gather(
        validate(service, source_scan), validate(service, source_scan)
    )
    assert first.validation_id == second.validation_id
    assert {first.reused, second.reused} == {False, True}
    assert len(repository._records) == 1


@pytest.mark.asyncio
async def test_postgres_mapping_preserves_schema_semantics_report() -> None:
    service, _, _, source_scan, _ = await semantics_fixture(overrides=reviewed_schema_overrides())
    report = await validate(service, source_scan)
    row = ConnectorPackageSchemaSemanticsValidationModel(
        **PostgreSQLPackageSchemaSemanticsValidationRepository._values(report)
    )
    assert PostgreSQLPackageSchemaSemanticsValidationRepository._to_domain(row) == report


def test_schema_semantics_api_requires_csrf_and_returns_minimized_report(tmp_path: Path) -> None:
    service, content_service, inventory_service, source_scan, _ = asyncio.run(
        semantics_fixture(overrides=reviewed_schema_overrides())
    )
    subject = schema_operator()
    provider = BasicTestIdentityProvider(subject)
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-schema-semantics-validation-request.v1",
        "source_content_policy_scan_id": source_scan.scan_id,
        "source_content_policy_scan_digest": source_scan.canonical_digest,
        "package_digest": source_scan.package_digest,
        "validation_profile": SCHEMA_SEMANTICS_PROFILE,
        "acknowledged_untrusted_schema_content": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=provider,
            package_supply_chain_inventory_service=inventory_service,
            package_content_policy_scan_service=content_service,
            package_schema_semantics_validation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-schema-semantics-validations"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "schema-api-001"})
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "schema-api-001",
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
    assert data["schema_semantic_validation_completed"] is True
    assert all(
        key not in data
        for key in ("body", "schema_body", "default_values", "patterns", "enum_values")
    )
