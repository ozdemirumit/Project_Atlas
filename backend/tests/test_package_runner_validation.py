from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_contract_validation import (
    contract_fixture,
    contract_operator,
)
from test_package_contract_validation import validate as contract_validate
from test_package_license_analysis import license_operator

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.contract_validation_memory import (
    InMemoryPackageContractValidationRepository,
)
from atlas.modules.connectors.adapters.runner_subprocess import (
    RUNNER_VALIDATION_PROFILE,
    SubprocessPackageRunner,
)
from atlas.modules.connectors.adapters.runner_validation_memory import (
    InMemoryPackageRunnerValidationRepository,
)
from atlas.modules.connectors.adapters.runner_validation_postgres import (
    PostgreSQLPackageRunnerValidationRepository,
)
from atlas.modules.connectors.application.runner_validation import (
    PackageRunnerValidationService,
)
from atlas.modules.connectors.application.runner_validation_ports import (
    PackageRunnerValidationError,
)
from atlas.modules.connectors.domain.contract_validation import ConnectorPackageContractValidation
from atlas.modules.connectors.domain.runner_validation import (
    ConnectorPackageRunnerValidation,
    RunnerValidationOutcome,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


def runner_operator(subject_id: str = "subject.runner.validator") -> AuthenticatedSubject:
    return license_operator(subject_id)


async def runner_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
    runner: SubprocessPackageRunner | None = None,
) -> tuple[PackageRunnerValidationService, ConnectorPackageContractValidation]:
    contract_service, _, license_source = await contract_fixture()
    source = await contract_validate(contract_service, license_source)
    service = PackageRunnerValidationService(
        repository=InMemoryPackageRunnerValidationRepository(),
        contract_source=contract_service.repository,
        inventory_source=contract_service._inventory_source,
        acquisition_source=contract_service._acquisition_source,
        archive_source=contract_service._archive_source,
        runner=runner or SubprocessPackageRunner(),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id="environment.development",
        clock=lambda: source.validated_at,
    )
    return service, source


async def validate(
    service: PackageRunnerValidationService,
    source: ConnectorPackageContractValidation,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "runner-test-001",
) -> ConnectorPackageRunnerValidation:
    return await service.create(
        actor=subject or runner_operator(),
        source_contract_validation_id=source.validation_id,
        source_contract_validation_digest=source.canonical_digest,
        package_digest=source.package_digest,
        validation_profile=RUNNER_VALIDATION_PROFILE,
        acknowledged_disconnected_synthetic_execution=True,
        idempotency_key=key,
        correlation_id="cor_runner_test",
    )


@pytest.mark.asyncio
async def test_exact_package_runs_in_disconnected_synthetic_runner() -> None:
    audit = CollectingAuditSink()
    service, source = await runner_fixture(audit_sink=audit)

    first = await validate(service, source)
    second = await validate(service, source)

    assert first.outcome is RunnerValidationOutcome.PASSED, [
        (item.code, item.state.value, item.summary) for item in first.checks
    ]
    assert first.workspace_removed and first.child_started and first.child_exit_code == 0
    assert first.capability_count == first.invoked_capability_count >= 1
    assert first.fail_closed_count + first.bounded_literal_count == first.capability_count
    assert first.runner_validation_completed and not first.lab_validation_completed
    assert not first.runtime_trust_granted and not first.execution_authorized
    assert second.validation_id == first.validation_id and second.reused
    assert audit.records[-1].event_type == "atlas.connector.package-runner-validation"
    exposed = asdict(first)
    for forbidden in (
        "source_code",
        "fixture_payload",
        "expected_output",
        "capability_ids",
        "paths",
        "environment",
        "stdout",
        "stderr",
        "exception",
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
    service, source = await runner_fixture()
    subject = replace(runner_operator(), authentication_method=method, assurance_level=assurance)

    report = await validate(service, source, subject=subject)

    assert report.outcome is RunnerValidationOutcome.PASSED


@pytest.mark.asyncio
async def test_runner_validation_rejects_non_human_actor() -> None:
    service, source = await runner_fixture()
    subject = replace(runner_operator(), kind=SubjectKind.SERVICE)

    with pytest.raises(PackageRunnerValidationError, match="package_runner_human_required"):
        await validate(service, source, subject=subject)


@pytest.mark.asyncio
async def test_runner_rejects_prior_actor_and_tampered_source() -> None:
    service, source = await runner_fixture()
    with pytest.raises(PackageRunnerValidationError, match="package_runner_separation_required"):
        await validate(service, source, subject=contract_operator())

    tampered = replace(source, canonical_digest="f" * 64)
    source_repository = cast(InMemoryPackageContractValidationRepository, service._contract_source)
    source_repository._records[source.validation_id] = tampered
    with pytest.raises(
        PackageRunnerValidationError, match="package_runner_source_integrity_failed"
    ):
        await validate(service, tampered, key="runner-tampered-001")


@pytest.mark.asyncio
async def test_runner_is_concurrency_safe_and_audit_before_persist() -> None:
    failing, failing_source = await runner_fixture(audit_sink=FailingAuditSink())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await validate(failing, failing_source)
    assert cast(InMemoryPackageRunnerValidationRepository, failing.repository)._records == {}

    service, source = await runner_fixture()
    first, second = await asyncio.gather(validate(service, source), validate(service, source))
    assert first.validation_id == second.validation_id
    assert {first.reused, second.reused} == {False, True}

    payload = PackageRunnerValidationService._normalize(
        PackageRunnerValidationService._payload(first)
    )
    restored = PostgreSQLPackageRunnerValidationRepository._to_domain(
        cast(dict[str, object], payload)
    )
    assert restored == first


@pytest.mark.asyncio
async def test_timeout_is_immutable_failed_evidence_without_authority() -> None:
    service, source = await runner_fixture(runner=SubprocessPackageRunner(timeout_seconds=0.000001))

    report = await validate(service, source, key="runner-timeout-001")

    assert report.outcome is RunnerValidationOutcome.FAILED
    assert report.promotion_blocked and report.workspace_removed
    assert report.runner_validation_completed and not report.lab_validation_completed
    assert not report.runtime_trust_granted and not report.execution_authorized


def test_runner_api_requires_csrf_and_returns_minimized_report(tmp_path: Path) -> None:
    service, source = asyncio.run(runner_fixture())
    subject = runner_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-runner-validation-request.v1",
        "source_contract_validation_id": source.validation_id,
        "source_contract_validation_digest": source.canonical_digest,
        "package_digest": source.package_digest,
        "validation_profile": RUNNER_VALIDATION_PROFILE,
        "acknowledged_disconnected_synthetic_execution": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_runner_validation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-runner-validations"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "runner-api-01"})
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "runner-api-01",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        validation_id = created.json()["data"]["validation_id"]
        read = client.get(f"{endpoint}/{validation_id}")

    assert denied.status_code == 403 and read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["outcome"] == "passed"
    assert data["contract_validation_completed"] is True
    assert data["runner_validation_completed"] is True
    assert data["lab_validation_completed"] is False
    for forbidden in (
        "source_code",
        "fixture_payload",
        "expected_output",
        "capability_ids",
        "paths",
        "environment",
        "stdout",
        "stderr",
        "exception",
    ):
        assert forbidden not in data
