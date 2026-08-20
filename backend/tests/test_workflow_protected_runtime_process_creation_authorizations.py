from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest

from atlas.modules.workflows.application.protected_runtime_process_creation_authorization_ports import (  # noqa: E501
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTATION_SIGNING_KEY_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_VERSION,
    WorkflowProtectedRuntimeProcessCreationAuthorizationError,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseResult,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightResult,
    WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeProcessCreationAuthorizationPresentation,
    WorkflowProtectedRuntimeProcessCreationAuthorizationPresentationState,
    WorkflowProtectedRuntimeProcessCreationAuthorizationSource,
    WorkflowProtectedRuntimeProcessCreationAuthorizationSourceRequest,
    WorkflowProtectedRuntimeProcessCreationLifecycleAttestation,
    WorkflowProtectedRuntimeProcessCreationLifecycleAttestationRequest,
    validate_workflow_protected_runtime_process_creation_authorization_request,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_authorizations import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationService,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_creation_authorization_domain import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationLease,
    code_owned_workflow_protected_runtime_process_creation_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_readiness_authorization_domain import (
    WorkflowProtectedRuntimeReadinessAuthorizationAuthority,
)
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WorkflowProtectedRuntimeReadinessConsumptionAuthority,
    WorkflowProtectedRuntimeReadinessConsumptionFailureClass,
    WorkflowProtectedRuntimeReadinessConsumptionResultState,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)

NOW = datetime(2026, 8, 18, 8, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.imp-227", "environment.imp-227", "site.imp-227")


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    return value


class _Evidence(SimpleNamespace):
    def digest_payload(self) -> dict[str, object]:
        return {
            name: _canonical_value(value)
            for name, value in vars(self).items()
            if name != "canonical_digest"
        }


def _evidence(**values: object) -> _Evidence:
    item = _Evidence(**values, canonical_digest="0" * 64)
    item.canonical_digest = canonical_digest(item.digest_payload())
    return item


def _instruction_digest(attempt: _Evidence) -> str:
    names = (
        "consumption_id",
        "attempt_id",
        "claim_id",
        "claim_digest",
        "authorization_lease_id",
        "authorization_lease_digest",
        "start_result_id",
        "start_result_digest",
        "protected_operation_reference",
        "destination_deployment_id",
        "destination_generation",
        "destination_fencing_token_digest",
        "protected_slot_commitment",
        "protected_slot_generation",
        "runtime_envelope_id",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
        "readiness_profile_id",
        "readiness_profile_version",
        "readiness_profile_digest",
        "expected_assessment_count_pre",
        "expected_assessment_count_post",
        "assessor_contract_id",
        "assessor_contract_version",
        "assessor_id",
        "assessor_version",
        "request_nonce_digest",
        "scope",
        "policy_id",
        "policy_version",
        "policy_digest",
        "started_at",
        "invocation_deadline",
    )
    values = {name: getattr(attempt, name) for name in names}
    values["attempt_digest"] = attempt.canonical_digest
    ordered = {
        "consumption_id": values["consumption_id"],
        "attempt_id": values["attempt_id"],
        "attempt_digest": values["attempt_digest"],
        **{name: values[name] for name in names[2:]},
    }
    return canonical_digest({name: _canonical_value(value) for name, value in ordered.items()})


def _source(
    *,
    state: WorkflowProtectedRuntimeReadinessConsumptionResultState = (
        WorkflowProtectedRuntimeReadinessConsumptionResultState
    ).RUNTIME_READY_IN_PROTECTED_BOUNDARY,
) -> WorkflowProtectedRuntimeProcessCreationAuthorizationSource:
    source_policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    zero = WorkflowProtectedRuntimeReadinessConsumptionAuthority()
    authorization_claim = _evidence(claim_id="readiness-authorization-claim.imp-227")
    authorization_lease = _evidence(
        authorization_lease_id="readiness-authorization-lease.imp-227",
        claim_id=authorization_claim.claim_id,
        claim_digest=authorization_claim.canonical_digest,
        authority=WorkflowProtectedRuntimeReadinessAuthorizationAuthority(
            protected_runtime_readiness_authority_granted=True
        ),
    )
    readiness_claim = _evidence(
        claim_id="readiness-claim.imp-227",
        consumption_id="readiness-consumption.imp-227",
        attempt_id="readiness-attempt.imp-227",
        authorization_lease_id=authorization_lease.authorization_lease_id,
        authorization_lease_digest=authorization_lease.canonical_digest,
        authority=zero,
    )
    attempt = _evidence(
        attempt_id=readiness_claim.attempt_id,
        consumption_id=readiness_claim.consumption_id,
        claim_id=readiness_claim.claim_id,
        claim_digest=readiness_claim.canonical_digest,
        authorization_lease_id=authorization_lease.authorization_lease_id,
        authorization_lease_digest=authorization_lease.canonical_digest,
        start_result_id="start-result.imp-224",
        start_result_digest="1" * 64,
        protected_operation_reference="protected-operation.imp-227",
        destination_deployment_id="deployment.imp-227",
        destination_generation=7,
        destination_fencing_token_digest="2" * 64,
        protected_slot_commitment="3" * 64,
        protected_slot_generation=11,
        runtime_envelope_id="runtime-envelope.imp-227",
        runtime_envelope_commitment="4" * 64,
        runtime_envelope_generation=11,
        readiness_profile_id=source_policy.readiness_profile_id,
        readiness_profile_version=source_policy.readiness_profile_version,
        readiness_profile_digest=source_policy.readiness_profile_digest,
        expected_assessment_count_pre=0,
        expected_assessment_count_post=1,
        assessor_contract_id=source_policy.required_assessor_contract_id,
        assessor_contract_version=source_policy.required_assessor_contract_version,
        assessor_id=source_policy.approved_assessor_id,
        assessor_version=source_policy.approved_assessor_version,
        receipt_verification_signing_key_id=source_policy.receipt_verification_signing_key_id,
        request_nonce_digest="5" * 64,
        scope=SCOPE,
        consumer_subject_id=source_policy.consumer_subject_id,
        consumer_audience=source_policy.consumer_audience,
        consumer_contract_id=source_policy.consumer_contract_id,
        consumer_contract_version=source_policy.consumer_contract_version,
        purpose_id=source_policy.purpose_id,
        policy_id=source_policy.policy_id,
        policy_version=source_policy.policy_version,
        policy_digest=source_policy.canonical_digest,
        started_at=NOW - timedelta(seconds=2),
        invocation_deadline=NOW - timedelta(seconds=1),
        authority=zero,
    )
    success = (
        state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READY_IN_PROTECTED_BOUNDARY
    )
    receipt = _evidence(
        consumption_id=attempt.consumption_id,
        attempt_id=attempt.attempt_id,
        attempt_digest=attempt.canonical_digest,
        claim_id=attempt.claim_id,
        claim_digest=attempt.claim_digest,
        instruction_digest=_instruction_digest(attempt),
        authorization_lease_id=attempt.authorization_lease_id,
        authorization_lease_digest=attempt.authorization_lease_digest,
        start_result_id=attempt.start_result_id,
        start_result_digest=attempt.start_result_digest,
        protected_operation_reference=attempt.protected_operation_reference,
        destination_deployment_id=attempt.destination_deployment_id,
        destination_generation=attempt.destination_generation,
        destination_fencing_token_digest=attempt.destination_fencing_token_digest,
        protected_slot_commitment=attempt.protected_slot_commitment,
        protected_slot_generation=attempt.protected_slot_generation,
        runtime_envelope_id=attempt.runtime_envelope_id,
        runtime_envelope_commitment=attempt.runtime_envelope_commitment,
        runtime_envelope_generation=attempt.runtime_envelope_generation,
        readiness_profile_id=attempt.readiness_profile_id,
        readiness_profile_version=attempt.readiness_profile_version,
        readiness_profile_digest=attempt.readiness_profile_digest,
        assessor_contract_id=attempt.assessor_contract_id,
        assessor_contract_version=attempt.assessor_contract_version,
        assessor_id=attempt.assessor_id,
        assessor_version=attempt.assessor_version,
        request_nonce_digest=attempt.request_nonce_digest,
        assessment_count_pre=0,
        assessment_count_post=1 if success else 0,
        result_state=state,
        runtime_ready=success,
        readiness_assessment_performed=True,
        runtime_locator_returned=False,
        process_identifier_returned=False,
        runtime_context_returned=False,
        endpoint_material_returned=False,
        credential_material_returned=False,
        secret_material_returned=False,
        command_constructed=False,
        prompt_constructed=False,
        model_inference_performed=False,
        network_activity_performed=False,
        connector_activity_performed=False,
        mcp_activity_performed=False,
        publication_performed=False,
        delivery_performed=False,
        dispatch_performed=False,
        execution_performed=False,
        infrastructure_mutation_performed=False,
        started_at=attempt.started_at,
        invocation_deadline=attempt.invocation_deadline,
        completed_at=NOW - timedelta(milliseconds=800),
        signing_key_id=source_policy.receipt_verification_signing_key_id,
        signature_algorithm=source_policy.receipt_signature_algorithm,
        integrity_signature="6" * 64,
    )
    result = _evidence(
        result_id="readiness-result.imp-226",
        consumption_id=attempt.consumption_id,
        attempt_id=attempt.attempt_id,
        attempt_digest=attempt.canonical_digest,
        claim_id=readiness_claim.claim_id,
        claim_digest=readiness_claim.canonical_digest,
        authorization_lease_id=authorization_lease.authorization_lease_id,
        authorization_lease_digest=authorization_lease.canonical_digest,
        start_result_id=attempt.start_result_id,
        start_result_digest=attempt.start_result_digest,
        readiness_profile_id=attempt.readiness_profile_id,
        readiness_profile_version=attempt.readiness_profile_version,
        readiness_profile_digest=attempt.readiness_profile_digest,
        destination_deployment_id=attempt.destination_deployment_id,
        destination_generation=attempt.destination_generation,
        destination_fencing_token_digest=attempt.destination_fencing_token_digest,
        protected_slot_commitment=attempt.protected_slot_commitment,
        protected_slot_generation=attempt.protected_slot_generation,
        runtime_envelope_id=attempt.runtime_envelope_id,
        runtime_envelope_commitment=attempt.runtime_envelope_commitment,
        runtime_envelope_generation=attempt.runtime_envelope_generation,
        state=state,
        failure_class=(
            None
            if success
            else (
                WorkflowProtectedRuntimeReadinessConsumptionFailureClass
            ).PROTECTED_ASSESSOR_REJECTED_WITHOUT_ASSESSMENT
        ),
        outcome_known=True,
        assessment_performed=True,
        runtime_ready=success,
        assessor_receipt_digest=receipt.canonical_digest,
        completed_at=receipt.completed_at,
        recorded_at=NOW - timedelta(milliseconds=700),
        scope=SCOPE,
        policy_id=source_policy.policy_id,
        policy_version=source_policy.policy_version,
        policy_digest=source_policy.canonical_digest,
        authority=zero,
    )
    return WorkflowProtectedRuntimeProcessCreationAuthorizationSource(
        result=cast(Any, result),
        attempt=cast(Any, attempt),
        readiness_claim=cast(Any, readiness_claim),
        readiness_receipt=cast(Any, receipt),
        readiness_authorization_lease=cast(Any, authorization_lease),
        readiness_authorization_claim=cast(Any, authorization_claim),
    )


class _Repository:
    durable = True

    def __init__(self, source: WorkflowProtectedRuntimeProcessCreationAuthorizationSource) -> None:
        self.source = source
        self.events: list[str] = []
        self.preflight_status = (
            WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightStatus.NONE
        )
        self.authoritative_time = NOW + timedelta(milliseconds=200)
        self.replay_lease: WorkflowProtectedRuntimeProcessCreationAuthorizationLease | None = None
        self.preflight_requests: list[
            WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightRequest
        ] = []
        self.source_requests: list[
            WorkflowProtectedRuntimeProcessCreationAuthorizationSourceRequest
        ] = []
        self.requests: list[WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseRequest] = []
        self.leases: list[WorkflowProtectedRuntimeProcessCreationAuthorizationLease] = []
        self.presentation_times: list[datetime] = []

    async def preflight_protected_runtime_process_creation_authorization(
        self, request: WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightRequest
    ) -> WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightResult:
        self.preflight_requests.append(request)
        self.events.append("preflight")
        return WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightResult(
            status=self.preflight_status,
            lease=self.replay_lease,
            evaluated_at=NOW,
        )

    async def get_protected_runtime_process_creation_authorization_source(
        self, request: WorkflowProtectedRuntimeProcessCreationAuthorizationSourceRequest
    ) -> WorkflowProtectedRuntimeProcessCreationAuthorizationSource:
        self.events.append("source")
        self.source_requests.append(request)
        assert request.readiness_result_id == self.source.result.result_id
        return self.source

    async def get_authoritative_time(self) -> datetime:
        self.events.append("authoritative_time")
        return self.authoritative_time

    async def authorize_protected_runtime_process_creation(
        self, request: WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseRequest
    ) -> WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseResult:
        self.events.append("authorize")
        validate_workflow_protected_runtime_process_creation_authorization_request(request)
        self.requests.append(request)
        self.leases.append(request.candidate)
        return WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseResult(
            status=WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseStatus.AUTHORIZED,
            lease=request.candidate,
            evaluated_at=NOW + timedelta(milliseconds=250),
        )

    async def list_protected_runtime_process_creation_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        evaluated_at: datetime,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedRuntimeProcessCreationAuthorizationPresentation, ...]:
        self.presentation_times.append(evaluated_at)
        leases = (
            lease
            for lease in self.leases
            if lease.scope == scope
            and (
                authorization_lease_ids is None
                or lease.authorization_lease_id in authorization_lease_ids
            )
        )
        return tuple(
            WorkflowProtectedRuntimeProcessCreationAuthorizationPresentation(
                lease=lease,
                consumed=False,
                evaluated_at=evaluated_at,
                effective_state=(
                    WorkflowProtectedRuntimeProcessCreationAuthorizationPresentationState.ACTIVE
                    if lease.is_active(evaluated_at=evaluated_at, consumed=False)
                    else (
                        WorkflowProtectedRuntimeProcessCreationAuthorizationPresentationState.EXPIRED
                    )
                ),
                protected_runtime_process_creation_authority_granted=lease.is_active(
                    evaluated_at=evaluated_at, consumed=False
                ),
            )
            for lease in tuple(leases)[:limit]
        )


class _Attestor:
    def __init__(
        self, repository: _Repository, *, available: bool = True, **overrides: object
    ) -> None:
        self.repository = repository
        self.available = available
        self.overrides = overrides

    async def attest_runtime_process_creation_lifecycle(
        self, request: WorkflowProtectedRuntimeProcessCreationLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeProcessCreationLifecycleAttestation:
        self.repository.events.append("attest")
        policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
        request_values = {
            name: getattr(request, name) for name in request.__slots__ if name != "requested_at"
        }
        values: dict[str, object] = {
            **request_values,
            "attestation_id": "process-creation-attestation.imp-227",
            "attestor_id": WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_ID,
            "attestor_version": WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_VERSION,
            "signing_key_id": (
                WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTATION_SIGNING_KEY_ID
            ),
            "signature_algorithm": "hmac-sha256",
            "observed_at": NOW + timedelta(milliseconds=100),
            "valid_until": NOW + timedelta(milliseconds=900),
            "runtime_envelope_eligible_until": NOW + timedelta(seconds=1),
            "exact_readiness_result_confirmed": True,
            "runtime_started_confirmed": True,
            "runtime_ready_confirmed": True,
            "readiness_assessment_confirmed": True,
            "metadata_only_confirmed": True,
            "runtime_envelope_current": True,
            "runtime_envelope_started": True,
            "destination_generation_current": True,
            "destination_fence_current": True,
            "protected_slot_generation_current": True,
            "readiness_profile_eligible": True,
            "process_creation_profile_id": policy.process_creation_profile_id,
            "process_creation_profile_version": policy.process_creation_profile_version,
            "process_creation_profile_digest": policy.process_creation_profile_digest,
            "prior_process_creation_claim_absent": True,
            "prior_process_creation_lease_absent": True,
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
            "integrity_signature": "7" * 64,
            **self.overrides,
        }
        attestation = WorkflowProtectedRuntimeProcessCreationLifecycleAttestation(
            **cast(Any, values), canonical_digest="0" * 64
        )
        return replace(
            attestation,
            canonical_digest=canonical_digest(attestation.digest_payload()),
        )

    def verify_runtime_process_creation_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeProcessCreationLifecycleAttestation
    ) -> bool:
        del attestation
        return True


class _ReceiptVerifier:
    available = True

    def verify_receipt(self, receipt: object) -> bool:
        del receipt
        return True


class _AuditSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def record(self, record: object) -> None:
        self.records.append(record)


def _context(
    *, subject_id: str = WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=subject_id,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=SCOPE,
        correlation_id="correlation.imp-227",
        decision_id="decision.imp-227",
        requested_at=NOW,
    )


def _service(
    repository: _Repository,
    audit: _AuditSink | None = None,
    attestation_overrides: dict[str, object] | None = None,
    *,
    attestor_available: bool = True,
) -> WorkflowProtectedRuntimeProcessCreationAuthorizationService:
    attestor = _Attestor(
        repository,
        available=attestor_available,
        **(attestation_overrides or {}),
    )
    return WorkflowProtectedRuntimeProcessCreationAuthorizationService(
        authorization_repository=cast(Any, repository),
        lifecycle_attestor=attestor,
        lifecycle_signature_verifier=attestor,
        readiness_receipt_signature_verifier=_ReceiptVerifier(),
        audit_sink=cast(Any, audit or _AuditSink()),
    )


async def _authorize(
    service: WorkflowProtectedRuntimeProcessCreationAuthorizationService,
    source: WorkflowProtectedRuntimeProcessCreationAuthorizationSource,
) -> WorkflowProtectedRuntimeProcessCreationAuthorizationLease:
    return await service.authorize(
        readiness_result_id=source.result.result_id,
        policy_id=service.policy.policy_id,
        policy_version=service.policy.policy_version,
        single_use_nonrenewable_nontransferable_future_request_acknowledged=True,
        no_process_creation_or_scheduling_authority_acknowledged=True,
        idempotency_key="imp-227-process-creation",
        context=_context(),
    )


def test_public_authorize_surface_is_metadata_only() -> None:
    parameters = set(
        inspect.signature(
            WorkflowProtectedRuntimeProcessCreationAuthorizationService.authorize
        ).parameters
    )
    assert parameters == {
        "self",
        "readiness_result_id",
        "policy_id",
        "policy_version",
        "single_use_nonrenewable_nontransferable_future_request_acknowledged",
        "no_process_creation_or_scheduling_authority_acknowledged",
        "idempotency_key",
        "context",
    }
    assert not parameters.intersection(
        {"command", "connector", "credential", "endpoint", "executable", "network"}
    )


@pytest.mark.asyncio
async def test_replay_first_then_issues_bounded_nonoperational_lease() -> None:
    source = _source()
    repository = _Repository(source)
    lease = await _authorize(_service(repository), source)

    assert repository.events == [
        "preflight",
        "source",
        "attest",
        "authoritative_time",
        "authorize",
    ]
    assert not hasattr(repository.source_requests[0], "readiness_result_digest")
    assert not hasattr(repository.preflight_requests[0], "readiness_result_digest")
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
    assert repository.preflight_requests[0].request_fingerprint == canonical_digest(
        {
            "policy_digest": policy.canonical_digest,
            "scope": SCOPE.canonical_value(),
            "readiness_result_id": source.result.result_id,
            "subject_id": WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
            "single_use_nonrenewable_nontransferable_future_request_acknowledged": True,
            "no_process_creation_or_scheduling_authority_acknowledged": True,
        }
    )
    assert lease.valid_until - lease.issued_at <= timedelta(seconds=1)
    assert lease.single_use is True
    assert lease.renewable is False
    assert lease.transferable is False
    assert lease.lease_is_bearer_capability is False
    authority = lease.authority.canonical_value()
    assert authority.pop("protected_runtime_process_creation_authority_granted") is True
    assert not any(authority.values())

    replay_repository = _Repository(source)
    replay_repository.preflight_status = (
        WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightStatus.REPLAY
    )
    replay_repository.replay_lease = lease
    assert await _authorize(_service(replay_repository, attestor_available=False), source) == lease
    assert replay_repository.events == ["preflight"]
    assert replay_repository.source_requests == []


@pytest.mark.asyncio
async def test_only_exact_ready_result_is_eligible() -> None:
    source = _source(
        state=(
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY
    )
    repository = _Repository(source)
    with pytest.raises(WorkflowProtectedRuntimeProcessCreationAuthorizationError) as exc_info:
        await _authorize(_service(repository), source)
    assert exc_info.value.code == "workflow_protected_runtime_process_creation_evidence_conflict"
    assert repository.events == ["preflight", "source"]


@pytest.mark.asyncio
async def test_changed_replay_fails_closed_before_source_or_attestor_io() -> None:
    source = _source()
    repository = _Repository(source)
    repository.preflight_status = (
        WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightStatus.IDEMPOTENCY_CONFLICT
    )

    with pytest.raises(WorkflowProtectedRuntimeProcessCreationAuthorizationError) as exc_info:
        await _authorize(_service(repository, attestor_available=False), source)

    assert exc_info.value.code.endswith("idempotency_conflict")
    assert repository.events == ["preflight"]
    assert repository.source_requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("field_name", ["generic_process_created", "scheduling_performed"])
async def test_attestation_fails_closed_if_process_or_schedule_exists(field_name: str) -> None:
    source = _source()
    repository = _Repository(source)
    with pytest.raises(WorkflowProtectedRuntimeProcessCreationAuthorizationError) as exc_info:
        await _authorize(_service(repository, attestation_overrides={field_name: True}), source)
    assert exc_info.value.code == "workflow_protected_runtime_process_creation_attestation_invalid"
    assert repository.events == ["preflight", "source", "attest", "authoritative_time"]
    assert repository.requests == []


@pytest.mark.asyncio
async def test_non_consumer_is_denied_before_protected_state_io() -> None:
    source = _source()
    repository = _Repository(source)
    service = _service(repository)
    with pytest.raises(WorkflowProtectedRuntimeProcessCreationAuthorizationError) as exc_info:
        await service.authorize(
            readiness_result_id=source.result.result_id,
            policy_id=service.policy.policy_id,
            policy_version=service.policy.policy_version,
            single_use_nonrenewable_nontransferable_future_request_acknowledged=True,
            no_process_creation_or_scheduling_authority_acknowledged=True,
            idempotency_key="imp-227-process-creation",
            context=_context(subject_id="human.user"),
        )
    assert exc_info.value.code.endswith("consumer_identity_required")
    assert repository.events == []


@pytest.mark.asyncio
async def test_semantic_audit_states_that_no_operation_was_performed() -> None:
    source = _source()
    repository = _Repository(source)
    audit = _AuditSink()
    await _authorize(_service(repository, audit), source)

    record = cast(Any, audit.records[-1])
    metadata = dict(record.target_metadata)
    assert metadata["protected_runtime_process_creation_request_authority"] == "true"
    assert metadata["process_creation_performed"] == "false"
    assert metadata["scheduling_authority"] == "false"
    assert metadata["network_access_authority"] == "false"
    assert metadata["connector_activity_authority"] == "false"
    assert metadata["execution_authority"] == "false"
    assert metadata["infrastructure_mutation_authority"] == "false"


@pytest.mark.asyncio
async def test_missing_acknowledgement_is_denied_and_minimally_audited() -> None:
    source = _source()
    repository = _Repository(source)
    audit = _AuditSink()
    service = _service(repository, audit)

    with pytest.raises(WorkflowProtectedRuntimeProcessCreationAuthorizationError) as exc_info:
        await service.authorize(
            readiness_result_id=source.result.result_id,
            policy_id=service.policy.policy_id,
            policy_version=service.policy.policy_version,
            single_use_nonrenewable_nontransferable_future_request_acknowledged=False,
            no_process_creation_or_scheduling_authority_acknowledged=True,
            idempotency_key="imp-227-process-creation",
            context=_context(),
        )

    assert exc_info.value.code.endswith("acknowledgement_required")
    assert repository.events == []
    record = cast(Any, audit.records[-1])
    metadata = dict(record.target_metadata)
    assert record.outcome == "denied"
    assert record.event_type.endswith(".rejected")
    assert record.result_code.endswith("acknowledgement_required")
    assert set(metadata) == {
        "readiness_result_reference",
        "protected_runtime_process_creation_request_authority",
        "process_creation_performed",
        "scheduling_performed",
        "execution_performed",
        "infrastructure_mutation_performed",
    }
    assert not any(value == source.result.result_id for value in metadata.values())
    assert all(metadata[name] == "false" for name in set(metadata) - {"readiness_result_reference"})


@pytest.mark.asyncio
async def test_expiry_audit_uses_inventory_time_and_is_idempotent_per_service() -> None:
    source = _source()
    repository = _Repository(source)
    audit = _AuditSink()
    service = _service(repository, audit)
    lease = await _authorize(service, source)
    repository.authoritative_time = lease.effective_until

    first = await service.list_presentations(scope=SCOPE)
    second = await service.list_presentations(scope=SCOPE)

    assert first.server_time == second.server_time == lease.effective_until
    assert repository.presentation_times == [lease.effective_until, lease.effective_until]
    assert all(
        presentation.evaluated_at == first.server_time
        and presentation.effective_state.value == "expired"
        and not presentation.protected_runtime_process_creation_authority_granted
        for presentation in first.presentations
    )
    expiry_records = [
        cast(Any, record)
        for record in audit.records
        if cast(Any, record).event_type.endswith(".expired")
    ]
    assert len(expiry_records) == 1
    assert expiry_records[0].occurred_at == lease.effective_until
    assert (
        dict(expiry_records[0].target_metadata)[
            "protected_runtime_process_creation_request_authority"
        ]
        == "false"
    )
