from __future__ import annotations

import asyncio
import inspect
import os
import re
from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, MetaData, Table, func, insert, null, select, text
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from test_workflow_protected_runtime_context_uses import NOW as CONTEXT_USE_NOW
from test_workflow_protected_runtime_context_uses import (
    _canonical_mapping as _runtime_context_use_canonical_mapping,
)
from test_workflow_protected_runtime_context_uses import (
    _service as _runtime_context_use_service,
)
from test_workflow_protected_runtime_context_uses_postgres import (
    _claim_request as _runtime_context_use_claim_request,
)
from test_workflow_protected_runtime_start_authorizations import (
    _Attestor as _RuntimeStartAuthorizationAttestor,
)
from test_workflow_protected_runtime_start_authorizations import (
    _ReceiptVerifier as _RuntimeStartAuthorizationReceiptVerifier,
)
from test_workflow_protected_runtime_start_authorizations import (
    _Repository as _RuntimeStartAuthorizationRepository,
)
from test_workflow_protected_runtime_start_authorizations import (
    _service as _runtime_start_authorization_service,
)
from test_workflow_protected_runtime_start_authorizations_postgres import (
    _runtime_context_use_result_parent_model,
)
from test_workflow_protected_runtime_start_consumptions import (
    NOW,
    SCOPE,
    _authorization_source,
    _InstructionSigner,
    _InstructionVerifier,
    _service,
)

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeContextInjectionDestinationHeadModel,
    WorkflowProtectedRuntimeContextInjectionSlotHeadModel,
    WorkflowProtectedRuntimeContextUseAttemptModel,
    WorkflowProtectedRuntimeContextUseClaimModel,
    WorkflowProtectedRuntimeContextUseResultModel,
    WorkflowProtectedRuntimeStartAuthorizationLeaseModel,
    WorkflowProtectedRuntimeStartConsumptionAttemptModel,
    WorkflowProtectedRuntimeStartConsumptionClaimModel,
    WorkflowProtectedRuntimeStartConsumptionResultModel,
    WorkflowProtectedRuntimeStartCoordinationHeadModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.protected_runtime_starters import (
    DenyAllWorkflowProtectedRuntimeStartReceiptSignatureVerifier,
)
from atlas.modules.workflows.application.protected_runtime_context_use_ports import (
    WorkflowProtectedRuntimeContextUseResultRequest,
    build_workflow_protected_runtime_context_use_instruction,
)
from atlas.modules.workflows.application.protected_runtime_start_authorization_ports import (
    WorkflowProtectedRuntimeStartAuthorizationSource,
    WorkflowProtectedRuntimeStartLifecycleAttestation,
)
from atlas.modules.workflows.application.protected_runtime_start_consumption_ports import (
    WorkflowProtectedRuntimeStartConsumptionClaimRequest,
    WorkflowProtectedRuntimeStartConsumptionResultRequest,
    WorkflowProtectedRuntimeStartConsumptionSource,
    build_workflow_protected_runtime_start_instruction,
    build_workflow_protected_runtime_start_signed_instruction_envelope,
)
from atlas.modules.workflows.domain.models import canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_domain import (
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WorkflowProtectedRuntimeContextUseReceipt,
    WorkflowProtectedRuntimeContextUseResultState,
)
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WorkflowProtectedRuntimeStartConsumptionResultState,
    WorkflowProtectedRuntimeStartReceipt,
    code_owned_workflow_protected_runtime_start_consumption_policy,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260817_0147_workflow_protected_runtime_start_consumption.py"
)
ADR_173_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260817_0146_workflow_protected_runtime_start_authorization.py"
)
APP_COMPOSITION = Path(__file__).resolve().parents[1] / "src" / "atlas" / "api" / "app.py"
DESTINATION_BOUNDARY_ID = "boundary.workflow-protected-target-context-capsule-consumer"
DESTINATION_DEPLOYMENT_ID = "deployment.workflow-protected-target-context-capsule-consumer"
DESTINATION_POLICY_DIGEST = "cf8b08ca5eef652623d69dd4521f8e25a7d537dc80a06de40fa7cc4cdc34fbcb"
RUNTIME_SLOT_PROFILE_DIGEST = "7c429ec36bd39f5d02add24b7622e55e32eb0cfca9345ebf272fd231385e3e6b"
USE_PROFILE_DIGEST = (
    code_owned_workflow_protected_runtime_context_use_authorization_policy().use_profile_digest
)
AUTHORIZATION_AUDIT_PAYLOAD: dict[str, object] = {"seed": "imp-224-actual-repository-claim-race"}


class _PinnedObservationPostgreSQLWorkflowPlanRepository(PostgreSQLWorkflowPlanRepository):
    def __init__(self, *, observed_at: datetime, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._pinned_observed_at = observed_at

    async def _lock_protected_runtime_start_consumption_rows(
        self,
        session: AsyncSession,
        *,
        request: WorkflowProtectedRuntimeStartConsumptionClaimRequest,
    ) -> Any:
        locked = await super()._lock_protected_runtime_start_consumption_rows(
            session,
            request=request,
        )
        authorization = replace(
            locked.authorization,
            first_observed_at=self._pinned_observed_at,
            observed_at=self._pinned_observed_at,
        )
        return replace(
            locked,
            authorization=authorization,
            observed_at=self._pinned_observed_at,
        )


def _checks(table: Table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def _model_values(model: object) -> dict[str, object]:
    table = cast(Any, type(model)).__table__
    return {column.name: getattr(model, column.name) for column in table.columns}


def _coordination_guard_body(source: str, *, replace: bool) -> str:
    operation = "CREATE OR REPLACE FUNCTION" if replace else "CREATE FUNCTION"
    match = re.search(
        rf"{operation} (?:guard_wf_rtstart_coord_mutation|"
        rf"\{{COORDINATION_GUARD_FUNCTION\}})\(\).*?\$\$(.*?)\$\$",
        source,
        re.DOTALL,
    )
    assert match is not None
    return " ".join(match.group(1).split())


def _authorization_source_at(base: datetime, *, suffix: str | None = None) -> Any:
    source = _authorization_source()
    claim = source.authorization_claim
    source_ids = (
        {}
        if suffix is None
        else {
            "use_result_id": f"runtime-use-result.{suffix}",
            "use_result_digest": canonical_digest(
                {"use_result_id": f"runtime-use-result.{suffix}"}
            ),
            "use_id": f"runtime-use.{suffix}",
            "use_attempt_id": f"runtime-use-attempt.{suffix}",
            "use_claim_id": f"runtime-use-claim.{suffix}",
            "authorization_consumption_result_id": f"use-auth-result.{suffix}",
            "runtime_envelope_id": f"runtime-envelope.{suffix}",
            "runtime_envelope_commitment": canonical_digest(
                {"runtime_envelope_id": f"runtime-envelope.{suffix}"}
            ),
            "runtime_slot_commitment": canonical_digest(
                {"runtime_slot_id": f"runtime-slot.{suffix}"}
            ),
        }
    )
    claim_ids = (
        {}
        if suffix is None
        else {
            "claim_id": f"runtime-start-authorization-claim.{suffix}",
        }
    )
    audit_digest = canonical_digest(AUTHORIZATION_AUDIT_PAYLOAD)
    claim_payload = claim.digest_payload()
    claim_payload.update(
        **cast(Any, source_ids),
        **cast(Any, claim_ids),
        destination_deployment_id=DESTINATION_DEPLOYMENT_ID,
        use_profile_digest=USE_PROFILE_DIGEST,
        authorization_audit_digest=audit_digest,
        use_completed_at=(base - timedelta(seconds=3)).isoformat(),
        use_result_recorded_at=(base - timedelta(seconds=2)).isoformat(),
        claimed_at=(base - timedelta(seconds=1)).isoformat(),
    )
    claim = replace(
        claim,
        **cast(Any, source_ids),
        **cast(Any, claim_ids),
        destination_deployment_id=DESTINATION_DEPLOYMENT_ID,
        use_profile_digest=USE_PROFILE_DIGEST,
        authorization_audit_digest=audit_digest,
        use_completed_at=base - timedelta(seconds=3),
        use_result_recorded_at=base - timedelta(seconds=2),
        claimed_at=base - timedelta(seconds=1),
        canonical_digest=canonical_digest(claim_payload),
    )
    lease = source.authorization_lease
    lease_ids = (
        {}
        if suffix is None
        else {
            "authorization_lease_id": f"runtime-start-authorization-lease.{suffix}",
            "lifecycle_attestation_id": f"runtime-start-attestation.{suffix}",
        }
    )
    issued_at = base - timedelta(milliseconds=500 if suffix is not None else 100)
    valid_until = issued_at + timedelta(seconds=1)
    attestation_valid_until = valid_until + timedelta(milliseconds=200)
    lease_payload = lease.digest_payload()
    lease_payload.update(
        **cast(Any, source_ids),
        **cast(Any, lease_ids),
        destination_deployment_id=DESTINATION_DEPLOYMENT_ID,
        use_profile_digest=USE_PROFILE_DIGEST,
        claim_id=claim.claim_id,
        claim_digest=claim.canonical_digest,
        use_completed_at=(base - timedelta(seconds=3)).isoformat(),
        use_result_recorded_at=(base - timedelta(seconds=2)).isoformat(),
        issued_at=issued_at.isoformat(),
        valid_until=valid_until.isoformat(),
        effective_until=valid_until.isoformat(),
        lifecycle_attestation_valid_until=attestation_valid_until.isoformat(),
        runtime_envelope_eligible_until=attestation_valid_until.isoformat(),
    )
    lease = replace(
        lease,
        **cast(Any, source_ids),
        **cast(Any, lease_ids),
        destination_deployment_id=DESTINATION_DEPLOYMENT_ID,
        use_profile_digest=USE_PROFILE_DIGEST,
        claim_id=claim.claim_id,
        claim_digest=claim.canonical_digest,
        use_completed_at=base - timedelta(seconds=3),
        use_result_recorded_at=base - timedelta(seconds=2),
        issued_at=issued_at,
        valid_until=valid_until,
        effective_until=valid_until,
        lifecycle_attestation_valid_until=attestation_valid_until,
        runtime_envelope_eligible_until=attestation_valid_until,
        canonical_digest=canonical_digest(lease_payload),
    )
    return type(source)(authorization_lease=lease, authorization_claim=claim)


async def _valid_runtime_start_authorization_evidence(
    repository: PostgreSQLWorkflowPlanRepository,
    *,
    base: datetime,
) -> tuple[
    WorkflowProtectedRuntimeStartConsumptionSource,
    tuple[
        WorkflowProtectedRuntimeContextUseClaimModel,
        WorkflowProtectedRuntimeContextUseAttemptModel,
        WorkflowProtectedRuntimeContextUseResultModel,
    ],
    WorkflowProtectedRuntimeStartLifecycleAttestation,
]:
    context_request = await _runtime_context_use_claim_request()
    use_claim = repository._protected_runtime_context_use_claim(
        context_request, claimed_at=CONTEXT_USE_NOW
    )
    use_attempt = repository._protected_runtime_context_use_attempt(
        context_request,
        claim=use_claim,
        started_at=CONTEXT_USE_NOW + timedelta(milliseconds=10),
        use_deadline=CONTEXT_USE_NOW + timedelta(milliseconds=500),
    )
    instruction = build_workflow_protected_runtime_context_use_instruction(use_attempt)
    receipt_values: dict[str, object] = {
        "instruction_digest": instruction.canonical_digest,
        "protected_operation_reference": instruction.protected_operation_reference,
        "authorization_consumption_result_id": instruction.authorization_consumption_result_id,
        "authorization_consumption_result_digest": (
            instruction.authorization_consumption_result_digest
        ),
        "destination_deployment_id": instruction.destination_deployment_id,
        "destination_generation": instruction.destination_generation,
        "destination_fencing_token_digest": instruction.destination_fencing_token_digest,
        "runtime_slot_commitment": instruction.runtime_slot_commitment,
        "runtime_slot_pre_generation": instruction.runtime_slot_pre_generation,
        "runtime_slot_post_generation": instruction.expected_runtime_slot_post_generation,
        "use_count_pre": 0,
        "use_count_post": 1,
        "use_profile_id": instruction.use_profile_id,
        "use_profile_version": instruction.use_profile_version,
        "use_profile_digest": instruction.use_profile_digest,
        "executor_contract_id": instruction.executor_contract_id,
        "executor_contract_version": instruction.executor_contract_version,
        "executor_id": instruction.executor_id,
        "executor_version": instruction.executor_version,
        "state": (
            WorkflowProtectedRuntimeContextUseResultState
        ).CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY,
        "failure_class": None,
        "context_adopted": True,
        "protected_runtime_context_use_performed": True,
        "context_terminal_non_reusable": True,
        "transient_material_zeroized": True,
        "context_disclosed": False,
        "runtime_started": False,
        "runtime_resumed": False,
        "process_created": False,
        "prompt_constructed": False,
        "model_inference_performed": False,
        "model_output_created": False,
        "filesystem_activity_performed": False,
        "provider_activity_performed": False,
        "connector_activity_performed": False,
        "network_activity_performed": False,
        "readiness_probe_performed": False,
        "publication_performed": False,
        "delivery_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
        "completed_at": instruction.started_at + timedelta(milliseconds=100),
        "use_deadline": instruction.use_deadline,
        "attested_by": instruction.executor_id,
        "signing_key_id": use_attempt.receipt_verification_signing_key_id,
        "signature_algorithm": "hmac-sha256",
        "integrity_signature": "b" * 64,
    }
    use_receipt = WorkflowProtectedRuntimeContextUseReceipt(
        **cast(Any, receipt_values),
        canonical_digest=canonical_digest(_runtime_context_use_canonical_mapping(receipt_values)),
    )
    context_service, _, _, _ = _runtime_context_use_service()
    use_result = context_service._build_receipted_result(
        claim_digest=use_claim.canonical_digest,
        attempt=use_attempt,
        receipt=use_receipt,
        recorded_at=use_receipt.completed_at + timedelta(milliseconds=50),
    )
    use_claim_row = repository._protected_runtime_context_adoption_claim_model(
        context_request, use_claim
    )
    use_attempt_row = repository._protected_runtime_context_use_attempt_model(
        context_request, use_claim, use_attempt
    )
    use_result_row = repository._protected_runtime_context_use_result_model(
        WorkflowProtectedRuntimeContextUseResultRequest(
            result=use_result,
            receipt=use_receipt,
            expected_claim_digest=use_claim.canonical_digest,
            expected_attempt_digest=use_attempt.canonical_digest,
        ),
        claim_row=use_claim_row,
        attempt_row=use_attempt_row,
    )
    source = WorkflowProtectedRuntimeStartAuthorizationSource(
        result=use_result,
        attempt=use_attempt,
        use_claim=use_claim,
        use_receipt=use_receipt,
    )
    events: list[str] = []
    attestor = _RuntimeStartAuthorizationAttestor(events)
    start_service = _runtime_start_authorization_service(
        _RuntimeStartAuthorizationRepository(source, events),
        attestor,
        _RuntimeStartAuthorizationReceiptVerifier(),
    )
    attestation_request = start_service._attestation_request(
        source,
        nonce_digest=canonical_digest({"runtime_start_nonce": uuid4().hex}),
        requested_at=base - timedelta(milliseconds=700),
    )
    template = await attestor.attest_runtime_start_lifecycle(attestation_request)
    attestation_values = {
        name: getattr(template, name) for name in template.__slots__ if name != "canonical_digest"
    }
    attestation_values.update(
        attestation_id=f"runtime-start-attestation.{uuid4().hex}",
        observed_at=base - timedelta(milliseconds=600),
        valid_until=base + timedelta(milliseconds=500),
        runtime_envelope_eligible_until=base + timedelta(milliseconds=700),
    )
    attestation = WorkflowProtectedRuntimeStartLifecycleAttestation(
        **cast(Any, attestation_values), canonical_digest="0" * 64
    )
    attestation = replace(
        attestation,
        canonical_digest=canonical_digest(attestation.digest_payload()),
    )
    idempotency_digest = canonical_digest(
        {"runtime_start_source": use_result.canonical_digest, "seed": uuid4().hex}
    )
    request_fingerprint = canonical_digest(
        {
            "runtime_start_source": use_result.canonical_digest,
            "idempotency_digest": idempotency_digest,
        }
    )
    authorization_claim, authorization_lease = start_service._build_candidates(
        source=source,
        attestation=attestation,
        issued_at=base - timedelta(milliseconds=500),
        idempotency_digest=idempotency_digest,
        request_fingerprint=request_fingerprint,
    )
    return (
        WorkflowProtectedRuntimeStartConsumptionSource(
            authorization_lease=authorization_lease,
            authorization_claim=authorization_claim,
        ),
        (use_claim_row, use_attempt_row, use_result_row),
        attestation,
    )


def _claim_request(
    *,
    base: datetime = NOW,
    suffix: str | None = None,
    source: WorkflowProtectedRuntimeStartConsumptionSource | None = None,
) -> WorkflowProtectedRuntimeStartConsumptionClaimRequest:
    service, _, _ = _service()
    source = source or _authorization_source_at(base, suffix=suffix)
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()
    idempotency_key = (
        "imp-224-runtime-start" if suffix is None else f"imp-224-runtime-start.{suffix}"
    )
    idempotency_digest = canonical_digest(
        {
            "scope": SCOPE.canonical_value(),
            "consumer_subject_id": policy.consumer_subject_id,
            "consumer_audience": policy.consumer_audience,
            "idempotency_key_sha256": sha256(idempotency_key.encode()).hexdigest(),
        }
    )
    request_fingerprint = canonical_digest(
        {
            "authorization_lease_id": source.authorization_lease.authorization_lease_id,
            "scope": SCOPE.canonical_value(),
            "consumer_subject_id": policy.consumer_subject_id,
            "consumer_audience": policy.consumer_audience,
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "policy_digest": policy.canonical_digest,
            "idempotency_digest": idempotency_digest,
            "irreversible_consumption_acknowledged": True,
            "uncertainty_no_retry_acknowledged": True,
        }
    )
    seed = canonical_digest(
        {
            "authorization_lease_id": source.authorization_lease.authorization_lease_id,
            "idempotency_digest": idempotency_digest,
            "request_fingerprint": request_fingerprint,
        }
    )
    candidate_started_at = source.authorization_lease.issued_at if suffix is not None else base
    claim = service._build_claim(
        source=source,
        claim_id=f"workflow-protected-runtime-start-consumption-claim.{seed[:24]}",
        attempt_id=f"workflow-protected-runtime-start-attempt.{seed[:24]}",
        consumption_id=f"workflow-protected-runtime-start-consumption.{seed[:24]}",
        scope=SCOPE,
        idempotency_digest=idempotency_digest,
        request_fingerprint=request_fingerprint,
        claimed_at=candidate_started_at,
    )
    attempt = service._build_attempt(
        source=source,
        claim=claim,
        started_at=candidate_started_at,
        seed=seed,
    )
    instruction = build_workflow_protected_runtime_start_instruction(attempt)
    envelope = build_workflow_protected_runtime_start_signed_instruction_envelope(
        instruction, _InstructionSigner()
    )
    return WorkflowProtectedRuntimeStartConsumptionClaimRequest(
        source=source,
        candidate_claim=claim,
        candidate_attempt=attempt,
        signed_instruction_envelope=envelope,
        offline_instruction_signature_verifier=_InstructionVerifier(),
        expected_policy_id=policy.policy_id,
        expected_policy_version=policy.policy_version,
        expected_policy_digest=policy.canonical_digest,
        minimum_invocation_margin_milliseconds=policy.minimum_invocation_margin_milliseconds,
        idempotency_key=idempotency_key,
        idempotency_digest=idempotency_digest,
        request_fingerprint=request_fingerprint,
    )


async def _terminal_result_request(
    request: WorkflowProtectedRuntimeStartConsumptionClaimRequest,
    *,
    recorded_at: datetime,
) -> WorkflowProtectedRuntimeStartConsumptionResultRequest:
    service, repository, _ = _service()
    presentation = await service._record_uncertainty(
        claim=request.candidate_claim,
        attempt=request.candidate_attempt,
    )
    assert presentation.result is not None
    assert presentation.result.state.value == "runtime_start_outcome_uncertain"
    assert repository.result == presentation.result
    payload = presentation.result.digest_payload()
    payload["recorded_at"] = recorded_at.isoformat()
    result = replace(
        presentation.result,
        recorded_at=recorded_at,
        canonical_digest=canonical_digest(payload),
    )
    return WorkflowProtectedRuntimeStartConsumptionResultRequest(
        result=result,
        receipt=None,
        expected_claim_digest=request.candidate_claim.canonical_digest,
        expected_attempt_digest=request.candidate_attempt.canonical_digest,
    )


async def _seed_actual_repository_path(
    connection: Any,
    repository: PostgreSQLWorkflowPlanRepository,
    request: WorkflowProtectedRuntimeStartConsumptionClaimRequest,
    *,
    seed_consumption: bool,
    runtime_context_models: tuple[
        WorkflowProtectedRuntimeContextUseClaimModel,
        WorkflowProtectedRuntimeContextUseAttemptModel,
        WorkflowProtectedRuntimeContextUseResultModel,
    ]
    | None = None,
    authorization_attestation: WorkflowProtectedRuntimeStartLifecycleAttestation | None = None,
) -> WorkflowProtectedRuntimeStartConsumptionResultRequest:
    lease = request.source.authorization_lease
    authorization_claim = request.source.authorization_claim
    result_request = await _terminal_result_request(
        request, recorded_at=request.candidate_attempt.started_at
    )
    if runtime_context_models is None:
        source_result = SimpleNamespace(
            result_id=lease.use_result_id,
            canonical_digest=lease.use_result_digest,
            use_id=lease.use_id,
            attempt_id=lease.use_attempt_id,
            attempt_digest=lease.use_attempt_digest,
            claim_id=lease.use_claim_id,
            claim_digest=lease.use_claim_digest,
            authorization_consumption_result_id=lease.authorization_consumption_result_id,
            authorization_consumption_result_digest=(lease.authorization_consumption_result_digest),
            destination_deployment_id=lease.destination_deployment_id,
            destination_generation=lease.destination_generation,
            destination_fencing_token_digest=lease.destination_fencing_token_digest,
            runtime_slot_commitment=lease.runtime_slot_commitment,
            runtime_slot_pre_generation=lease.runtime_slot_post_generation - 1,
            runtime_slot_post_generation=lease.runtime_slot_post_generation,
            use_count_pre=0,
            use_count_post=lease.use_count_post,
            use_profile_id=lease.use_profile_id,
            use_profile_version=lease.use_profile_version,
            use_profile_digest=lease.use_profile_digest,
            executor_receipt_digest=lease.use_receipt_digest,
            outcome_known=lease.use_outcome_known,
            context_adopted=lease.context_adopted,
            protected_runtime_context_use_performed=(lease.protected_runtime_context_use_performed),
            context_terminal_non_reusable=lease.context_terminal_non_reusable,
            transient_material_zeroized=lease.transient_material_zeroized,
            completed_at=lease.use_completed_at,
            recorded_at=lease.use_result_recorded_at,
            use_deadline=lease.use_completed_at + timedelta(milliseconds=500),
            state=lease.use_result_state,
        )
        parent_result = await _runtime_context_use_result_parent_model(
            repository, SimpleNamespace(result=source_result)
        )
        context_models: tuple[object, ...] = (parent_result,)
    else:
        context_models = runtime_context_models
    source_result_stub = SimpleNamespace(
        runtime_slot_pre_generation=lease.runtime_slot_post_generation - 1,
        use_count_pre=0,
    )
    attestation = authorization_attestation or SimpleNamespace(
        observed_at=lease.issued_at,
        canonical_digest=lease.lifecycle_attestation_digest,
        digest_payload=lambda: {
            "attestation_id": lease.lifecycle_attestation_id,
            "observed_at": lease.issued_at.isoformat(),
        },
    )
    lease_model = repository._protected_runtime_start_lease_model(
        lease,
        cast(Any, attestation),
        source_result=cast(Any, source_result_stub),
    )
    authorization_audit_payload: dict[str, object] = (
        AUTHORIZATION_AUDIT_PAYLOAD
        if runtime_context_models is None
        else {
            "policy_digest": authorization_claim.policy_digest,
            "request_fingerprint": authorization_claim.request_fingerprint,
            "scope": authorization_claim.scope.canonical_value(),
            "use_result_id": authorization_claim.use_result_id,
        }
    )
    authorization_claim_model = repository._protected_runtime_start_claim_model(
        authorization_claim,
        authorization_lease_id=lease.authorization_lease_id,
        idempotency_key=f"imp-223-seed.{lease.authorization_lease_id}",
        audit_payload=authorization_audit_payload,
        source_result=cast(Any, source_result_stub),
    )
    destination_payload = {
        "destination_boundary_id": DESTINATION_BOUNDARY_ID,
        "destination_deployment_id": lease.destination_deployment_id,
        "destination_generation": lease.destination_generation,
        "destination_fencing_token_digest": lease.destination_fencing_token_digest,
        "policy_digest": DESTINATION_POLICY_DIGEST,
    }
    destination_model = WorkflowProtectedRuntimeContextInjectionDestinationHeadModel(
        **destination_payload,
        current=True,
        canonical_digest=canonical_digest(destination_payload),
        payload=destination_payload,
    )
    slot_payload = {
        "destination_boundary_id": DESTINATION_BOUNDARY_ID,
        "destination_deployment_id": lease.destination_deployment_id,
        "destination_generation": lease.destination_generation,
        "destination_fencing_token_digest": lease.destination_fencing_token_digest,
        "runtime_slot_commitment": lease.runtime_slot_commitment,
        "runtime_slot_profile_digest": RUNTIME_SLOT_PROFILE_DIGEST,
        "slot_generation": lease.runtime_slot_post_generation,
        "slot_state": "context_used_terminal",
    }
    slot_model = WorkflowProtectedRuntimeContextInjectionSlotHeadModel(
        **slot_payload,
        current=True,
        canonical_digest=canonical_digest(slot_payload),
        payload=slot_payload,
    )
    claim_model = repository._protected_runtime_start_consumption_claim_model(request)
    attempt_model = repository._protected_runtime_start_consumption_attempt_model(request)
    head_model = WorkflowProtectedRuntimeStartCoordinationHeadModel(
        runtime_envelope_id=lease.runtime_envelope_id,
        organization_id=request.candidate_attempt.scope.organization_id,
        environment_id=request.candidate_attempt.scope.environment_id,
        site_id=request.candidate_attempt.scope.site_id,
        runtime_envelope_commitment=lease.runtime_envelope_commitment,
        runtime_envelope_generation=lease.runtime_envelope_generation,
        use_result_id=lease.use_result_id,
        use_result_digest=lease.use_result_digest,
        destination_deployment_id=lease.destination_deployment_id,
        destination_generation=lease.destination_generation,
        destination_fencing_token_digest=lease.destination_fencing_token_digest,
        runtime_slot_commitment=lease.runtime_slot_commitment,
        runtime_slot_post_generation=lease.runtime_slot_post_generation,
        state="start_attempt_pending" if seed_consumption else "authorized_unconsumed",
        active_authorization_lease_id=lease.authorization_lease_id,
        consumption_claim_id=(request.candidate_claim.claim_id if seed_consumption else None),
        runtime_start_attempt_id=(
            request.candidate_attempt.attempt_id if seed_consumption else None
        ),
        runtime_start_result_id=None,
        runtime_start_result_digest=None,
        runtime_start_attempt_pending=seed_consumption,
        runtime_start_attempt_terminal=False,
        runtime_started=False,
        runtime_resumed=False,
        process_created=False,
        process_scheduled=False,
        version=3 if seed_consumption else 2,
        updated_at=request.candidate_attempt.started_at,
    )
    await connection.execute(text("SET LOCAL session_replication_role = replica"))
    for shared_model in (destination_model, slot_model):
        table = cast(Any, type(shared_model).__table__)
        statement = postgres_insert(table).values(**_model_values(shared_model))
        await connection.execute(
            statement.on_conflict_do_update(
                index_elements=[column.name for column in table.primary_key.columns],
                set_={
                    column.name: getattr(statement.excluded, column.name)
                    for column in table.columns
                    if not column.primary_key
                },
            )
        )
    for model in (
        *context_models,
        head_model,
        lease_model,
        authorization_claim_model,
        *((claim_model, attempt_model) if seed_consumption else ()),
    ):
        await connection.execute(insert(cast(Any, type(model).__table__)), _model_values(model))
    await connection.execute(text("SET LOCAL session_replication_role = origin"))
    return result_request


def test_migration_is_linear_atomic_append_only_and_guarded() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    adr_173_source = ADR_173_MIGRATION.read_text(encoding="utf-8")
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()

    assert 'revision: str = "20260817_0147"' in source
    assert 'down_revision: str | None = "20260817_0146"' in source
    assert (
        "refusing guarded upgrade: legacy protected runtime-start attempts "
        "lack atomic consumption evidence"
    ) in source
    assert "state IN ('start_attempt_pending', 'start_attempt_terminal')" in source
    upgrade_source = source.split("def upgrade() -> None:", 1)[1]
    assert upgrade_source.index(
        "_guard_upgrade_without_legacy_runtime_start_attempts()"
    ) < upgrade_source.index(
        'op.add_column(COORDINATION_TABLE, sa.Column("runtime_start_result_id"'
    )
    assert source.count("op.create_table(") == 3
    assert "workflow_event_runtime_start_consumption_claims" in source
    assert "workflow_event_runtime_start_consumption_attempts" in source
    assert "workflow_event_runtime_start_consumption_results" in source
    assert "fk_wf_rtstart_cons_{prefix}_lease" in source
    assert "fk_wf_rtstart_cons_attempt_claim" in source
    assert "fk_wf_rtstart_cons_result_attempt" in source
    assert "fk_wf_rtstart_coord_attempt" in source
    assert "fk_wf_rtstart_coord_terminal_result" in source
    assert "OLD.state = 'authorized_unconsumed' AND NEW.state = 'start_attempt_pending'" in source
    assert "OLD.state = 'start_attempt_pending' AND NEW.state = 'start_attempt_terminal'" in source
    upgrade_guard = source.split("def _restore_adr173_coordination_guard", 1)[0]
    restored_guard = source.split("def _restore_adr173_coordination_guard", 1)[1].split(
        "def upgrade", 1
    )[0]
    assert (
        "OLD.state = 'authorized_unconsumed' AND NEW.state = 'start_attempt_terminal'"
        not in upgrade_guard
    )
    assert "NEW.state = 'start_attempt_pending'" in restored_guard
    assert "NEW.state = 'start_attempt_terminal'" in restored_guard
    assert "OLD.state = 'start_attempt_pending'" not in restored_guard
    assert _coordination_guard_body(restored_guard, replace=True) == (
        _coordination_guard_body(adr_173_source, replace=False)
    )
    assert "terminal_result_runtime_started" in upgrade_guard
    assert "runtime-start terminal outcome does not match result evidence" in upgrade_guard
    assert "BEFORE UPDATE OR DELETE" in source
    assert "trg_wf_rtstart_cons_claim_append_only" in source
    assert "trg_wf_rtstart_cons_attempt_append_only" in source
    assert "trg_wf_rtstart_cons_result_append_only" in source
    assert (
        "refusing guarded downgrade: protected runtime-start consumption evidence exists" in source
    )
    assert policy.canonical_digest in source
    assert policy.source_policy_digest in source
    assert policy.runtime_start_profile_digest in source
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_orm_binds_exact_lease_claim_attempt_result_and_coordination_lineage() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeStartAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeStartConsumptionClaimModel.__table__)
    attempt = cast(Table, WorkflowProtectedRuntimeStartConsumptionAttemptModel.__table__)
    result = cast(Table, WorkflowProtectedRuntimeStartConsumptionResultModel.__table__)
    coordination = cast(Table, WorkflowProtectedRuntimeStartCoordinationHeadModel.__table__)

    assert claim.name == "workflow_event_runtime_start_consumption_claims"
    assert attempt.name == "workflow_event_runtime_start_consumption_attempts"
    assert result.name == "workflow_event_runtime_start_consumption_results"
    assert {
        "authorization_lease_digest",
        "authorization_claim_digest",
        "use_result_digest",
        "destination_fencing_token_digest",
        "runtime_slot_generation",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
    } <= set(claim.c.keys())
    assert {
        "uq_wf_rtstart_auth_lease_identity",
        "uq_wf_rtstart_auth_lease_consume",
    } <= {constraint.name for constraint in lease.constraints}
    assert {
        "fk_wf_rtstart_cons_claim_lease",
        "fk_wf_rtstart_cons_claim_auth_claim",
        "fk_wf_rtstart_cons_claim_coord",
    } <= {constraint.name for constraint in claim.foreign_key_constraints}
    assert "fk_wf_rtstart_cons_attempt_claim" in {
        constraint.name for constraint in attempt.foreign_key_constraints
    }
    assert "fk_wf_rtstart_cons_result_attempt" in {
        constraint.name for constraint in result.foreign_key_constraints
    }
    assert {
        "fk_wf_rtstart_coord_result",
        "fk_wf_rtstart_coord_attempt",
        "fk_wf_rtstart_coord_terminal_result",
    } <= {constraint.name for constraint in coordination.foreign_key_constraints}
    terminal_result_fk = next(
        constraint
        for constraint in coordination.foreign_key_constraints
        if constraint.name == "fk_wf_rtstart_coord_terminal_result"
    )
    assert tuple(element.parent.name for element in terminal_result_fk.elements) == (
        "runtime_start_result_id",
        "runtime_start_result_digest",
        "consumption_claim_id",
        "runtime_start_attempt_id",
        "active_authorization_lease_id",
    )
    assert {"runtime_start_result_id", "runtime_start_result_digest"} <= set(coordination.c.keys())


def test_orm_enforces_zero_authority_started_attempt_and_terminal_outcomes() -> None:
    claim_checks = _checks(
        cast(Table, WorkflowProtectedRuntimeStartConsumptionClaimModel.__table__)
    )
    attempt_checks = _checks(
        cast(Table, WorkflowProtectedRuntimeStartConsumptionAttemptModel.__table__)
    )
    result_checks = _checks(
        cast(Table, WorkflowProtectedRuntimeStartConsumptionResultModel.__table__)
    )

    assert "irreversible_consumption_acknowledged" in claim_checks
    assert "uncertainty_no_retry_acknowledged" in claim_checks
    assert "runtime_start_attempt_started" in attempt_checks
    assert "expected_start_count_pre = 0" in attempt_checks
    assert "expected_start_count_post = 1" in attempt_checks
    assert "runtime_started_in_protected_boundary" in result_checks
    assert "runtime_start_failed_without_start" in result_checks
    assert "runtime_start_outcome_uncertain" in result_checks
    for forbidden in (
        "runtime_resume_authorized",
        "connector_activity_authorized",
        "network_access_authorized",
        "dispatch_authorized",
        "execution_authorized",
        "infrastructure_mutation_authorized",
        "protected_runtime_start_authority_granted",
    ):
        assert f"NOT {forbidden}" in claim_checks
        assert f"NOT {forbidden}" in attempt_checks
        assert f"NOT {forbidden}" in result_checks


def test_repository_locks_lineage_commits_before_return_and_never_calls_starter() -> None:
    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_protected_runtime_start_consumption_rows
    )
    claim_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.claim_protected_runtime_start_consumption
    )
    result_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.record_protected_runtime_start_consumption_result
    )
    result_lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_protected_runtime_start_consumption_result_rows
    )
    validity_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_runtime_start_consumption_request_is_valid
    )

    assert "_lock_protected_runtime_start_authorization_rows" in lock_source
    assert "with_for_update" in lock_source
    assert lock_source.index("claims = tuple") < lock_source.index("attempts = tuple")
    assert lock_source.index("attempts = tuple") < lock_source.index("results = tuple")
    assert claim_source.index("session.add") < claim_source.index("head.state")
    assert claim_source.index("head.state") < claim_source.index("await session.commit")
    invalid_branch = claim_source.split(
        "if not self._protected_runtime_start_consumption_request_is_valid", 1
    )[1]
    assert invalid_branch.index("invalid_status =") < invalid_branch.index(
        "await session.rollback()"
    )
    assert "start_attempt_pending" in claim_source
    assert "start_attempt_terminal" in result_source
    assert "lease.issued_at <= locked.authorization.first_observed_at" in validity_source
    assert result_lock_source.index(
        "_lock_protected_runtime_start_authorization_rows"
    ) < result_lock_source.index("WorkflowProtectedRuntimeStartConsumptionClaimModel")
    assert result_lock_source.index(
        "WorkflowProtectedRuntimeStartConsumptionClaimModel"
    ) < result_lock_source.index("WorkflowProtectedRuntimeStartConsumptionAttemptModel")
    assert result_lock_source.index(
        "WorkflowProtectedRuntimeStartConsumptionAttemptModel"
    ) < result_lock_source.index("WorkflowProtectedRuntimeStartConsumptionResultModel")
    assert "clock_timestamp" in lock_source
    for forbidden in ("starter.start", "connector", "mcp", "network", "process_manager"):
        assert forbidden not in claim_source.lower()
        assert forbidden not in result_source.lower()


def test_result_foreign_key_binds_all_repeated_attempt_lineage() -> None:
    attempt = cast(Table, WorkflowProtectedRuntimeStartConsumptionAttemptModel.__table__)
    result = cast(Table, WorkflowProtectedRuntimeStartConsumptionResultModel.__table__)
    constraint = next(
        item
        for item in result.foreign_key_constraints
        if item.name == "fk_wf_rtstart_cons_result_attempt"
    )
    expected = (
        "attempt_id",
        "attempt_digest",
        "claim_id",
        "claim_digest",
        "consumption_id",
        "authorization_lease_id",
        "authorization_lease_digest",
        "destination_deployment_id",
        "destination_generation",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
        "runtime_start_profile_id",
        "runtime_start_profile_version",
        "runtime_start_profile_digest",
        "protected_operation_reference",
        "instruction_digest",
        "started_at",
        "invocation_deadline",
    )

    assert tuple(element.parent.name for element in constraint.elements) == expected
    assert tuple(element.column.name for element in constraint.elements) == (
        "attempt_id",
        "canonical_digest",
        *expected[2:],
    )
    assert all(element.column.table is attempt for element in constraint.elements)
    assert "uq_wf_rtstart_cons_attempt_result_line" in {item.name for item in attempt.constraints}


def test_repository_models_round_trip_signed_attempt_evidence() -> None:
    request = _claim_request()
    repository = cast(Any, PostgreSQLWorkflowPlanRepository)

    claim_row = repository._protected_runtime_start_consumption_claim_model(request)
    attempt_row = repository._protected_runtime_start_consumption_attempt_model(request)

    assert repository._protected_runtime_start_consumption_claim_from_row(claim_row) == (
        request.candidate_claim
    )
    assert repository._protected_runtime_start_consumption_attempt_from_row(attempt_row) == (
        request.candidate_attempt
    )
    assert attempt_row.instruction_digest == (
        build_workflow_protected_runtime_start_instruction(
            request.candidate_attempt
        ).canonical_digest
    )
    assert attempt_row.signed_instruction_envelope_digest == (
        request.signed_instruction_envelope.canonical_digest
    )


@pytest.mark.asyncio
async def test_result_model_inherits_required_consumer_identity() -> None:
    request = _claim_request()
    repository = cast(Any, PostgreSQLWorkflowPlanRepository)
    attempt_row = repository._protected_runtime_start_consumption_attempt_model(request)
    result_request = await _terminal_result_request(
        request,
        recorded_at=request.candidate_attempt.started_at,
    )

    result_row = repository._protected_runtime_start_consumption_result_model(
        result_request,
        attempt_row=attempt_row,
    )

    assert result_row.consumer_subject_id == request.candidate_attempt.consumer_subject_id
    assert result_row.consumer_audience == request.candidate_attempt.consumer_audience
    assert result_row.consumer_contract_id == request.candidate_attempt.consumer_contract_id
    assert (
        result_row.consumer_contract_version == request.candidate_attempt.consumer_contract_version
    )
    assert result_row.purpose_id == request.candidate_attempt.purpose_id
    assert result_row.starter_receipt_payload.compare(null())


def test_suffixed_live_source_keeps_code_owned_destination() -> None:
    request = _claim_request(base=NOW, suffix="live-a")

    assert request.source.authorization_lease.destination_deployment_id == DESTINATION_DEPLOYMENT_ID
    assert request.source.authorization_claim.destination_deployment_id == DESTINATION_DEPLOYMENT_ID
    assert request.source.authorization_lease.use_profile_digest == USE_PROFILE_DIGEST
    assert request.source.authorization_claim.use_profile_digest == USE_PROFILE_DIGEST
    assert request.candidate_claim.claimed_at == request.source.authorization_lease.issued_at
    assert request.candidate_attempt.started_at == request.source.authorization_lease.issued_at


def test_persisted_starter_receipt_requires_available_exact_signature_verifier() -> None:
    request = _claim_request()
    instruction = build_workflow_protected_runtime_start_instruction(request.candidate_attempt)
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()
    receipt_values: dict[str, object] = {
        "consumption_id": instruction.consumption_id,
        "attempt_id": instruction.attempt_id,
        "instruction_digest": instruction.canonical_digest,
        "protected_operation_reference": instruction.protected_operation_reference,
        "authorization_lease_id": instruction.authorization_lease_id,
        "destination_deployment_id": instruction.destination_deployment_id,
        "destination_generation": instruction.destination_generation,
        "destination_fencing_token_digest": instruction.destination_fencing_token_digest,
        "runtime_slot_commitment": instruction.runtime_slot_commitment,
        "runtime_slot_generation": instruction.runtime_slot_generation,
        "runtime_envelope_id": instruction.runtime_envelope_id,
        "runtime_envelope_commitment": instruction.runtime_envelope_commitment,
        "runtime_envelope_generation": instruction.runtime_envelope_generation,
        "request_nonce_digest": instruction.request_nonce_digest,
        "result_state": (
            WorkflowProtectedRuntimeStartConsumptionResultState
        ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY,
        "runtime_started": True,
        "runtime_start_count_pre": 0,
        "runtime_start_count_post": 1,
        "runtime_envelope_current": True,
        "runtime_envelope_inactive": False,
        "residual_process_absent": False,
        "residual_task_absent": False,
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
        "completed_at": NOW + timedelta(milliseconds=400),
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

    class ExactReceiptVerifier:
        @property
        def available(self) -> bool:
            return True

        def verify_receipt(self, candidate: WorkflowProtectedRuntimeStartReceipt) -> bool:
            return candidate.integrity_signature == "e" * 64

    service, _, _ = _service()
    result = service._build_receipted_result(
        claim=request.candidate_claim,
        attempt=request.candidate_attempt,
        receipt=receipt,
        recorded_at=receipt.completed_at,
    )
    result_request = WorkflowProtectedRuntimeStartConsumptionResultRequest(
        result=result,
        receipt=receipt,
        expected_claim_digest=request.candidate_claim.canonical_digest,
        expected_attempt_digest=request.candidate_attempt.canonical_digest,
    )
    repository = PostgreSQLWorkflowPlanRepository(engine=cast(Any, object()))
    attempt_row = repository._protected_runtime_start_consumption_attempt_model(request)
    valid_row = repository._protected_runtime_start_consumption_result_model(
        result_request, attempt_row=attempt_row
    )
    verifier = ExactReceiptVerifier()
    repository.bind_protected_runtime_start_receipt_signature_verifier(verifier)
    repository.bind_protected_runtime_start_receipt_signature_verifier(verifier)
    assert repository._protected_runtime_start_consumption_result_from_row(valid_row) == result

    forged_payload = receipt.digest_payload()
    forged_payload["integrity_signature"] = "0" * 64
    forged_receipt = replace(
        receipt,
        integrity_signature="0" * 64,
        canonical_digest=canonical_digest(forged_payload),
    )
    forged_result_payload = result.digest_payload()
    forged_result_payload["starter_receipt_digest"] = forged_receipt.canonical_digest
    forged_result = replace(
        result,
        starter_receipt_digest=forged_receipt.canonical_digest,
        canonical_digest=canonical_digest(forged_result_payload),
    )
    forged_row = repository._protected_runtime_start_consumption_result_model(
        WorkflowProtectedRuntimeStartConsumptionResultRequest(
            result=forged_result,
            receipt=forged_receipt,
            expected_claim_digest=request.candidate_claim.canonical_digest,
            expected_attempt_digest=request.candidate_attempt.canonical_digest,
        ),
        attempt_row=attempt_row,
    )
    with pytest.raises(ValueError, match="repository contract violated"):
        repository._protected_runtime_start_consumption_result_from_row(forged_row)

    unavailable_repository = PostgreSQLWorkflowPlanRepository(engine=cast(Any, object()))
    unavailable_repository.bind_protected_runtime_start_receipt_signature_verifier(
        DenyAllWorkflowProtectedRuntimeStartReceiptSignatureVerifier()
    )
    with pytest.raises(ValueError, match="repository contract violated"):
        unavailable_repository._protected_runtime_start_consumption_result_from_row(valid_row)
    with pytest.raises(ValueError, match="already bound"):
        repository.bind_protected_runtime_start_receipt_signature_verifier(
            DenyAllWorkflowProtectedRuntimeStartReceiptSignatureVerifier()
        )
    app_source = APP_COMPOSITION.read_text(encoding="utf-8")
    bind_call = "bind_runtime_start_receipt_verifier(runtime_start_receipt_verifier)"
    service_call = "WorkflowProtectedRuntimeStartConsumptionService("
    composition = app_source.split("if workflow_protected_runtime_start_consumption_service", 1)[1]
    assert bind_call in composition
    assert composition.index(bind_call) < composition.index(service_call)


@pytest.mark.asyncio
async def test_live_postgres_real_repository_claim_race_when_configured() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    request: WorkflowProtectedRuntimeStartConsumptionClaimRequest | None = None
    setup_committed = False
    try:
        async with engine.connect() as setup_connection:
            setup_transaction = await setup_connection.begin()
            database_now = cast(
                datetime,
                await setup_connection.scalar(select(func.clock_timestamp())),
            )
            suffix = f"imp224-{uuid4().hex[:16]}"
            request = _claim_request(base=database_now, suffix=suffix)
            await _seed_actual_repository_path(
                setup_connection,
                PostgreSQLWorkflowPlanRepository(engine=engine),
                request,
                seed_consumption=False,
            )
            assert await setup_connection.scalar(text("SHOW session_replication_role")) == "origin"
            await setup_transaction.commit()
            setup_committed = True

        async with engine.connect() as first_connection, engine.connect() as second_connection:
            assert await first_connection.scalar(text("SHOW session_replication_role")) == "origin"
            assert await second_connection.scalar(text("SHOW session_replication_role")) == "origin"
            await first_connection.rollback()
            await second_connection.rollback()
            pinned_observed_at = request.source.authorization_lease.issued_at + timedelta(
                milliseconds=100
            )

            def first_session() -> AsyncSession:
                return AsyncSession(bind=first_connection, expire_on_commit=False)

            def second_session() -> AsyncSession:
                return AsyncSession(bind=second_connection, expire_on_commit=False)

            first_repository = _PinnedObservationPostgreSQLWorkflowPlanRepository(
                engine=engine,
                session_factory=first_session,
                observed_at=pinned_observed_at,
            )
            second_repository = _PinnedObservationPostgreSQLWorkflowPlanRepository(
                engine=engine,
                session_factory=second_session,
                observed_at=pinned_observed_at,
            )
            first_write, second_write = await asyncio.gather(
                first_repository.claim_protected_runtime_start_consumption(request),
                second_repository.claim_protected_runtime_start_consumption(request),
            )

        assert sorted((first_write.status.value, second_write.status.value)) == [
            "claimed",
            "replay_pending",
        ]
        winner = first_write if first_write.status.value == "claimed" else second_write
        assert winner.claim == request.candidate_claim
        assert winner.attempt == request.candidate_attempt
        async with engine.connect() as verification_connection:
            claim_count = await verification_connection.scalar(
                text(
                    "SELECT count(*) FROM workflow_event_runtime_start_consumption_claims "
                    "WHERE authorization_lease_id = :authorization_lease_id"
                ),
                {
                    "authorization_lease_id": (
                        request.source.authorization_lease.authorization_lease_id
                    )
                },
            )
            attempt_count = await verification_connection.scalar(
                text(
                    "SELECT count(*) FROM workflow_event_runtime_start_consumption_attempts "
                    "WHERE authorization_lease_id = :authorization_lease_id"
                ),
                {
                    "authorization_lease_id": (
                        request.source.authorization_lease.authorization_lease_id
                    )
                },
            )
            head = (
                (
                    await verification_connection.execute(
                        text(
                            "SELECT state, consumption_claim_id, runtime_start_attempt_id, "
                            "runtime_start_attempt_pending, runtime_start_attempt_terminal "
                            "FROM workflow_event_runtime_start_coordination_heads "
                            "WHERE runtime_envelope_id = :runtime_envelope_id"
                        ),
                        {"runtime_envelope_id": request.candidate_attempt.runtime_envelope_id},
                    )
                )
                .mappings()
                .one()
            )
        assert claim_count == 1
        assert attempt_count == 1
        assert dict(head) == {
            "state": "start_attempt_pending",
            "consumption_claim_id": request.candidate_claim.claim_id,
            "runtime_start_attempt_id": request.candidate_attempt.attempt_id,
            "runtime_start_attempt_pending": True,
            "runtime_start_attempt_terminal": False,
        }
    finally:
        if request is not None and setup_committed:
            lease = request.source.authorization_lease
            async with engine.begin() as cleanup_connection:
                await cleanup_connection.execute(
                    text("SET LOCAL session_replication_role = replica")
                )
                for statement, parameters in (
                    (
                        "DELETE FROM workflow_event_runtime_start_consumption_results "
                        "WHERE authorization_lease_id = :lease_id",
                        {"lease_id": lease.authorization_lease_id},
                    ),
                    (
                        "DELETE FROM workflow_event_runtime_start_consumption_attempts "
                        "WHERE authorization_lease_id = :lease_id",
                        {"lease_id": lease.authorization_lease_id},
                    ),
                    (
                        "DELETE FROM workflow_event_runtime_start_consumption_claims "
                        "WHERE authorization_lease_id = :lease_id",
                        {"lease_id": lease.authorization_lease_id},
                    ),
                    (
                        "DELETE FROM workflow_event_runtime_start_auth_claims "
                        "WHERE authorization_lease_id = :lease_id",
                        {"lease_id": lease.authorization_lease_id},
                    ),
                    (
                        "DELETE FROM workflow_event_runtime_start_auth_leases "
                        "WHERE authorization_lease_id = :lease_id",
                        {"lease_id": lease.authorization_lease_id},
                    ),
                    (
                        "DELETE FROM workflow_event_runtime_start_coordination_heads "
                        "WHERE runtime_envelope_id = :runtime_envelope_id",
                        {"runtime_envelope_id": lease.runtime_envelope_id},
                    ),
                    (
                        "DELETE FROM workflow_protected_runtime_context_use_results "
                        "WHERE result_id = :result_id",
                        {"result_id": lease.use_result_id},
                    ),
                    (
                        "DELETE FROM workflow_protected_runtime_context_injection_slot_heads "
                        "WHERE destination_deployment_id = :deployment_id "
                        "AND runtime_slot_commitment = :slot_commitment",
                        {
                            "deployment_id": lease.destination_deployment_id,
                            "slot_commitment": lease.runtime_slot_commitment,
                        },
                    ),
                    (
                        "DELETE FROM "
                        "workflow_protected_runtime_context_injection_destination_heads "
                        "WHERE destination_deployment_id = :deployment_id",
                        {"deployment_id": lease.destination_deployment_id},
                    ),
                ):
                    await cleanup_connection.execute(text(statement), parameters)
                await cleanup_connection.execute(
                    text("SET LOCAL session_replication_role = origin")
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_schema_guards_append_only_and_one_claim_winner_when_configured() -> (
    None
):
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    claim_clone = f"imp224_claim_race_{uuid4().hex}"
    head_clone = f"imp224_head_guard_{uuid4().hex}"
    try:
        async with engine.connect() as connection:
            tables = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
                            "AND tablename IN (:claim, :attempt, :result)"
                        ),
                        {
                            "claim": "workflow_event_runtime_start_consumption_claims",
                            "attempt": "workflow_event_runtime_start_consumption_attempts",
                            "result": "workflow_event_runtime_start_consumption_results",
                        },
                    )
                ).scalars()
            )
            assert tables == {
                "workflow_event_runtime_start_consumption_claims",
                "workflow_event_runtime_start_consumption_attempts",
                "workflow_event_runtime_start_consumption_results",
            }
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger WHERE tgname IN "
                            "('trg_wf_rtstart_cons_claim_append_only', "
                            "'trg_wf_rtstart_cons_attempt_append_only', "
                            "'trg_wf_rtstart_cons_result_append_only')"
                        )
                    )
                ).scalars()
            )
            assert len(triggers) == 3

        async with engine.connect() as actual_connection:
            actual_transaction = await actual_connection.begin()
            try:
                database_now = cast(
                    datetime,
                    await actual_connection.scalar(select(func.clock_timestamp())),
                )
                request = _claim_request(
                    base=database_now,
                    suffix=f"imp224-schema-{uuid4().hex[:16]}",
                )
                seed_repository = PostgreSQLWorkflowPlanRepository(engine=engine)
                result_request = await _seed_actual_repository_path(
                    actual_connection,
                    seed_repository,
                    request,
                    seed_consumption=True,
                )
                attempt_model = seed_repository._protected_runtime_start_consumption_attempt_model(
                    request
                )
                mismatched_result_model = (
                    seed_repository._protected_runtime_start_consumption_result_model(
                        result_request, attempt_row=attempt_model
                    )
                )
                mismatch_transaction = await actual_connection.begin_nested()
                await actual_connection.execute(
                    insert(
                        cast(
                            Any,
                            WorkflowProtectedRuntimeStartConsumptionResultModel.__table__,
                        )
                    ),
                    _model_values(mismatched_result_model),
                )
                with pytest.raises(
                    DBAPIError,
                    match="runtime-start terminal outcome does not match result evidence",
                ):
                    await actual_connection.execute(
                        text(
                            "UPDATE workflow_event_runtime_start_coordination_heads "
                            "SET state = 'start_attempt_terminal', "
                            "runtime_start_result_id = :result_id, "
                            "runtime_start_result_digest = :result_digest, "
                            "runtime_start_attempt_pending = FALSE, "
                            "runtime_start_attempt_terminal = TRUE, "
                            "runtime_started = TRUE, version = version + 1 "
                            "WHERE runtime_envelope_id = :runtime_envelope_id"
                        ),
                        {
                            "result_id": result_request.result.result_id,
                            "result_digest": result_request.result.canonical_digest,
                            "runtime_envelope_id": (request.candidate_attempt.runtime_envelope_id),
                        },
                    )
                await mismatch_transaction.rollback()

                def actual_session() -> AsyncSession:
                    return AsyncSession(
                        bind=actual_connection,
                        expire_on_commit=False,
                        join_transaction_mode="create_savepoint",
                    )

                actual_repository = PostgreSQLWorkflowPlanRepository(
                    engine=engine,
                    session_factory=actual_session,
                )
                write = await actual_repository.record_protected_runtime_start_consumption_result(
                    result_request
                )
                assert write.status.value == "recorded"
                assert write.result == result_request.result
                head = (
                    (
                        await actual_connection.execute(
                            text(
                                "SELECT state, runtime_start_result_id, "
                                "runtime_start_result_digest, runtime_start_attempt_pending, "
                                "runtime_start_attempt_terminal, runtime_started "
                                "FROM workflow_event_runtime_start_coordination_heads "
                                "WHERE runtime_envelope_id = :runtime_envelope_id"
                            ),
                            {
                                "runtime_envelope_id": (
                                    request.candidate_attempt.runtime_envelope_id
                                )
                            },
                        )
                    )
                    .mappings()
                    .one()
                )
                assert head == {
                    "state": "start_attempt_terminal",
                    "runtime_start_result_id": result_request.result.result_id,
                    "runtime_start_result_digest": result_request.result.canonical_digest,
                    "runtime_start_attempt_pending": False,
                    "runtime_start_attempt_terminal": True,
                    "runtime_started": False,
                }
                replay = await actual_repository.record_protected_runtime_start_consumption_result(
                    result_request
                )
                assert replay.status.value == "replay"
                assert replay.result == result_request.result
            finally:
                await actual_transaction.rollback()

        request = _claim_request()
        claim_model = (
            PostgreSQLWorkflowPlanRepository._protected_runtime_start_consumption_claim_model(
                request
            )
        )
        values = {
            column.name: getattr(claim_model, column.name)
            for column in WorkflowProtectedRuntimeStartConsumptionClaimModel.__table__.columns
        }
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    f"CREATE UNLOGGED TABLE {claim_clone} "
                    "(LIKE workflow_event_runtime_start_consumption_claims INCLUDING ALL)"
                )
            )
            await connection.execute(
                text(
                    f"CREATE TRIGGER imp224_claim_append BEFORE UPDATE OR DELETE ON {claim_clone} "
                    "FOR EACH ROW EXECUTE FUNCTION reject_wf_rtstart_cons_mutation()"
                )
            )
            await connection.execute(
                text(
                    f"CREATE UNLOGGED TABLE {head_clone} "
                    "(LIKE workflow_event_runtime_start_coordination_heads INCLUDING ALL)"
                )
            )
            await connection.execute(
                text(
                    f"CREATE TRIGGER imp224_head_guard BEFORE UPDATE OR DELETE ON {head_clone} "
                    "FOR EACH ROW EXECUTE FUNCTION guard_wf_rtstart_coord_mutation()"
                )
            )

        async with engine.connect() as reflection:
            claim_table = await reflection.run_sync(
                lambda sync: Table(claim_clone, MetaData(), autoload_with=sync)
            )

        first_values = dict(values)
        second_values = dict(values)
        suffix = uuid4().hex
        second_values.update(
            claim_id=f"claim.competing.{suffix}",
            consumption_id=f"consumption.competing.{suffix}",
            attempt_id=f"attempt.competing.{suffix}",
            idempotency_digest="e" * 64,
            idempotency_key=f"competing-{suffix}",
            canonical_digest="f" * 64,
        )
        async with engine.connect() as first, engine.connect() as second:
            first_tx = await first.begin()
            second_tx = await second.begin()
            await first.execute(insert(claim_table), first_values)
            competing = asyncio.create_task(second.execute(insert(claim_table), second_values))
            await asyncio.sleep(0.1)
            assert competing.done() is False
            await first_tx.commit()
            with pytest.raises(IntegrityError):
                await competing
            await second_tx.rollback()

        async with engine.connect() as connection:
            append_tx = await connection.begin()
            with pytest.raises(DBAPIError, match="append-only"):
                await connection.execute(
                    text(f"UPDATE {claim_clone} SET canonical_digest = :digest"),
                    {"digest": "0" * 64},
                )
            await append_tx.rollback()

            head_values = {
                "runtime_envelope_id": f"runtime-envelope.{uuid4().hex}",
                "organization_id": SCOPE.organization_id,
                "environment_id": SCOPE.environment_id,
                "site_id": SCOPE.site_id,
                "runtime_envelope_commitment": "1" * 64,
                "runtime_envelope_generation": 2,
                "use_result_id": f"use-result.{uuid4().hex}",
                "use_result_digest": "2" * 64,
                "destination_deployment_id": "deployment.imp-224",
                "destination_generation": 1,
                "destination_fencing_token_digest": "3" * 64,
                "runtime_slot_commitment": "4" * 64,
                "runtime_slot_post_generation": 2,
                "state": "authorized_unconsumed",
                "active_authorization_lease_id": "lease.imp-224",
                "consumption_claim_id": None,
                "runtime_start_attempt_id": None,
                "runtime_start_result_id": None,
                "runtime_start_result_digest": None,
                "runtime_start_attempt_pending": False,
                "runtime_start_attempt_terminal": False,
                "runtime_started": False,
                "runtime_resumed": False,
                "process_created": False,
                "process_scheduled": False,
                "version": 2,
                "updated_at": NOW,
            }
            await connection.execute(
                text(
                    f"INSERT INTO {head_clone} ("
                    + ", ".join(head_values)
                    + ") VALUES ("
                    + ", ".join(f":{name}" for name in head_values)
                    + ")"
                ),
                head_values,
            )
            illegal_tx = await connection.begin_nested()
            with pytest.raises(DBAPIError, match="illegal runtime-start coordination transition"):
                await connection.execute(
                    text(
                        f"UPDATE {head_clone} SET state = 'start_attempt_terminal', "
                        "consumption_claim_id = 'claim.illegal', "
                        "runtime_start_attempt_id = 'attempt.illegal', "
                        "runtime_start_result_id = 'result.illegal', "
                        "runtime_start_result_digest = :digest, "
                        "runtime_start_attempt_terminal = TRUE, version = 3 "
                        "WHERE runtime_envelope_id = :envelope_id"
                    ),
                    {
                        "digest": "5" * 64,
                        "envelope_id": head_values["runtime_envelope_id"],
                    },
                )
            await illegal_tx.rollback()
            await connection.rollback()
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f"DROP TABLE IF EXISTS {head_clone}"))
            await connection.execute(text(f"DROP TABLE IF EXISTS {claim_clone}"))
        await engine.dispose()
