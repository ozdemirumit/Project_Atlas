from __future__ import annotations

import asyncio
import inspect
import os
from dataclasses import replace
from datetime import timedelta
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import Table, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from test_workflow_protected_runtime_process_creation_authorizations_postgres import (
    _authorize_process_creation,
    _cleanup_fixture_fences,
    _cleanup_process_creation,
    _FixtureProcessCreationRepository,
    _process_service,
    _seed_fixture_fences,
    _seed_ready_result,
)
from test_workflow_protected_runtime_process_creation_consumptions_postgres import (
    _cleanup_consumption,
)
from test_workflow_protected_runtime_readiness_authorizations_postgres import (
    _AcceptAllReceiptVerifier,
)
from test_workflow_protected_runtime_readiness_consumptions_postgres import (
    _cleanup as _cleanup_readiness,
)

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeProcessCreationResultModel,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaimModel,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.protected_runtime_process_creators import (
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_consumptions import (
    WorkflowProtectedRuntimeProcessCreationConsumptionService,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_authorization_ports import (  # noqa: E501
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTATION_SIGNING_KEY_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTOR_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTOR_VERSION,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationSourceRequest,
    WorkflowProtectedRuntimeProcessSchedulingStateAttestation,
    WorkflowProtectedRuntimeProcessSchedulingStateAttestationRequest,
)
from atlas.modules.workflows.domain.models import canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_creation_consumption_domain import (
    code_owned_workflow_protected_runtime_process_creation_consumption_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_authorization_domain import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_process_scheduling_authorization_policy,
)


def _method_source(name: str) -> str:
    return inspect.getsource(getattr(PostgreSQLWorkflowPlanRepository, name))


def test_repository_exposes_bounded_process_scheduling_authorization_contract() -> None:
    for name in (
        "preflight_protected_runtime_process_scheduling_authorization",
        "get_protected_runtime_process_scheduling_authorization_source",
        "authorize_protected_runtime_process_scheduling",
        "list_protected_runtime_process_scheduling_authorization_presentations",
        "_lock_protected_runtime_process_scheduling_authorization_rows",
        "_protected_runtime_process_scheduling_replay",
        "_protected_runtime_process_scheduling_source_is_current",
        "_protected_runtime_process_scheduling_lease_model",
        "_protected_runtime_process_scheduling_claim_model",
    ):
        assert callable(getattr(PostgreSQLWorkflowPlanRepository, name))


def test_lock_is_replay_first_authoritative_and_revalidates_full_lineage() -> None:
    source = _method_source("_lock_protected_runtime_process_scheduling_authorization_rows")

    assert source.index("existing_claims = tuple(") < source.index("source_statement = (")
    assert source.count("func.clock_timestamp()") >= 2
    assert ".with_for_update()" in source
    for model in (
        "WorkflowProtectedRuntimeProcessCreationResultModel",
        "WorkflowProtectedRuntimeProcessCreationAttemptModel",
        "WorkflowProtectedRuntimeProcessCreationConsumptionClaimModel",
        "WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseModel",
        "WorkflowProtectedRuntimeProcessCreationAuthorizationClaimModel",
    ):
        assert model in source
    assert "_lock_protected_runtime_process_creation_authorization_rows" in source


def test_persistence_has_no_scheduling_or_external_effect_path() -> None:
    authorize = _method_source("authorize_protected_runtime_process_scheduling")
    current = _method_source("_protected_runtime_process_scheduling_source_is_current")

    assert "clock_timestamp" in authorize
    assert (
        "validate_workflow_protected_runtime_process_scheduling_authorization_request" in authorize
    )
    assert "WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseModel" not in authorize
    assert "WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaimModel" not in authorize
    assert "process_scheduled" in current
    assert "process_resumed" in current
    assert "process_dispatched" in current
    assert "process_executed" in current
    for forbidden in (
        "httpx",
        "requests.",
        "socket.",
        "subprocess",
        "connector",
        "mcp",
        "provider_sdk",
        "schedule_process",
        "resume_process",
        "dispatch_process",
        "execute_process",
    ):
        assert forbidden not in authorize.lower()


class _SchedulingStateAttestor:
    available = True

    async def attest_runtime_process_scheduling_state(
        self, request: WorkflowProtectedRuntimeProcessSchedulingStateAttestationRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingStateAttestation:
        request_values = {
            name: getattr(request, name) for name in request.__slots__ if name != "requested_at"
        }
        valid_until = request.requested_at + timedelta(seconds=1)
        values: dict[str, object] = {
            **request_values,
            "attestation_id": f"process-scheduling-attestation.{uuid4().hex}",
            "attestor_id": WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTOR_ID,
            "attestor_version": WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTOR_VERSION,
            "signing_key_id": (
                WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTATION_SIGNING_KEY_ID
            ),
            "signature_algorithm": "test-signature-v1",
            "observed_at": request.requested_at,
            "valid_until": valid_until,
            "process_state_eligible_until": valid_until,
            "exact_process_creation_result_confirmed": True,
            "terminal_success_confirmed": True,
            "metadata_only_confirmed": True,
            "process_created_confirmed": True,
            "process_sealed_confirmed": True,
            "process_suspended_confirmed": True,
            "process_not_scheduled_confirmed": True,
            "process_not_resumed_confirmed": True,
            "process_not_dispatched_confirmed": True,
            "process_not_executed_confirmed": True,
            "runtime_envelope_current": True,
            "destination_generation_current": True,
            "destination_fence_current": True,
            "protected_slot_generation_current": True,
            "prior_process_scheduling_claim_absent": True,
            "prior_process_scheduling_lease_absent": True,
            "scheduling_performed": False,
            "resume_performed": False,
            "dispatch_performed": False,
            "execution_performed": False,
            "network_activity_performed": False,
            "connector_activity_performed": False,
            "mcp_activity_performed": False,
            "provider_activity_performed": False,
            "infrastructure_mutation_performed": False,
            "process_locator_included": False,
            "process_identifier_included": False,
            "process_material_included": False,
            "runtime_material_included": False,
            "command_material_included": False,
            "argument_material_included": False,
            "environment_material_included": False,
            "prompt_material_included": False,
            "model_material_included": False,
            "endpoint_material_included": False,
            "credential_material_included": False,
            "secret_material_included": False,
            "integrity_signature": "f" * 64,
        }
        attestation = WorkflowProtectedRuntimeProcessSchedulingStateAttestation(
            **cast(Any, values), canonical_digest="0" * 64
        )
        return replace(
            attestation,
            canonical_digest=canonical_digest(attestation.digest_payload()),
        )

    def verify_runtime_process_scheduling_state_attestation(
        self, attestation: WorkflowProtectedRuntimeProcessSchedulingStateAttestation
    ) -> bool:
        del attestation
        return True


async def _seed_created_process(
    engine: AsyncEngine,
    repository: _FixtureProcessCreationRepository,
    *,
    receipt_verifier: Any,
    suffix: str,
) -> tuple[Any, Any, str]:
    start_request, readiness_result = await _seed_ready_result(engine, repository, suffix=suffix)
    await _seed_fixture_fences(engine, repository, readiness_result)
    authorization = await _authorize_process_creation(
        _process_service(repository),
        readiness_result,
        idempotency_key=f"imp-229-creation-auth-{uuid4().hex}",
    )
    service = WorkflowProtectedRuntimeProcessCreationConsumptionService(
        repository=cast(Any, repository),
        instruction_signer=(
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSigner(
                development_enabled=True
            )
        ),
        instruction_signature_verifier=(
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier(
                development_enabled=True
            )
        ),
        receipt_signature_verifier=receipt_verifier,
        creator=DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator(
            development_enabled=True
        ),
    )
    policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
    outcome = await service.consume(
        authorization_lease_id=authorization.authorization_lease_id,
        scope=readiness_result.scope,
        consumer_subject_id=policy.consumer_subject_id,
        consumer_audience=policy.consumer_audience,
        consumer_contract_id=policy.consumer_contract_id,
        consumer_contract_version=policy.consumer_contract_version,
        irreversible_consumption_acknowledged=True,
        uncertainty_no_retry_acknowledged=True,
        idempotency_key=f"imp-229-creation-{uuid4().hex}",
    )
    assert outcome.result is not None
    return start_request, readiness_result, authorization.authorization_lease_id


async def _authorization_request(
    repository: PostgreSQLWorkflowPlanRepository,
    *,
    process_creation_result_id: str,
    scope: Any,
    idempotency_key: str,
    attestor: _SchedulingStateAttestor,
    receipt_verifier: Any,
) -> WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseRequest:
    policy = code_owned_workflow_protected_runtime_process_scheduling_authorization_policy()
    source = await repository.get_protected_runtime_process_scheduling_authorization_source(
        WorkflowProtectedRuntimeProcessSchedulingAuthorizationSourceRequest(
            process_creation_result_id=process_creation_result_id,
            scope=scope,
            consumer_subject_id=policy.consumer_subject_id,
            consumer_audience=policy.consumer_audience,
            consumer_contract_id=policy.consumer_contract_id,
            consumer_contract_version=policy.consumer_contract_version,
        )
    )
    assert source is not None
    result = source.result
    attempt = source.attempt
    creation_lease = source.process_creation_authorization_lease
    requested_at = await repository.get_authoritative_time()
    nonce_digest = canonical_digest(
        {"nonce": uuid4().hex, "process_creation_result_id": result.result_id}
    )
    attestation_request = WorkflowProtectedRuntimeProcessSchedulingStateAttestationRequest(
        process_creation_result_id=result.result_id,
        process_creation_result_digest=result.canonical_digest,
        process_creation_consumption_id=result.consumption_id,
        process_creation_attempt_id=attempt.attempt_id,
        process_creation_attempt_digest=attempt.canonical_digest,
        process_creation_claim_id=source.process_creation_claim.claim_id,
        process_creation_claim_digest=source.process_creation_claim.canonical_digest,
        process_creation_authorization_lease_id=creation_lease.authorization_lease_id,
        process_creation_authorization_lease_digest=creation_lease.canonical_digest,
        process_creation_authorization_claim_id=(
            source.process_creation_authorization_claim.claim_id
        ),
        process_creation_authorization_claim_digest=(
            source.process_creation_authorization_claim.canonical_digest
        ),
        process_creation_receipt_digest=source.process_creation_receipt.canonical_digest,
        destination_deployment_id=result.scope.site_id,
        destination_generation=attempt.runtime_envelope_generation,
        destination_fencing_token_digest=attempt.runtime_envelope_commitment,
        protected_slot_commitment=attempt.runtime_envelope_commitment,
        protected_slot_generation=attempt.runtime_envelope_generation,
        runtime_envelope_id=attempt.runtime_envelope_id,
        runtime_envelope_commitment=result.runtime_envelope_commitment,
        runtime_envelope_generation=result.runtime_envelope_generation,
        process_creation_profile_id=result.process_creation_profile_id,
        process_creation_profile_version=result.process_creation_profile_version,
        process_creation_profile_digest=result.process_creation_profile_digest,
        primitive_id=result.primitive_id,
        primitive_version=result.primitive_version,
        primitive_digest=result.primitive_digest,
        scheduling_profile_id=policy.scheduling_profile_id,
        scheduling_profile_version=policy.scheduling_profile_version,
        scheduling_profile_digest=policy.scheduling_profile_digest,
        scope=result.scope,
        consumer_subject_id=policy.consumer_subject_id,
        consumer_audience=policy.consumer_audience,
        consumer_contract_id=policy.consumer_contract_id,
        consumer_contract_version=policy.consumer_contract_version,
        purpose_id=policy.purpose_id,
        request_nonce_digest=nonce_digest,
        requested_at=requested_at,
    )
    attestation = await attestor.attest_runtime_process_scheduling_state(attestation_request)
    idempotency_digest = canonical_digest(
        {
            "idempotency_key": idempotency_key,
            "scope": scope.canonical_value(),
            "subject_id": policy.consumer_subject_id,
        }
    )
    fingerprint = canonical_digest(
        {
            "policy_digest": policy.canonical_digest,
            "scope": scope.canonical_value(),
            "process_creation_result_id": result.result_id,
            "subject_id": policy.consumer_subject_id,
            "single_use_nonrenewable_nontransferable_future_request_acknowledged": True,
            "no_scheduling_resume_dispatch_or_execution_authority_acknowledged": True,
        }
    )
    source_values: dict[str, object] = {
        "process_creation_result_id": result.result_id,
        "process_creation_result_digest": result.canonical_digest,
        "process_creation_consumption_id": result.consumption_id,
        "process_creation_attempt_id": attempt.attempt_id,
        "process_creation_attempt_digest": attempt.canonical_digest,
        "process_creation_claim_id": source.process_creation_claim.claim_id,
        "process_creation_claim_digest": source.process_creation_claim.canonical_digest,
        "process_creation_authorization_lease_id": creation_lease.authorization_lease_id,
        "process_creation_authorization_lease_digest": creation_lease.canonical_digest,
        "process_creation_authorization_claim_id": (
            source.process_creation_authorization_claim.claim_id
        ),
        "process_creation_authorization_claim_digest": (
            source.process_creation_authorization_claim.canonical_digest
        ),
        "process_creation_receipt_digest": source.process_creation_receipt.canonical_digest,
        "process_creation_result_state": result.result_state,
        "process_creation_failure_class": result.failure_class,
        "process_creation_outcome_known": result.outcome_known,
        "process_created": result.process_created,
        "process_sealed": result.process_sealed,
        "process_suspended": result.process_suspended,
        "process_scheduled": result.process_scheduled,
        "process_resumed": result.process_resumed,
        "process_dispatched": result.process_dispatched,
        "process_executed": result.process_executed,
        "process_creation_completed_at": result.completed_at,
        "process_creation_result_recorded_at": result.recorded_at,
        "destination_deployment_id": result.scope.site_id,
        "destination_generation": attempt.runtime_envelope_generation,
        "destination_fencing_token_digest": attempt.runtime_envelope_commitment,
        "protected_slot_commitment": attempt.runtime_envelope_commitment,
        "protected_slot_generation": attempt.runtime_envelope_generation,
        "runtime_envelope_id": attempt.runtime_envelope_id,
        "runtime_envelope_commitment": result.runtime_envelope_commitment,
        "runtime_envelope_generation": result.runtime_envelope_generation,
        "process_creation_profile_id": result.process_creation_profile_id,
        "process_creation_profile_version": result.process_creation_profile_version,
        "process_creation_profile_digest": result.process_creation_profile_digest,
        "primitive_id": result.primitive_id,
        "primitive_version": result.primitive_version,
        "primitive_digest": result.primitive_digest,
        "scope": result.scope,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
    }
    audit_payload = {
        "policy_digest": policy.canonical_digest,
        "request_fingerprint": fingerprint,
        "scope": scope.canonical_value(),
        "process_creation_result_id": result.result_id,
    }
    claim_values = {
        **source_values,
        "claim_id": f"workflow-protected-runtime-process-scheduling-claim.{uuid4().hex}",
        "request_fingerprint": fingerprint,
        "idempotency_digest": idempotency_digest,
        "authorization_audit_digest": canonical_digest(audit_payload),
        "claimed_at": requested_at,
        "authority": WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority(),
    }
    claim = WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim(
        **cast(Any, claim_values),
        canonical_digest=canonical_digest(_payload(claim_values)),
    )
    lease_values = {
        **source_values,
        "authorization_lease_id": (
            f"workflow-protected-runtime-process-scheduling-authorization-lease.{uuid4().hex}"
        ),
        "claim_id": claim.claim_id,
        "claim_digest": claim.canonical_digest,
        "process_state_attestation_id": attestation.attestation_id,
        "process_state_attestation_digest": attestation.canonical_digest,
        "process_state_attestation_valid_until": attestation.valid_until,
        "process_state_eligible_until": attestation.process_state_eligible_until,
        "attestation_metadata_only": True,
        "scheduling_profile_id": policy.scheduling_profile_id,
        "scheduling_profile_version": policy.scheduling_profile_version,
        "scheduling_profile_digest": policy.scheduling_profile_digest,
        "issued_at": requested_at,
        "valid_until": attestation.valid_until,
        "effective_until": attestation.valid_until,
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        "authority": WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority(
            protected_runtime_process_scheduling_authority_granted=True
        ),
    }
    lease = WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease(
        **cast(Any, lease_values),
        canonical_digest=canonical_digest(_payload(lease_values)),
    )
    return WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseRequest(
        source=source,
        process_state_attestation=attestation,
        expected_request_nonce_digest=nonce_digest,
        offline_signature_verifier=attestor,
        offline_process_creation_receipt_signature_verifier=receipt_verifier,
        expected_policy_digest=policy.canonical_digest,
        expected_validity_window_seconds=policy.maximum_lifetime_seconds,
        scope=scope,
        consumer_subject_id=policy.consumer_subject_id,
        consumer_audience=policy.consumer_audience,
        pre_attestation_observed_at=requested_at,
        requested_at=requested_at,
        candidate_claim=claim,
        candidate=lease,
        idempotency_key=idempotency_key,
        idempotency_digest=idempotency_digest,
        request_fingerprint=fingerprint,
    )


def _payload(values: dict[str, object]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if hasattr(value, "isoformat")
            else value.value
            if hasattr(value, "value")
            else value.canonical_value()
            if hasattr(value, "canonical_value")
            else value
        )
        for name, value in values.items()
    }


async def _cleanup_scheduling(engine: AsyncEngine, *, process_creation_result_id: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        for table in (
            "workflow_event_runtime_process_scheduling_auth_claims",
            "workflow_event_runtime_process_scheduling_auth_leases",
        ):
            await connection.execute(
                text(f"DELETE FROM {table} WHERE process_creation_result_id = :result_id"),
                {"result_id": process_creation_result_id},
            )
        await connection.execute(text("SET LOCAL session_replication_role = origin"))


@pytest.mark.asyncio
async def test_live_postgres_exact_race_changed_replay_one_winner_and_append_only() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url)
    repository = _FixtureProcessCreationRepository(engine=engine)
    repository.bind_protected_runtime_start_receipt_signature_verifier(
        cast(Any, _AcceptAllReceiptVerifier())
    )
    receipt_verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier(
            development_enabled=True
        )
    )
    repository.bind_protected_runtime_process_creation_receipt_signature_verifier(receipt_verifier)
    seeded: list[Any] = []
    readiness_result: Any | None = None
    creation_lease_id: str | None = None
    process_creation_result_id: str | None = None
    try:
        start_request, readiness_result, creation_lease_id = await _seed_created_process(
            engine,
            repository,
            receipt_verifier=receipt_verifier,
            suffix=f"imp229-scheduling-{uuid4().hex[:12]}",
        )
        seeded.append(start_request)
        async with repository._sessions() as session:
            process_creation_result_id = cast(
                str,
                await session.scalar(
                    select(WorkflowProtectedRuntimeProcessCreationResultModel.result_id).where(
                        WorkflowProtectedRuntimeProcessCreationResultModel.authorization_lease_id
                        == creation_lease_id
                    )
                ),
            )
        attestor = _SchedulingStateAttestor()
        idempotency_key = f"imp-229-scheduling-{uuid4().hex}"
        request = await _authorization_request(
            repository,
            process_creation_result_id=process_creation_result_id,
            scope=readiness_result.scope,
            idempotency_key=idempotency_key,
            attestor=attestor,
            receipt_verifier=receipt_verifier,
        )
        exact = await asyncio.gather(
            repository.authorize_protected_runtime_process_scheduling(request),
            repository.authorize_protected_runtime_process_scheduling(request),
        )
        assert {item.status for item in exact} == {
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus.AUTHORIZED,
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus.REPLAY,
        }
        first = next(item.lease for item in exact if item.lease is not None)
        assert first is not None
        assert all(item.lease == first for item in exact)
        assert first.valid_until - first.issued_at <= timedelta(seconds=1)
        assert first.authority.protected_runtime_process_scheduling_authority_granted is True
        assert not any(
            value
            for name, value in first.authority.canonical_value().items()
            if name != "protected_runtime_process_scheduling_authority_granted"
        )

        claim_table = cast(
            Table, WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaimModel.__table__
        )
        lease_table = cast(
            Table, WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseModel.__table__
        )
        async with engine.connect() as connection:
            claim_row = (
                (
                    await connection.execute(
                        select(claim_table).where(
                            claim_table.c.process_creation_result_id == process_creation_result_id
                        )
                    )
                )
                .mappings()
                .one()
            )
            lease_row = (
                (
                    await connection.execute(
                        select(lease_table).where(
                            lease_table.c.process_creation_result_id == process_creation_result_id
                        )
                    )
                )
                .mappings()
                .one()
            )
        assert claim_row["authorization_lease_id"] == lease_row["authorization_lease_id"]
        assert lease_row["claim_id"] == claim_row["claim_id"]
        assert lease_row["claim_digest"] == claim_row["canonical_digest"]

        policy = code_owned_workflow_protected_runtime_process_scheduling_authorization_policy()
        changed = await repository.preflight_protected_runtime_process_scheduling_authorization(
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightRequest(
                process_creation_result_id=process_creation_result_id,
                scope=readiness_result.scope,
                consumer_subject_id=policy.consumer_subject_id,
                consumer_audience=policy.consumer_audience,
                policy_id=policy.policy_id,
                policy_version=policy.policy_version,
                policy_digest=policy.canonical_digest,
                idempotency_key=idempotency_key,
                idempotency_digest=cast(str, claim_row["idempotency_digest"]),
                request_fingerprint="a" * 64,
                offline_signature_verifier=attestor,
                offline_process_creation_receipt_signature_verifier=receipt_verifier,
            )
        )
        assert (
            changed.status
            is (
                WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightStatus
            ).IDEMPOTENCY_CONFLICT
        )
        assert changed.lease is None

        await asyncio.sleep(1.05)
        replay = await repository.preflight_protected_runtime_process_scheduling_authorization(
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightRequest(
                process_creation_result_id=process_creation_result_id,
                scope=readiness_result.scope,
                consumer_subject_id=policy.consumer_subject_id,
                consumer_audience=policy.consumer_audience,
                policy_id=policy.policy_id,
                policy_version=policy.policy_version,
                policy_digest=policy.canonical_digest,
                idempotency_key=idempotency_key,
                idempotency_digest=cast(str, claim_row["idempotency_digest"]),
                request_fingerprint=cast(str, claim_row["request_fingerprint"]),
                offline_signature_verifier=attestor,
                offline_process_creation_receipt_signature_verifier=receipt_verifier,
            )
        )
        assert (
            replay.status
            is WorkflowProtectedRuntimeProcessSchedulingAuthorizationPreflightStatus.REPLAY
        )
        assert replay.lease == first

        competing = await _authorization_request(
            repository,
            process_creation_result_id=process_creation_result_id,
            scope=readiness_result.scope,
            idempotency_key=f"imp-229-competing-{uuid4().hex}",
            attestor=attestor,
            receipt_verifier=receipt_verifier,
        )
        denied = await repository.authorize_protected_runtime_process_scheduling(competing)
        assert (
            denied.status
            is WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseStatus.ALREADY_AUTHORIZED
        )
        assert denied.lease is None

        for table, key, value in (
            (lease_table, "authorization_lease_id", first.authorization_lease_id),
            (claim_table, "claim_id", first.claim_id),
        ):
            async with engine.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError, match="append-only"):
                    await connection.execute(
                        table.update()
                        .where(table.c[key] == value)
                        .values(canonical_digest="a" * 64)
                    )
                await transaction.rollback()
            async with engine.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError, match="append-only"):
                    await connection.execute(table.delete().where(table.c[key] == value))
                await transaction.rollback()
    finally:
        if process_creation_result_id is not None:
            await _cleanup_scheduling(engine, process_creation_result_id=process_creation_result_id)
        if creation_lease_id is not None:
            await _cleanup_consumption(engine, authorization_lease_id=creation_lease_id)
        if readiness_result is not None:
            await _cleanup_process_creation(engine, readiness_result_id=readiness_result.result_id)
            await _cleanup_fixture_fences(
                engine,
                repository,
                readiness_result_id=readiness_result.result_id,
            )
        if seeded:
            await _cleanup_readiness(engine, tuple(seeded))
        await engine.dispose()
