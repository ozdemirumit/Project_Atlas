from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_contract_validation import contract_operator
from test_package_license_analysis import license_operator
from test_package_runner_validation import runner_fixture
from test_package_runner_validation import validate as runner_validate

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.lab_mock_target import (
    LAB_SELF_TEST_PROFILE,
    MockTargetConnectorLabRunner,
)
from atlas.modules.connectors.adapters.lab_self_test_memory import (
    InMemoryConnectorLabPlanSource,
    InMemoryLabAccessBroker,
    InMemoryPackageLabSelfTestRepository,
)
from atlas.modules.connectors.adapters.lab_self_test_postgres import (
    PostgreSQLPackageLabSelfTestRepository,
)
from atlas.modules.connectors.adapters.runner_validation_memory import (
    InMemoryPackageRunnerValidationRepository,
)
from atlas.modules.connectors.application.lab_self_test import (
    PackageLabSelfTestService,
    build_development_lab_plan,
)
from atlas.modules.connectors.application.lab_self_test_ports import PackageLabSelfTestError
from atlas.modules.connectors.domain.lab_self_test import (
    ConnectorLabPlan,
    ConnectorPackageLabSelfTest,
    LabExecutionLease,
    LabSelfTestOutcome,
)
from atlas.modules.connectors.domain.runner_validation import ConnectorPackageRunnerValidation
from atlas.modules.identity.domain.models import AuthenticatedSubject


def lab_operator(subject_id: str = "subject.package.lab-operator") -> AuthenticatedSubject:
    return license_operator(subject_id)


class NonRevokingAccessBroker(InMemoryLabAccessBroker):
    async def release(self, *, lease: LabExecutionLease) -> bool:
        await super().release(lease=lease)
        return False


async def lab_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
    runner: MockTargetConnectorLabRunner | None = None,
    non_revoking_access_broker: bool = False,
) -> tuple[
    PackageLabSelfTestService,
    ConnectorPackageRunnerValidation,
    ConnectorLabPlan,
    InMemoryLabAccessBroker,
]:
    runner_service, contract = await runner_fixture()
    source = await runner_validate(runner_service, contract)
    plan = build_development_lab_plan(
        organization_id=source.organization_id,
        environment_id=source.environment_id,
        approved_at=source.validated_at - timedelta(hours=1),
        expires_at=source.validated_at + timedelta(days=1),
    )
    broker_type = NonRevokingAccessBroker if non_revoking_access_broker else InMemoryLabAccessBroker
    broker = broker_type(clock=lambda: source.validated_at)
    service = PackageLabSelfTestService(
        repository=InMemoryPackageLabSelfTestRepository(),
        runner_source=runner_service.repository,
        contract_source=runner_service._contract_source,
        inventory_source=runner_service._inventory_source,
        acquisition_source=runner_service._acquisition_source,
        archive_source=runner_service._archive_source,
        plan_source=InMemoryConnectorLabPlanSource((plan,)),
        access_broker=broker,
        runner=runner or MockTargetConnectorLabRunner(),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=source.environment_id,
        clock=lambda: source.validated_at,
    )
    return service, source, plan, broker


async def self_test(
    service: PackageLabSelfTestService,
    source: ConnectorPackageRunnerValidation,
    plan: ConnectorLabPlan,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "lab-self-test-001",
) -> ConnectorPackageLabSelfTest:
    return await service.create(
        actor=subject or lab_operator(),
        source_runner_validation_id=source.validation_id,
        source_runner_validation_digest=source.canonical_digest,
        package_digest=source.package_digest,
        lab_plan_id=plan.plan_id,
        lab_plan_digest=plan.canonical_digest,
        validation_profile=LAB_SELF_TEST_PROFILE,
        acknowledged_non_production_read_only_lab_access=True,
        idempotency_key=key,
        correlation_id="cor_lab_self_test",
    )


@pytest.mark.asyncio
async def test_exact_package_passes_plan_bound_read_only_lab_self_test() -> None:
    audit = CollectingAuditSink()
    service, source, plan, broker = await lab_fixture(audit_sink=audit)

    first = await self_test(service, source, plan)
    second = await self_test(service, source, plan)

    assert first.outcome is LabSelfTestOutcome.PASSED, [
        (item.code, item.state.value, item.summary) for item in first.checks
    ]
    assert first.capability_count == first.tested_capability_count == source.capability_count
    assert first.lease_issued and first.lease_released and first.credentials_revoked
    assert first.session_closed and first.workspace_removed and broker.active_count == 0
    assert first.runner_validation_completed and first.lab_validation_completed
    assert not first.runtime_trust_granted and not first.execution_authorized
    assert not first.infrastructure_mutation_performed
    assert second.self_test_id == first.self_test_id and second.reused
    assert audit.records[-1].event_type == "atlas.connector.package-lab-self-test"
    exposed = asdict(first)
    for forbidden in (
        "destination_references",
        "tls_trust_reference",
        "secret_reference_ids",
        "credential_handle",
        "endpoint",
        "request_payload",
        "response_payload",
        "stdout",
        "stderr",
        "exception",
    ):
        assert forbidden not in exposed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subject",
    [
        contract_operator(),
        lab_operator("subject.runner.validator"),
        lab_operator("subject.lab.plan-approver"),
        lab_operator("subject.lab.credential-custodian"),
    ],
)
async def test_lab_self_test_rejects_prior_and_plan_actors(
    subject: AuthenticatedSubject,
) -> None:
    service, source, plan, _ = await lab_fixture()

    with pytest.raises(PackageLabSelfTestError, match="package_lab_separation_required"):
        await self_test(service, source, plan, subject=subject)


@pytest.mark.asyncio
async def test_lab_self_test_rejects_tampered_runner_and_plan() -> None:
    service, source, plan, _ = await lab_fixture()
    runner_source = cast(InMemoryPackageRunnerValidationRepository, service._runner_source)
    runner_source._records[source.validation_id] = replace(source, canonical_digest="f" * 64)
    with pytest.raises(PackageLabSelfTestError, match="package_lab_source_integrity_failed"):
        await self_test(service, source, plan, key="lab-self-test-tamper-01")

    service, source, plan, _ = await lab_fixture()
    plan_source = cast(InMemoryConnectorLabPlanSource, service._plan_source)
    plan_source._records[plan.plan_id] = replace(plan, canonical_digest="e" * 64)
    with pytest.raises(PackageLabSelfTestError, match="package_lab_source_integrity_failed"):
        await self_test(service, source, plan, key="lab-self-test-tamper-02")


@pytest.mark.asyncio
async def test_lab_self_test_is_concurrency_safe_and_audit_before_persist() -> None:
    failing, source, plan, _ = await lab_fixture(audit_sink=FailingAuditSink())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await self_test(failing, source, plan)
    assert cast(InMemoryPackageLabSelfTestRepository, failing.repository)._records == {}

    service, source, plan, _ = await lab_fixture()
    first, second = await asyncio.gather(
        self_test(service, source, plan), self_test(service, source, plan)
    )
    assert first.self_test_id == second.self_test_id
    assert {first.reused, second.reused} == {False, True}

    payload = PackageLabSelfTestService._normalize(PackageLabSelfTestService._payload(first))
    restored = PostgreSQLPackageLabSelfTestRepository._to_domain(cast(dict[str, object], payload))
    assert restored == first


@pytest.mark.asyncio
async def test_failed_lab_control_or_revocation_blocks_promotion_without_authority() -> None:
    service, source, plan, _ = await lab_fixture(
        runner=MockTargetConnectorLabRunner(failed_check="lab.authentication")
    )
    failed = await self_test(service, source, plan, key="lab-self-test-failed-01")
    assert failed.outcome is LabSelfTestOutcome.FAILED and failed.promotion_blocked
    assert failed.lab_validation_completed and not failed.execution_authorized

    service, source, plan, broker = await lab_fixture(non_revoking_access_broker=True)
    revoked = await self_test(service, source, plan, key="lab-self-test-failed-02")
    assert revoked.outcome is LabSelfTestOutcome.FAILED
    assert not revoked.lease_released and not revoked.credentials_revoked
    assert broker.active_count == 0


def test_lab_self_test_api_requires_csrf_and_returns_minimized_report(tmp_path: Path) -> None:
    service, source, plan, _ = asyncio.run(lab_fixture())
    subject = lab_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-lab-self-test-request.v1",
        "source_runner_validation_id": source.validation_id,
        "source_runner_validation_digest": source.canonical_digest,
        "package_digest": source.package_digest,
        "lab_plan_id": plan.plan_id,
        "lab_plan_digest": plan.canonical_digest,
        "validation_profile": LAB_SELF_TEST_PROFILE,
        "acknowledged_non_production_read_only_lab_access": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_lab_self_test_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-lab-self-tests"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "lab-api-001"})
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "lab-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        self_test_id = created.json()["data"]["self_test_id"]
        read = client.get(f"{endpoint}/{self_test_id}")

    assert denied.status_code == 403 and read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["outcome"] == "passed"
    assert data["source_runner_validation_id"] == source.validation_id
    assert data["lab_plan_id"] == plan.plan_id
    assert data["runner_validation_completed"] is True
    assert data["lab_validation_completed"] is True
    assert data["runtime_trust_granted"] is False
    for forbidden in (
        "destination_references",
        "tls_trust_reference",
        "secret_reference_ids",
        "credential_handle",
        "endpoint",
        "request_payload",
        "response_payload",
        "stdout",
        "stderr",
        "exception",
    ):
        assert forbidden not in data
