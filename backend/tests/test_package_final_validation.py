from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink, candidate
from test_package_contract_validation import contract_fixture
from test_package_contract_validation import validate as contract_validate
from test_package_lab_self_test import lab_operator
from test_package_lab_self_test import self_test as lab_self_test
from test_package_runner_validation import runner_operator
from test_package_runner_validation import validate as runner_validate

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.final_validation_memory import (
    InMemoryFinalValidationPolicySource,
    InMemoryPackageFinalValidationRepository,
)
from atlas.modules.connectors.adapters.final_validation_postgres import (
    PostgreSQLPackageFinalValidationRepository,
)
from atlas.modules.connectors.adapters.lab_mock_target import MockTargetConnectorLabRunner
from atlas.modules.connectors.adapters.lab_self_test_memory import (
    InMemoryConnectorLabPlanSource,
    InMemoryLabAccessBroker,
    InMemoryPackageLabSelfTestRepository,
)
from atlas.modules.connectors.adapters.runner_subprocess import SubprocessPackageRunner
from atlas.modules.connectors.adapters.runner_validation_memory import (
    InMemoryPackageRunnerValidationRepository,
)
from atlas.modules.connectors.application.final_validation import (
    PackageFinalValidationService,
    build_development_final_validation_policy,
)
from atlas.modules.connectors.application.final_validation_ports import PackageFinalValidationError
from atlas.modules.connectors.application.lab_self_test import (
    PackageLabSelfTestService,
    build_development_lab_plan,
)
from atlas.modules.connectors.application.runner_validation import PackageRunnerValidationService
from atlas.modules.connectors.domain.final_validation import (
    ConnectorPackageFinalValidation,
    FinalValidationOutcome,
    FinalValidationPolicySnapshot,
)
from atlas.modules.connectors.domain.lab_self_test import ConnectorPackageLabSelfTest
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.mcp_builder.adapters.candidate_handoff_memory import (
    InMemoryMcpBuilderCandidateHandoffRepository,
)


def final_operator(subject_id: str = "subject.package.final-validator") -> AuthenticatedSubject:
    return lab_operator(subject_id)


async def final_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
    maximum_disclosed_limitations: int = 100,
) -> tuple[
    PackageFinalValidationService,
    ConnectorPackageLabSelfTest,
    FinalValidationPolicySnapshot,
]:
    contract_service, parts, license_source = await contract_fixture()
    contract = await contract_validate(contract_service, license_source)
    runner_service = PackageRunnerValidationService(
        repository=InMemoryPackageRunnerValidationRepository(),
        contract_source=contract_service.repository,
        inventory_source=contract_service._inventory_source,
        acquisition_source=contract_service._acquisition_source,
        archive_source=contract_service._archive_source,
        runner=SubprocessPackageRunner(),
        audit_sink=CollectingAuditSink(),
        environment_id=contract.environment_id,
        clock=lambda: contract.validated_at,
    )
    runner = await runner_validate(runner_service, contract)
    plan = build_development_lab_plan(
        organization_id=runner.organization_id,
        environment_id=runner.environment_id,
        approved_at=runner.validated_at - timedelta(hours=1),
        expires_at=runner.validated_at + timedelta(days=1),
    )
    lab_service = PackageLabSelfTestService(
        repository=InMemoryPackageLabSelfTestRepository(),
        runner_source=runner_service.repository,
        contract_source=contract_service.repository,
        inventory_source=contract_service._inventory_source,
        acquisition_source=contract_service._acquisition_source,
        archive_source=contract_service._archive_source,
        plan_source=InMemoryConnectorLabPlanSource((plan,)),
        access_broker=InMemoryLabAccessBroker(clock=lambda: runner.validated_at),
        runner=MockTargetConnectorLabRunner(),
        audit_sink=CollectingAuditSink(),
        environment_id=runner.environment_id,
        clock=lambda: runner.validated_at,
    )
    lab = await lab_self_test(lab_service, runner, plan)
    policy = build_development_final_validation_policy(
        organization_id=lab.organization_id,
        environment_id=lab.environment_id,
        issued_at=lab.validated_at - timedelta(days=1),
        expires_at=lab.validated_at + timedelta(days=1),
    )
    if maximum_disclosed_limitations != policy.maximum_disclosed_limitations:
        draft = replace(
            policy,
            maximum_disclosed_limitations=maximum_disclosed_limitations,
            canonical_digest="0" * 64,
        )
        payload = cast(dict[str, object], asdict(draft))
        payload.pop("canonical_digest")
        policy = replace(
            draft,
            canonical_digest=PackageFinalValidationService._digest(
                PackageFinalValidationService._normalize(payload)
            ),
        )

    handoff, _ = candidate()
    handoffs = InMemoryMcpBuilderCandidateHandoffRepository()
    assert await handoffs.add(handoff)
    malware_service = parts[0]
    vulnerability_service = parts[1]
    static_service = parts[2]
    authority_service = parts[3]
    semantics_service = parts[4]
    inventory_service = parts[5]
    license_service = parts[8]
    service = PackageFinalValidationService(
        repository=InMemoryPackageFinalValidationRepository(),
        handoff_source=handoffs,
        acquisition_source=contract_service._acquisition_source,
        archive_source=contract_service._archive_source,
        validation_source=inventory_service._validation_source,
        inventory_source=inventory_service.repository,
        content_policy_source=semantics_service._content_policy_source,
        schema_semantics_source=semantics_service.repository,
        authority_behavior_source=authority_service.repository,
        static_dependency_source=static_service.repository,
        vulnerability_source=vulnerability_service.repository,
        malware_source=malware_service.repository,
        license_source=license_service.repository,
        contract_source=contract_service.repository,
        runner_source=runner_service.repository,
        lab_source=lab_service.repository,
        policy_source=InMemoryFinalValidationPolicySource((policy,)),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=lab.environment_id,
        clock=lambda: lab.validated_at,
    )
    return service, lab, policy


async def final_validate(
    service: PackageFinalValidationService,
    lab: ConnectorPackageLabSelfTest,
    policy: FinalValidationPolicySnapshot,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "final-validation-001",
) -> ConnectorPackageFinalValidation:
    return await service.create(
        actor=subject or final_operator(),
        source_lab_self_test_id=lab.self_test_id,
        source_lab_self_test_digest=lab.canonical_digest,
        package_digest=lab.package_digest,
        policy_id=policy.policy_id,
        policy_digest=policy.canonical_digest,
        acknowledged_evidence_only_no_approval=True,
        idempotency_key=key,
        correlation_id="cor_final_validation",
    )


@pytest.mark.asyncio
async def test_exact_lineage_is_eligible_without_lifecycle_authority() -> None:
    audit = CollectingAuditSink()
    service, lab, policy = await final_fixture(audit_sink=audit)

    first = await final_validate(service, lab, policy)
    second = await final_validate(service, lab, policy)

    assert first.outcome is FinalValidationOutcome.ELIGIBLE
    assert first.eligible_for_human_approval and not first.promotion_blocked
    assert first.stage_count == first.passed_stage_count == 13
    assert len(first.stage_evidence) == 13 and first.blocking_risk_count == 0
    assert first.final_validation_completed and not first.connector_approved
    assert not first.package_signed and not first.execution_authorized
    assert not first.infrastructure_mutation_performed
    assert second.validation_id == first.validation_id and second.reused
    assert audit.records[-1].event_type == "atlas.connector.package-final-validation"


@pytest.mark.asyncio
async def test_final_validation_rejects_upstream_actors_and_tampering() -> None:
    service, lab, policy = await final_fixture()
    for subject in (
        runner_operator(),
        lab_operator(),
        final_operator(lab.lab_plan_approved_by),
        final_operator(lab.credential_custodied_by),
    ):
        with pytest.raises(PackageFinalValidationError, match="package_final_separation_required"):
            await final_validate(service, lab, policy, subject=subject, key=subject.subject_id)

    lab_source = cast(InMemoryPackageLabSelfTestRepository, service._lab_source)
    lab_source._records[lab.self_test_id] = replace(lab, canonical_digest="f" * 64)
    with pytest.raises(PackageFinalValidationError, match="package_final_source_integrity_failed"):
        await final_validate(service, lab, policy, key="final-tamper-001")


@pytest.mark.asyncio
async def test_policy_can_block_without_granting_authority() -> None:
    service, lab, policy = await final_fixture(maximum_disclosed_limitations=0)
    result = await final_validate(service, lab, policy)

    assert result.outcome is FinalValidationOutcome.BLOCKED
    assert result.promotion_blocked and not result.eligible_for_human_approval
    assert result.blocking_risk_count == 1
    assert not result.connector_approved and not result.runtime_trust_granted


@pytest.mark.asyncio
async def test_stale_evidence_has_explicit_blocking_risk() -> None:
    service, lab, policy = await final_fixture()
    draft = replace(
        policy,
        maximum_evidence_age_days=1,
        expires_at=lab.validated_at + timedelta(days=5),
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(draft))
    payload.pop("canonical_digest")
    policy = replace(
        draft,
        canonical_digest=PackageFinalValidationService._digest(
            PackageFinalValidationService._normalize(payload)
        ),
    )
    policy_source = cast(InMemoryFinalValidationPolicySource, service._policy_source)
    policy_source._records[policy.policy_id] = policy
    service._clock = lambda: lab.validated_at + timedelta(days=2)

    result = await final_validate(service, lab, policy, key="final-stale-001")

    assert result.outcome is FinalValidationOutcome.BLOCKED
    assert result.blocking_risk_count == 13
    blocking_risks = tuple(item for item in result.risks if item.blocking)
    assert all(item.code.endswith(".evidence-stale") for item in blocking_risks)
    assert not result.connector_approved and not result.execution_authorized


@pytest.mark.asyncio
async def test_final_validation_is_concurrency_safe_and_audit_before_persist() -> None:
    failing, lab, policy = await final_fixture(audit_sink=FailingAuditSink())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await final_validate(failing, lab, policy)
    assert cast(InMemoryPackageFinalValidationRepository, failing.repository)._records == {}

    service, lab, policy = await final_fixture()
    first, second = await asyncio.gather(
        final_validate(service, lab, policy), final_validate(service, lab, policy)
    )
    assert first.validation_id == second.validation_id
    assert {first.reused, second.reused} == {False, True}

    payload = PackageFinalValidationService._normalize(asdict(first))
    assert isinstance(payload, dict)
    restored = PostgreSQLPackageFinalValidationRepository._to_domain(payload)
    assert restored == first


def test_final_validation_api_requires_csrf_and_returns_minimized_report(
    tmp_path: Path,
) -> None:
    service, source, policy = asyncio.run(final_fixture())
    subject = final_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-final-validation-request.v1",
        "source_lab_self_test_id": source.self_test_id,
        "source_lab_self_test_digest": source.canonical_digest,
        "package_digest": source.package_digest,
        "policy_id": policy.policy_id,
        "policy_digest": policy.canonical_digest,
        "acknowledged_evidence_only_no_approval": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_final_validation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-final-validations"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "final-api-001"})
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "final-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        validation_id = created.json()["data"]["validation_id"]
        read = client.get(f"{endpoint}/{validation_id}")

    assert denied.status_code == 403 and read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["outcome"] == "eligible_for_human_approval"
    assert data["source_lab_self_test_id"] == source.self_test_id
    assert data["policy_id"] == policy.policy_id
    assert data["stage_count"] == data["passed_stage_count"] == 13
    assert len(data["stage_evidence"]) == 13
    assert data["final_validation_completed"] is True
    assert data["eligible_for_human_approval"] is True
    assert data["connector_approved"] is False
    assert data["execution_authorized"] is False
    assert data["infrastructure_mutation_performed"] is False
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
        "target_alias",
    ):
        assert forbidden not in data
