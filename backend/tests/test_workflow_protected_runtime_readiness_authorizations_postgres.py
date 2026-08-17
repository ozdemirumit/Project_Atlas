from __future__ import annotations

import ast
import asyncio
import os
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import Table, func, insert, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from test_workflow_protected_runtime_start_consumption_postgres import (
    _claim_request as _runtime_start_claim_request,
)
from test_workflow_protected_runtime_start_consumption_postgres import (
    _model_values,
    _seed_actual_repository_path,
    _valid_runtime_start_authorization_evidence,
)
from test_workflow_protected_runtime_start_consumptions import _service as _runtime_start_service

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeReadinessAuthorizationClaimModel,
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel,
    WorkflowProtectedRuntimeStartConsumptionResultModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application.protected_runtime_readiness_authorization_ports import (
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeReadinessAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeReadinessAuthorizationPresentationState,
    WorkflowProtectedRuntimeReadinessAuthorizationSourceRequest,
    WorkflowProtectedRuntimeReadinessLifecycleAttestation,
)
from atlas.modules.workflows.application.protected_runtime_readiness_authorizations import (
    WorkflowProtectedRuntimeReadinessAuthorizationService,
)
from atlas.modules.workflows.application.protected_runtime_start_consumption_ports import (
    WorkflowProtectedRuntimeStartConsumptionResultRequest,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WorkflowProtectedRuntimeStartConsumptionResultState,
    WorkflowProtectedRuntimeStartReceipt,
    code_owned_workflow_protected_runtime_start_consumption_policy,
)

POSTGRES_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "atlas"
    / "modules"
    / "workflows"
    / "adapters"
    / "postgres.py"
)
SOURCE = POSTGRES_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
REPOSITORY = next(
    node
    for node in TREE.body
    if isinstance(node, ast.ClassDef) and node.name == "PostgreSQLWorkflowPlanRepository"
)


def _method_source(name: str) -> str:
    node = next(
        item
        for item in REPOSITORY.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    return ast.get_source_segment(SOURCE, node) or ""


def test_repository_declares_readiness_models_ports_and_locked_sources() -> None:
    for symbol in (
        "WorkflowProtectedRuntimeReadinessAuthorizationClaimModel",
        "WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel",
        "WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest",
        "WorkflowProtectedRuntimeReadinessAuthorizationPreflightRequest",
        "WorkflowProtectedRuntimeReadinessAuthorizationPresentation",
        "WorkflowProtectedRuntimeReadinessLifecycleAttestation",
        "WorkflowProtectedRuntimeReadinessLifecycleSignatureVerifier",
        "_ProtectedRuntimeReadinessAuthorizationLockedSources",
    ):
        assert symbol in SOURCE


def test_preflight_is_durable_replay_first_and_never_attests() -> None:
    preflight = _method_source("preflight_protected_runtime_readiness_authorization")

    assert "_lock_protected_runtime_readiness_authorization_rows" in preflight
    assert "_protected_runtime_readiness_idempotency_claim" in preflight
    assert "_protected_runtime_readiness_verified_replay_lease" in preflight
    assert "offline_signature_verifier" in preflight
    assert "offline_start_receipt_signature_verifier" in preflight
    assert "attest_runtime_readiness_lifecycle" not in preflight
    assert "session.add" not in preflight


def test_lock_loads_complete_source_with_prelock_database_time_in_one_join() -> None:
    lock = _method_source("_lock_protected_runtime_readiness_authorization_rows")

    assert lock.count("clock_timestamp") == 4
    assert '.cte("runtime_readiness_first_observation")' in lock
    assert '.prefix_with("MATERIALIZED")' in lock
    assert ".join(first_observation, true())" in lock
    assert "first_observation.c.first_observed_at" in lock
    assert "_lock_protected_runtime_start_authorization_rows" not in lock
    assert "source_scope = and_(" in lock
    assert "consumer_subject_id" in lock
    assert "consumer_audience" in lock
    assert "source_statement = (" in lock
    assert "await session.execute(locked(source_statement))" in lock
    assert "prior_claim_exists, prior_lease_exists, observed_at" in lock
    assert "exists(select(literal(1)).where(or_(*claim_filters)))" in lock
    assert "exists(select(literal(1)).where(lease_filter))" in lock
    assert "if not prior_claim_exists and not prior_lease_exists:" in lock
    assert lock.index("if not prior_claim_exists and not prior_lease_exists:") < lock.index(
        "existing_claims ="
    )
    assert "session.get" not in lock
    for model in (
        "WorkflowProtectedRuntimeContextUseClaimModel",
        "WorkflowProtectedRuntimeContextUseAttemptModel",
        "WorkflowProtectedRuntimeContextUseResultModel",
        "WorkflowProtectedRuntimeStartAuthorizationClaimModel",
        "WorkflowProtectedRuntimeStartAuthorizationLeaseModel",
        "WorkflowProtectedRuntimeStartConsumptionClaimModel",
        "WorkflowProtectedRuntimeStartConsumptionAttemptModel",
        "WorkflowProtectedRuntimeStartConsumptionResultModel",
        "WorkflowProtectedRuntimeContextInjectionDestinationHeadModel",
        "WorkflowProtectedRuntimeContextInjectionSlotHeadModel",
        "WorkflowProtectedRuntimeStartCoordinationHeadModel",
    ):
        assert model in lock
    assert lock.index("source_statement = (") < lock.index("existing_claims =")
    assert lock.index("existing_claims =") < lock.index("existing_leases =")
    assert "with_for_update" in lock


def test_source_accepts_only_signed_successful_terminal_start() -> None:
    source = _method_source("_protected_runtime_readiness_source_from_locked")

    assert "RUNTIME_STARTED_IN_PROTECTED_BOUNDARY" in source
    assert "runtime_started is True" in source
    assert "starter_receipt" in source
    assert "receipt_verifier=receipt_verifier" in source
    assert 'head.state == "start_attempt_terminal"' in source
    assert "head.runtime_start_attempt_terminal" in source
    assert "head.runtime_start_result_digest == start_result.canonical_digest" in source
    assert "destination.destination_fencing_token_digest" in source
    assert "slot.runtime_slot_commitment" in source
    assert 'slot.slot_state == "context_used_terminal"' in source


def test_authorize_replays_before_retiming_and_has_one_winner_recovery() -> None:
    authorize = _method_source("authorize_protected_runtime_readiness")

    assert authorize.index("_protected_runtime_readiness_replay") < authorize.index(
        "_protected_runtime_readiness_retimed_request"
    )
    assert "validate_workflow_protected_runtime_readiness_authorization_request" in (
        _method_source("_protected_runtime_readiness_evidence_matches")
    )
    assert "except (IntegrityError, TypeError, ValueError)" in authorize
    assert authorize.count("_lock_protected_runtime_readiness_authorization_rows") == 2
    assert authorize.count("_protected_runtime_readiness_replay") == 2
    assert "session.flush" in authorize
    assert "session.commit" in authorize
    assert authorize.index("_protected_runtime_readiness_evidence_matches") < authorize.index(
        "final_observed_at ="
    )
    assert authorize.index("final_observed_at =") < authorize.index("session.add")
    assert "_protected_runtime_readiness_final_window_matches" in authorize


def test_evidence_uses_offline_signatures_and_both_database_observations() -> None:
    evidence = _method_source("_protected_runtime_readiness_evidence_matches")
    signature = _method_source("_protected_runtime_readiness_attestation_signature_valid")

    assert "offline_start_receipt_signature_verifier" in evidence
    assert "offline_signature_verifier" in evidence
    assert "locked.first_observed_at" in evidence
    assert "locked.observed_at" in evidence
    assert "attestation.valid_until" in evidence
    assert "attestation.runtime_envelope_eligible_until" in evidence
    assert "verify_runtime_readiness_lifecycle_attestation" in signature
    assert "verify_runtime_readiness_eligibility_attestation" not in signature
    assert "candidate.lifecycle_attestation_valid_until == attestation.valid_until" in evidence
    assert "candidate.runtime_envelope_eligible_until" in evidence


def test_repository_path_has_no_probe_or_operational_io() -> None:
    methods = "\n".join(
        _method_source(name)
        for name in (
            "preflight_protected_runtime_readiness_authorization",
            "authorize_protected_runtime_readiness",
            "_lock_protected_runtime_readiness_authorization_rows",
            "_protected_runtime_readiness_evidence_matches",
        )
    ).lower()

    for forbidden in (
        "readiness_prober",
        "probe_runtime",
        "httpx",
        "requests.",
        "socket.",
        "connector_client",
        "mcp_client",
        "process_manager",
        "subprocess",
    ):
        assert forbidden not in methods


def test_presentations_are_read_only_append_only_projections() -> None:
    presentation = _method_source("list_protected_runtime_readiness_authorization_presentations")

    assert "WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel" in presentation
    assert "statement_timestamp" in presentation
    assert "session.execute" in presentation
    assert "session.add" not in presentation
    assert "session.delete" not in presentation
    assert "session.commit" not in presentation
    assert "update(" not in presentation


class _AcceptAllReceiptVerifier:
    available = True

    def verify_receipt(self, receipt: object) -> bool:
        del receipt
        return True


class _ExactLifecycleVerifier:
    def __init__(self, *, delay_seconds: float = 0) -> None:
        self._delay_seconds = delay_seconds

    def verify_runtime_readiness_lifecycle_attestation(self, attestation: object) -> bool:
        del attestation
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        return True


class _AliasOnlyLifecycleVerifier:
    def verify_runtime_readiness_eligibility_attestation(self, attestation: object) -> bool:
        del attestation
        return True


class _UnusedAttestor:
    available = True


class _UnusedAuditSink:
    async def record(self, record: object) -> None:
        del record


async def _seed_successful_runtime_start(
    connection: Any,
    repository: PostgreSQLWorkflowPlanRepository,
    *,
    suffix: str,
) -> tuple[Any, WorkflowProtectedRuntimeStartReceipt]:
    database_now = cast(datetime, await connection.scalar(select(func.clock_timestamp())))
    (
        source,
        runtime_context_models,
        authorization_attestation,
    ) = await _valid_runtime_start_authorization_evidence(
        repository,
        base=database_now,
    )
    request = _runtime_start_claim_request(
        base=database_now,
        suffix=suffix,
        source=source,
    )
    await _seed_actual_repository_path(
        connection,
        repository,
        request,
        seed_consumption=True,
        runtime_context_models=runtime_context_models,
        authorization_attestation=authorization_attestation,
    )
    attempt = request.candidate_attempt
    instruction = request.signed_instruction_envelope.instruction
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()
    receipt_values: dict[str, object] = {
        "consumption_id": attempt.consumption_id,
        "attempt_id": attempt.attempt_id,
        "instruction_digest": instruction.canonical_digest,
        "protected_operation_reference": attempt.protected_operation_reference,
        "authorization_lease_id": attempt.authorization_lease_id,
        "destination_deployment_id": attempt.destination_deployment_id,
        "destination_generation": attempt.destination_generation,
        "destination_fencing_token_digest": attempt.destination_fencing_token_digest,
        "runtime_slot_commitment": attempt.runtime_slot_commitment,
        "runtime_slot_generation": attempt.runtime_slot_generation,
        "runtime_envelope_id": attempt.runtime_envelope_id,
        "runtime_envelope_commitment": attempt.runtime_envelope_commitment,
        "runtime_envelope_generation": attempt.runtime_envelope_generation,
        "request_nonce_digest": attempt.request_nonce_digest,
        "result_state": (
            WorkflowProtectedRuntimeStartConsumptionResultState
        ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY,
        "runtime_started": True,
        "runtime_start_count_pre": 0,
        "runtime_start_count_post": 1,
        "runtime_envelope_current": True,
        "runtime_envelope_inactive": False,
        "residual_process_absent": True,
        "residual_task_absent": True,
        "scheduling_performed": False,
        "runtime_resumed": False,
        "generic_process_created": False,
        "prompt_constructed": False,
        "model_inference_performed": False,
        "network_activity_performed": False,
        "readiness_probe_performed": False,
        "publication_performed": False,
        "delivery_performed": False,
        "connector_activity_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
        "starter_contract_id": policy.required_starter_contract_id,
        "starter_contract_version": policy.required_starter_contract_version,
        "starter_id": policy.approved_starter_id,
        "starter_version": policy.approved_starter_version,
        "signing_key_id": policy.receipt_verification_signing_key_id,
        "signature_algorithm": policy.receipt_signature_algorithm,
        "completed_at": attempt.started_at + timedelta(milliseconds=100),
        "integrity_signature": "e" * 64,
    }
    receipt = WorkflowProtectedRuntimeStartReceipt(
        **cast(Any, receipt_values),
        canonical_digest=canonical_digest(
            {
                name: (
                    value.isoformat()
                    if isinstance(value, datetime)
                    else value.value
                    if hasattr(value, "value")
                    else value
                )
                for name, value in receipt_values.items()
            }
        ),
    )
    service, _, _ = _runtime_start_service()
    result = service._build_receipted_result(
        claim=request.candidate_claim,
        attempt=attempt,
        receipt=receipt,
        recorded_at=receipt.completed_at + timedelta(milliseconds=50),
    )
    result_request = WorkflowProtectedRuntimeStartConsumptionResultRequest(
        result=result,
        receipt=receipt,
        expected_claim_digest=request.candidate_claim.canonical_digest,
        expected_attempt_digest=attempt.canonical_digest,
    )
    attempt_model = repository._protected_runtime_start_consumption_attempt_model(request)
    result_model = repository._protected_runtime_start_consumption_result_model(
        result_request,
        attempt_row=attempt_model,
    )
    await connection.execute(text("SET LOCAL session_replication_role = replica"))
    await connection.execute(
        insert(cast(Table, WorkflowProtectedRuntimeStartConsumptionResultModel.__table__)),
        _model_values(result_model),
    )
    await connection.execute(
        text(
            "UPDATE workflow_event_runtime_start_coordination_heads "
            "SET state = 'start_attempt_terminal', runtime_start_result_id = :result_id, "
            "runtime_start_result_digest = :result_digest, "
            "runtime_start_attempt_pending = FALSE, "
            "runtime_start_attempt_terminal = TRUE, runtime_started = TRUE, "
            "version = version + 1, updated_at = :updated_at "
            "WHERE runtime_envelope_id = :runtime_envelope_id"
        ),
        {
            "result_id": result.result_id,
            "result_digest": result.canonical_digest,
            "runtime_envelope_id": attempt.runtime_envelope_id,
            "updated_at": result.recorded_at,
        },
    )
    await connection.execute(text("SET LOCAL session_replication_role = origin"))
    return request, receipt


def _lifecycle_attestation(
    service: WorkflowProtectedRuntimeReadinessAuthorizationService,
    source: Any,
    *,
    requested_at: datetime,
    validity_milliseconds: int = 1_000,
) -> tuple[WorkflowProtectedRuntimeReadinessLifecycleAttestation, str]:
    nonce = canonical_digest({"nonce": uuid4().hex})
    attestation_request = service._attestation_request(
        source,
        nonce_digest=nonce,
        requested_at=requested_at,
    )
    request_values = {
        name: getattr(attestation_request, name)
        for name in attestation_request.__slots__
        if name != "requested_at"
    }
    valid_until = requested_at + timedelta(milliseconds=validity_milliseconds)
    values: dict[str, object] = {
        **request_values,
        "attestation_id": f"runtime-readiness-attestation.{uuid4().hex}",
        "attestor_id": service.policy.required_attestor_id,
        "attestor_version": service.policy.required_attestor_version,
        "signing_key_id": service.policy.verification_signing_key_id,
        "signature_algorithm": "hmac-sha256",
        "observed_at": requested_at,
        "valid_until": valid_until,
        "runtime_envelope_eligible_until": valid_until,
        "exact_start_result_confirmed": True,
        "runtime_started_confirmed": True,
        "runtime_envelope_current": True,
        "runtime_envelope_started": True,
        "destination_generation_current": True,
        "destination_fence_current": True,
        "protected_slot_generation_current": True,
        "readiness_profile_eligible": True,
        "prior_readiness_claim_absent": True,
        "prior_readiness_lease_absent": True,
        "prior_readiness_attempt_absent": True,
        "prior_readiness_result_absent": True,
        "runtime_resumed": False,
        "runtime_stopped": False,
        "runtime_restarted": False,
        "generic_process_created": False,
        "scheduling_performed": False,
        "readiness_probe_performed": False,
        "network_activity_performed": False,
        "connector_activity_performed": False,
        "publication_performed": False,
        "delivery_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
        "runtime_locator_included": False,
        "process_identifier_included": False,
        "context_included": False,
        "endpoint_included": False,
        "credential_included": False,
        "secret_included": False,
        "command_included": False,
        "integrity_signature": "4" * 64,
    }
    attestation = WorkflowProtectedRuntimeReadinessLifecycleAttestation(
        **cast(Any, values), canonical_digest="0" * 64
    )
    return (
        replace(
            attestation,
            canonical_digest=canonical_digest(attestation.digest_payload()),
        ),
        nonce,
    )


async def _authorization_request(
    repository: PostgreSQLWorkflowPlanRepository,
    source: Any,
    *,
    idempotency_key: str,
    lifecycle_verifier: Any,
    validity_milliseconds: int = 1_000,
) -> WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest:
    receipt_verifier = _AcceptAllReceiptVerifier()
    service = WorkflowProtectedRuntimeReadinessAuthorizationService(
        authorization_repository=cast(Any, repository),
        lifecycle_attestor=cast(Any, _UnusedAttestor()),
        lifecycle_signature_verifier=cast(Any, lifecycle_verifier),
        start_receipt_signature_verifier=cast(Any, receipt_verifier),
        audit_sink=cast(Any, _UnusedAuditSink()),
    )
    first_observed_at = await repository.get_authoritative_time()
    attestation, nonce = _lifecycle_attestation(
        service,
        source,
        requested_at=first_observed_at,
        validity_milliseconds=validity_milliseconds,
    )
    issued_at = await repository.get_authoritative_time()
    idempotency_digest = canonical_digest(
        {
            "idempotency_key": idempotency_key,
            "scope": source.result.scope.canonical_value(),
            "subject_id": service.policy.consumer_subject_id,
        }
    )
    fingerprint = canonical_digest(
        {
            "policy_digest": service.policy.canonical_digest,
            "scope": source.result.scope.canonical_value(),
            "start_result_digest": source.result.canonical_digest,
            "start_result_id": source.result.result_id,
            "subject_id": service.policy.consumer_subject_id,
        }
    )
    claim, lease = service._build_candidates(
        source=source,
        attestation=attestation,
        issued_at=issued_at,
        idempotency_digest=idempotency_digest,
        request_fingerprint=fingerprint,
    )
    return WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest(
        source=source,
        lifecycle_attestation=attestation,
        expected_request_nonce_digest=nonce,
        offline_signature_verifier=cast(Any, lifecycle_verifier),
        offline_start_receipt_signature_verifier=cast(Any, receipt_verifier),
        expected_policy_digest=service.policy.canonical_digest,
        expected_validity_window_seconds=service.policy.maximum_lifetime_seconds,
        scope=source.result.scope,
        consumer_subject_id=service.policy.consumer_subject_id,
        consumer_audience=service.policy.consumer_audience,
        pre_attestation_observed_at=first_observed_at,
        requested_at=issued_at,
        candidate_claim=claim,
        candidate=lease,
        idempotency_key=idempotency_key,
        idempotency_digest=idempotency_digest,
        request_fingerprint=fingerprint,
    )


async def _assert_authorization_preconditions(
    repository: PostgreSQLWorkflowPlanRepository,
    request: WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest,
) -> None:
    async with repository._sessions() as session:
        locked = await repository._lock_protected_runtime_readiness_authorization_rows(
            session,
            start_result_id=request.source.result.result_id,
            scope=request.scope,
            consumer_subject_id=request.consumer_subject_id,
            consumer_audience=request.consumer_audience,
            idempotency_key=request.idempotency_key,
        )
        working = repository._protected_runtime_readiness_retimed_request(
            request, issued_at=locked.observed_at
        )
        source = repository._protected_runtime_readiness_source_from_locked(
            locked,
            receipt_verifier=request.offline_start_receipt_signature_verifier,
        )
        attestation = working.lifecycle_attestation
        candidate = working.candidate
        checks = {
            "source": source == working.source,
            "signature": repository._protected_runtime_readiness_attestation_signature_valid(
                working.offline_signature_verifier, attestation
            ),
            "result_before_pre_attestation": (
                working.source.result.recorded_at <= working.pre_attestation_observed_at
            ),
            "pre_attestation_before_observed": (
                working.pre_attestation_observed_at <= attestation.observed_at
            ),
            "attestation_before_first_lock": (attestation.observed_at <= locked.first_observed_at),
            "lock_order": locked.first_observed_at <= locked.observed_at,
            "attestation_active": locked.observed_at < attestation.valid_until,
            "envelope_active": (locked.observed_at < attestation.runtime_envelope_eligible_until),
            "candidate_retimed": candidate.issued_at == locked.observed_at,
            "candidate_window": candidate.valid_until == candidate.effective_until,
            "no_prior_evidence": not locked.existing_claims and not locked.existing_leases,
            "full_evidence": repository._protected_runtime_readiness_evidence_matches(
                working, locked
            ),
        }
        assert all(checks.values()), checks

        final_observed_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
        final_working = repository._protected_runtime_readiness_retimed_request(
            request, issued_at=final_observed_at
        )
        assert repository._protected_runtime_readiness_final_window_matches(
            final_working,
            locked=locked,
            final_observed_at=final_observed_at,
        )
        audit_payload: dict[str, object] = {
            "start_result_id": final_working.candidate.start_result_id,
            "policy_digest": final_working.candidate.policy_digest,
            "request_fingerprint": final_working.request_fingerprint,
            "scope": final_working.scope.canonical_value(),
        }
        assert (
            canonical_digest(audit_payload)
            == final_working.candidate_claim.authorization_audit_digest
        )
        repository._protected_runtime_readiness_lease_model(
            final_working.candidate,
            final_working.lifecycle_attestation,
            locked=locked,
        )
        repository._protected_runtime_readiness_claim_model(
            final_working.candidate_claim,
            authorization_lease_id=final_working.candidate.authorization_lease_id,
            idempotency_key=final_working.idempotency_key,
            audit_payload=audit_payload,
            locked=locked,
        )
        await session.rollback()


async def _cleanup_runtime_start_sources(engine: Any, requests: tuple[Any, ...]) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        for request in requests:
            lease = request.source.authorization_lease
            start_result_id = (
                "workflow-protected-runtime-start-result."
                f"{request.candidate_attempt.attempt_id.rsplit('.', 1)[-1]}"
            )
            parameters = {
                "start_result_id": start_result_id,
                "authorization_lease_id": lease.authorization_lease_id,
                "runtime_envelope_id": lease.runtime_envelope_id,
                "use_result_id": lease.use_result_id,
                "use_attempt_id": lease.use_attempt_id,
                "use_claim_id": lease.use_claim_id,
                "deployment_id": lease.destination_deployment_id,
                "slot_commitment": lease.runtime_slot_commitment,
            }
            for statement in (
                "DELETE FROM workflow_event_runtime_readiness_auth_claims "
                "WHERE start_result_id = :start_result_id",
                "DELETE FROM workflow_event_runtime_readiness_auth_leases "
                "WHERE start_result_id = :start_result_id",
                "DELETE FROM workflow_event_runtime_start_consumption_results "
                "WHERE authorization_lease_id = :authorization_lease_id",
                "DELETE FROM workflow_event_runtime_start_consumption_attempts "
                "WHERE authorization_lease_id = :authorization_lease_id",
                "DELETE FROM workflow_event_runtime_start_consumption_claims "
                "WHERE authorization_lease_id = :authorization_lease_id",
                "DELETE FROM workflow_event_runtime_start_auth_claims "
                "WHERE authorization_lease_id = :authorization_lease_id",
                "DELETE FROM workflow_event_runtime_start_auth_leases "
                "WHERE authorization_lease_id = :authorization_lease_id",
                "DELETE FROM workflow_event_runtime_start_coordination_heads "
                "WHERE runtime_envelope_id = :runtime_envelope_id",
                "DELETE FROM workflow_protected_runtime_context_use_results "
                "WHERE result_id = :use_result_id",
                "DELETE FROM workflow_protected_runtime_context_use_attempts "
                "WHERE attempt_id = :use_attempt_id",
                "DELETE FROM workflow_protected_runtime_context_use_claims "
                "WHERE claim_id = :use_claim_id",
                "DELETE FROM workflow_protected_runtime_context_injection_slot_heads "
                "WHERE destination_deployment_id = :deployment_id "
                "AND runtime_slot_commitment = :slot_commitment",
            ):
                await connection.execute(text(statement), parameters)
        await connection.execute(text("SET LOCAL session_replication_role = origin"))


@pytest.mark.asyncio
async def test_live_postgres_readiness_repository_race_replay_scope_guards_and_expiry() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    seeded_requests: list[Any] = []
    repository = PostgreSQLWorkflowPlanRepository(engine=engine)
    receipt_verifier = _AcceptAllReceiptVerifier()
    repository.bind_protected_runtime_start_receipt_signature_verifier(cast(Any, receipt_verifier))
    try:
        async with engine.begin() as connection:
            first_seed, first_receipt = await _seed_successful_runtime_start(
                connection,
                repository,
                suffix=f"imp225-live-{uuid4().hex[:16]}",
            )
            seeded_requests.append(first_seed)
        del first_receipt

        first_result_id = (
            "workflow-protected-runtime-start-result."
            f"{first_seed.candidate_attempt.attempt_id.rsplit('.', 1)[-1]}"
        )
        async with engine.connect() as connection:
            first_result_digest = cast(
                str,
                await connection.scalar(
                    select(
                        WorkflowProtectedRuntimeStartConsumptionResultModel.canonical_digest
                    ).where(
                        WorkflowProtectedRuntimeStartConsumptionResultModel.result_id
                        == first_result_id
                    )
                ),
            )
        source_request = WorkflowProtectedRuntimeReadinessAuthorizationSourceRequest(
            start_result_id=first_result_id,
            start_result_digest=first_result_digest,
            scope=first_seed.candidate_attempt.scope,
            consumer_subject_id=first_seed.candidate_attempt.consumer_subject_id,
            consumer_audience=first_seed.candidate_attempt.consumer_audience,
            consumer_contract_id=first_seed.candidate_attempt.consumer_contract_id,
            consumer_contract_version=first_seed.candidate_attempt.consumer_contract_version,
        )
        source = await repository.get_protected_runtime_readiness_authorization_source(
            source_request
        )
        assert source is not None
        wrong_scope = WorkflowScope(
            "organization.cross-tenant",
            source.result.scope.environment_id,
            source.result.scope.site_id,
        )
        assert (
            await repository.get_protected_runtime_readiness_authorization_source(
                replace(source_request, scope=wrong_scope)
            )
            is None
        )

        exact_verifier = _ExactLifecycleVerifier()
        request = await _authorization_request(
            repository,
            source,
            idempotency_key=f"imp-225-race-{uuid4().hex}",
            lifecycle_verifier=exact_verifier,
        )
        await _assert_authorization_preconditions(repository, request)
        request = await _authorization_request(
            repository,
            source,
            idempotency_key=f"imp-225-race-{uuid4().hex}",
            lifecycle_verifier=exact_verifier,
        )
        first_outcome, second_outcome = await asyncio.wait_for(
            asyncio.gather(
                repository.authorize_protected_runtime_readiness(request),
                repository.authorize_protected_runtime_readiness(request),
            ),
            timeout=15,
        )
        assert {first_outcome.status, second_outcome.status} == {
            WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus.AUTHORIZED,
            WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus.REPLAY,
        }
        winner = (
            first_outcome
            if first_outcome.status
            is WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus.AUTHORIZED
            else second_outcome
        )
        assert winner.lease is not None

        alias_preflight = WorkflowProtectedRuntimeReadinessAuthorizationPreflightRequest(
            start_result_id=request.source.result.result_id,
            start_result_digest=request.source.result.canonical_digest,
            scope=request.scope,
            consumer_subject_id=request.consumer_subject_id,
            consumer_audience=request.consumer_audience,
            policy_id=request.candidate.policy_id,
            policy_version=request.candidate.policy_version,
            policy_digest=request.candidate.policy_digest,
            idempotency_key=request.idempotency_key,
            idempotency_digest=request.idempotency_digest,
            request_fingerprint=request.request_fingerprint,
            offline_signature_verifier=cast(Any, _AliasOnlyLifecycleVerifier()),
            offline_start_receipt_signature_verifier=cast(Any, receipt_verifier),
        )
        rejected_alias = await repository.preflight_protected_runtime_readiness_authorization(
            alias_preflight
        )
        assert (
            rejected_alias.status
            is WorkflowProtectedRuntimeReadinessAuthorizationPreflightStatus.EVIDENCE_CONFLICT
        )

        lease_table = cast(
            Table, WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel.__table__
        )
        claim_table = cast(
            Table, WorkflowProtectedRuntimeReadinessAuthorizationClaimModel.__table__
        )
        for table, key, value in (
            (lease_table, "authorization_lease_id", winner.lease.authorization_lease_id),
            (claim_table, "claim_id", winner.lease.claim_id),
        ):
            async with engine.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError, match="append-only"):
                    await connection.execute(
                        table.update()
                        .where(table.c[key] == value)
                        .values(canonical_digest="f" * 64)
                    )
                await transaction.rollback()
            async with engine.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError, match="append-only"):
                    await connection.execute(table.delete().where(table.c[key] == value))
                await transaction.rollback()
            async with engine.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError, match="append-only"):
                    await connection.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
                await transaction.rollback()

        downgrade_environment = os.environ.copy()
        downgrade_environment["ATLAS_DATABASE_URL"] = database_url
        downgrade = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", "downgrade", "20260817_0147"],
            cwd=Path(__file__).parents[1],
            env=downgrade_environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert downgrade.returncode != 0
        assert "refusing guarded downgrade" in (downgrade.stdout + downgrade.stderr)
        async with engine.connect() as connection:
            assert (
                await connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20260817_0148"
            )

        remaining = (
            winner.lease.effective_until - await repository.get_authoritative_time()
        ).total_seconds()
        if remaining > 0:
            await asyncio.sleep(remaining + 0.05)
        projection = await repository.list_protected_runtime_readiness_authorization_presentations(
            scope=winner.lease.scope,
            authorization_lease_ids=(winner.lease.authorization_lease_id,),
        )
        assert len(projection) == 1
        assert (
            projection[0].effective_state
            is WorkflowProtectedRuntimeReadinessAuthorizationPresentationState.EXPIRED
        )
        assert projection[0].protected_runtime_readiness_authority_granted is False

        await _cleanup_runtime_start_sources(engine, (first_seed,))
        seeded_requests.clear()

        async with engine.begin() as connection:
            second_seed, second_receipt = await _seed_successful_runtime_start(
                connection,
                repository,
                suffix=f"imp225-clock-{uuid4().hex[:16]}",
            )
            seeded_requests.append(second_seed)
        del second_receipt

        second_result_id = (
            "workflow-protected-runtime-start-result."
            f"{second_seed.candidate_attempt.attempt_id.rsplit('.', 1)[-1]}"
        )
        async with engine.connect() as connection:
            second_result_digest = cast(
                str,
                await connection.scalar(
                    select(
                        WorkflowProtectedRuntimeStartConsumptionResultModel.canonical_digest
                    ).where(
                        WorkflowProtectedRuntimeStartConsumptionResultModel.result_id
                        == second_result_id
                    )
                ),
            )
        second_source = await repository.get_protected_runtime_readiness_authorization_source(
            WorkflowProtectedRuntimeReadinessAuthorizationSourceRequest(
                start_result_id=second_result_id,
                start_result_digest=second_result_digest,
                scope=second_seed.candidate_attempt.scope,
                consumer_subject_id=second_seed.candidate_attempt.consumer_subject_id,
                consumer_audience=second_seed.candidate_attempt.consumer_audience,
                consumer_contract_id=second_seed.candidate_attempt.consumer_contract_id,
                consumer_contract_version=second_seed.candidate_attempt.consumer_contract_version,
            )
        )
        assert second_source is not None
        delayed_verifier = _ExactLifecycleVerifier(delay_seconds=0.2)
        expiring_request = await _authorization_request(
            repository,
            second_source,
            idempotency_key=f"imp-225-final-clock-{uuid4().hex}",
            lifecycle_verifier=delayed_verifier,
            validity_milliseconds=120,
        )
        expired = await repository.authorize_protected_runtime_readiness(expiring_request)
        assert (
            expired.status
            is WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus.EVIDENCE_CONFLICT
        )
        assert expired.lease is None
    finally:
        if seeded_requests:
            await _cleanup_runtime_start_sources(engine, tuple(seeded_requests))
        await engine.dispose()
