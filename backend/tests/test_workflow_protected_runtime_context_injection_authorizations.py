from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import timedelta
from typing import Any, cast

import pytest
from test_workflow_protected_resident_context_access_authorization_domain import (
    _lease as _access_authorization_lease,
)
from test_workflow_protected_resident_context_access_consumption_domain import (
    NOW,
    SUCCESS,
    _payload,
)
from test_workflow_protected_resident_context_access_consumption_domain import (
    _attempt as _access_attempt,
)
from test_workflow_protected_resident_context_access_consumption_domain import (
    _claim as _access_claim,
)
from test_workflow_protected_resident_context_access_consumption_domain import (
    _receipt as _accessor_receipt,
)
from test_workflow_protected_resident_context_access_consumption_domain import (
    _result as _access_result,
)

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedRuntimeContextInjectionAuthorizationError,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseResult,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightResult,
    WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation,
    WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState,
    WorkflowProtectedRuntimeContextInjectionAuthorizationService,
    WorkflowProtectedRuntimeContextInjectionAuthorizationSource,
    WorkflowProtectedRuntimeHandleLifecycleAttestation,
    WorkflowProtectedRuntimeHandleLifecycleAttestationRequest,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    validate_workflow_protected_runtime_context_injection_authorization_request,
)
from atlas.modules.workflows.application.protected_resident_context_access_consumption_ports import (  # noqa: E501
    build_workflow_protected_resident_context_trusted_accessor_instruction,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextInjectionAuthorizationLease,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_runtime_context_injection_authorization_policy,
)

SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")
PREFLIGHT_AT = NOW + timedelta(milliseconds=350)
AUTHORITATIVE_NOW = NOW + timedelta(milliseconds=400)
ATTESTATION_VALID_UNTIL = NOW + timedelta(milliseconds=1400)


def _rebuild(value: Any, **overrides: object) -> Any:
    values = {
        field.name: getattr(value, field.name)
        for field in fields(value)
        if field.name != "canonical_digest"
    }
    values.update(overrides)
    return type(value)(**cast(Any, values), canonical_digest=canonical_digest(_payload(values)))


def _source() -> WorkflowProtectedRuntimeContextInjectionAuthorizationSource:
    base_result = _access_result(SUCCESS)
    access_lease = _rebuild(
        _access_authorization_lease(),
        scope=base_result.scope,
        protected_resident_context_id=base_result.protected_resident_context_id,
        protected_resident_context_digest=base_result.protected_resident_context_digest,
        protected_resident_context_usable_until=(
            base_result.protected_resident_context_usable_until
        ),
    )
    claim = _rebuild(
        _access_claim(),
        authorization_lease_id=access_lease.authorization_lease_id,
        authorization_lease_digest=access_lease.canonical_digest,
    )
    attempt = _rebuild(
        _access_attempt(),
        consumption_claim_id=claim.claim_id,
        consumption_claim_digest=claim.canonical_digest,
        authorization_lease_id=access_lease.authorization_lease_id,
        authorization_lease_digest=access_lease.canonical_digest,
    )
    instruction = build_workflow_protected_resident_context_trusted_accessor_instruction(attempt)
    receipt = _rebuild(
        _accessor_receipt(),
        access_id=attempt.access_id,
        attempt_id=attempt.attempt_id,
        consumption_claim_id=claim.claim_id,
        instruction_digest=instruction.canonical_digest,
        authorization_lease_id=access_lease.authorization_lease_id,
        authorization_lease_digest=access_lease.canonical_digest,
        protected_resident_context_id=attempt.protected_resident_context_id,
        protected_resident_context_digest=attempt.protected_resident_context_digest,
    )
    result = _rebuild(
        base_result,
        attempt_id=attempt.attempt_id,
        attempt_digest=attempt.canonical_digest,
        consumption_claim_id=claim.claim_id,
        consumption_claim_digest=claim.canonical_digest,
        authorization_lease_id=access_lease.authorization_lease_id,
        authorization_lease_digest=access_lease.canonical_digest,
        accessor_receipt_digest=receipt.canonical_digest,
    )
    return WorkflowProtectedRuntimeContextInjectionAuthorizationSource(
        result=result,
        attempt=attempt,
        consumption_claim=claim,
        access_authorization_lease=access_lease,
        accessor_receipt=receipt,
        protected_runtime_handle_id=cast(str, result.protected_runtime_handle_id),
        protected_runtime_handle_digest=cast(str, result.protected_runtime_handle_digest),
        protected_runtime_handle_created_at=cast(Any, result.protected_runtime_handle_created_at),
        protected_runtime_handle_usable_until=cast(
            Any, result.protected_runtime_handle_usable_until
        ),
        protected_resident_context_usable_until=(result.protected_resident_context_usable_until),
        destination_boundary_id=attempt.destination_boundary_id,
        destination_deployment_id=attempt.destination_deployment_id,
        destination_generation=attempt.destination_generation,
        destination_fencing_token_digest=attempt.destination_fencing_token_digest,
        runtime_handle_profile_id=result.runtime_handle_profile_id,
        runtime_handle_profile_version=result.runtime_handle_profile_version,
        runtime_handle_profile_digest=result.runtime_handle_profile_digest,
        consumer_subject_id=result.consumer_subject_id,
        consumer_audience=result.consumer_audience,
        consumer_contract_id=result.consumer_contract_id,
        consumer_contract_version=result.consumer_contract_version,
        accessor_receipt_digest=receipt.canonical_digest,
        accessor_receipt_signing_key_id=receipt.signing_key_id,
        accessor_receipt_signature_algorithm=receipt.signature_algorithm,
        accessor_receipt_integrity_signature=receipt.integrity_signature,
    )


def _attestation(
    request: WorkflowProtectedRuntimeHandleLifecycleAttestationRequest,
    **overrides: object,
) -> WorkflowProtectedRuntimeHandleLifecycleAttestation:
    values: dict[str, object] = {
        field.name: getattr(request, field.name)
        for field in fields(request)
        if field.name != "requested_at"
    }
    values.update(
        {
            "attestation_id": "attestation.runtime-handle.imp-218",
            "attestor_id": "attestor.workflow-protected-runtime-handle-lifecycle",
            "attestor_version": "1.0",
            "signing_key_id": "key.workflow-protected-runtime-handle-lifecycle.v1",
            "signature_algorithm": "test-sha256-v1",
            "observed_at": PREFLIGHT_AT,
            "valid_until": ATTESTATION_VALID_UNTIL,
            "runtime_handle_present": True,
            "runtime_handle_is_bearer_capability": False,
            "runtime_handle_unexpired": True,
            "runtime_handle_unrevoked": True,
            "runtime_handle_undestroyed": True,
            "runtime_handle_uninjected": True,
            "runtime_handle_unused": True,
            "destination_generation_current": True,
            "destination_fence_current": True,
            "injector_profile_eligible": True,
            "runtime_slot_profile_eligible": True,
            "raw_context_included": False,
            "runtime_handle_material_included": False,
            "runtime_payload_included": False,
            "runtime_handle_locator_included": False,
            "endpoint_included": False,
            "credential_included": False,
            "secret_included": False,
            "bearer_token_included": False,
            "provider_payload_included": False,
            "handle_lookup_authorized": False,
            "handle_retrieval_authorized": False,
            "handle_use_authorized": False,
            "runtime_use_authorized": False,
            "runtime_context_injection_authorized": False,
            "injection_consumption_outstanding": False,
            "connector_activity_authorized": False,
            "network_activity_authorized": False,
            "readiness_probe_authorized": False,
            "publication_authorized": False,
            "delivery_authorized": False,
            "dispatch_authorized": False,
            "execution_authorized": False,
            "infrastructure_mutation_authorized": False,
            "integrity_signature": "signature.runtime-handle.imp-218",
        }
    )
    values.update(overrides)
    return WorkflowProtectedRuntimeHandleLifecycleAttestation(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


class _Repository:
    durable = True

    def __init__(
        self,
        source: WorkflowProtectedRuntimeContextInjectionAuthorizationSource,
        *,
        events: list[str] | None = None,
    ) -> None:
        self.source = source
        self.events = events if events is not None else []
        self.preflight_status = (
            WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightStatus.NONE
        )
        self.replay_lease: WorkflowProtectedRuntimeContextInjectionAuthorizationLease | None = None
        self.preflights: list[
            WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightRequest
        ] = []
        self.source_calls = 0
        self.authorizations: list[
            WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseRequest
        ] = []

    async def preflight_protected_runtime_context_injection_authorization(
        self,
        request: WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightRequest,
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightResult:
        self.events.append("preflight")
        self.preflights.append(request)
        return WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightResult(
            status=self.preflight_status,
            lease=self.replay_lease,
            evaluated_at=PREFLIGHT_AT,
        )

    async def get_protected_runtime_context_injection_authorization_source(
        self, *, access_result_id: str
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationSource:
        self.events.append("source")
        assert access_result_id == self.source.result.access_id
        self.source_calls += 1
        return self.source

    async def get_authoritative_time(self) -> Any:
        self.events.append("authoritative_time")
        return AUTHORITATIVE_NOW

    async def authorize_protected_runtime_context_injection(
        self,
        request: WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseRequest,
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseResult:
        self.events.append("authorize")
        validate_workflow_protected_runtime_context_injection_authorization_request(request)
        self.authorizations.append(request)
        return WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseResult(
            status=WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseStatus.AUTHORIZED,
            lease=request.candidate,
            evaluated_at=AUTHORITATIVE_NOW,
        )

    async def list_protected_runtime_context_injection_authorization_presentations(
        self, **kwargs: object
    ) -> tuple[WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation, ...]:
        del kwargs
        return ()


class _Attestor:
    available = True

    def __init__(
        self,
        *,
        events: list[str] | None = None,
        overrides: dict[str, object] | None = None,
    ) -> None:
        self.events = events if events is not None else []
        self.overrides = overrides or {}
        self.requests: list[WorkflowProtectedRuntimeHandleLifecycleAttestationRequest] = []

    async def attest_runtime_handle_lifecycle(
        self, request: WorkflowProtectedRuntimeHandleLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeHandleLifecycleAttestation:
        self.events.append("attest")
        self.requests.append(request)
        return _attestation(request, **self.overrides)


class _Verifier:
    def __init__(self) -> None:
        self.lifecycle_calls = 0
        self.receipt_calls = 0

    def verify_runtime_handle_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeHandleLifecycleAttestation
    ) -> bool:
        del attestation
        self.lifecycle_calls += 1
        return True

    def verify_receipt(self, receipt: object) -> bool:
        del receipt
        self.receipt_calls += 1
        return True


class _AuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, record: AuditRecord) -> None:
        self.records.append(record)


def _context() -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=SCOPE,
        correlation_id="correlation.imp-218",
        decision_id="decision.imp-218",
        requested_at=NOW,
    )


def _service(
    repository: _Repository,
    attestor: _Attestor,
    verifier: _Verifier,
    audit_sink: _AuditSink | None = None,
) -> WorkflowProtectedRuntimeContextInjectionAuthorizationService:
    return WorkflowProtectedRuntimeContextInjectionAuthorizationService(
        authorization_repository=repository,
        lifecycle_attestor=attestor,
        lifecycle_signature_verifier=verifier,
        accessor_receipt_signature_verifier=verifier,
        audit_sink=audit_sink or _AuditSink(),
    )


async def _authorize(
    service: WorkflowProtectedRuntimeContextInjectionAuthorizationService,
    source: WorkflowProtectedRuntimeContextInjectionAuthorizationSource,
) -> WorkflowProtectedRuntimeContextInjectionAuthorizationLease:
    return await service.authorize(
        access_result_id=source.result.access_id,
        access_result_digest=source.result.canonical_digest,
        policy_id=service.policy.policy_id,
        policy_version=service.policy.policy_version,
        idempotency_key="imp-218-runtime-injection",
        context=_context(),
    )


def test_public_authorize_surface_contains_only_result_policy_idempotency_and_context() -> None:
    parameters = set(
        inspect.signature(
            WorkflowProtectedRuntimeContextInjectionAuthorizationService.authorize
        ).parameters
    )

    assert parameters == {
        "self",
        "access_result_id",
        "access_result_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    assert not parameters.intersection(
        {
            "protected_runtime_handle_id",
            "protected_runtime_handle_digest",
            "destination",
            "injector",
            "runtime_slot",
            "lifetime",
            "authority",
        }
    )


@pytest.mark.asyncio
async def test_authorize_derives_bounded_single_use_lease_without_injection_or_handle_use() -> None:
    source = _source()
    events: list[str] = []
    repository = _Repository(source, events=events)
    attestor = _Attestor(events=events)
    verifier = _Verifier()
    audit_sink = _AuditSink()

    lease = await _authorize(_service(repository, attestor, verifier, audit_sink), source)

    assert repository.source_calls == 1
    assert len(attestor.requests) == 1
    assert len(repository.authorizations) == 1
    assert events == [
        "preflight",
        "source",
        "attest",
        "authoritative_time",
        "authorize",
    ]
    assert verifier.lifecycle_calls == 2
    assert verifier.receipt_calls == 2
    assert lease.access_result_id == source.result.access_id
    assert lease.protected_runtime_handle_id == source.protected_runtime_handle_id
    assert lease.injector_id == (
        code_owned_workflow_protected_runtime_context_injection_authorization_policy().approved_injector_id
    )
    assert lease.valid_until - lease.issued_at <= timedelta(seconds=1)
    assert lease.protected_runtime_context_injection_authority_granted is True
    assert all(
        getattr(lease, name) is False
        for name in (
            "protected_resident_context_access_authority_granted",
            "network_access_authorized",
            "readiness_probe_authorized",
            "publication_authorized",
            "delivery_authorized",
            "dispatch_authorized",
            "execution_authorized",
            "infrastructure_mutation_authorized",
        )
    )
    assert len(audit_sink.records) == 1
    assert not hasattr(repository, "inject")
    assert not hasattr(attestor, "lookup_handle")


@pytest.mark.asyncio
async def test_exact_replay_bypasses_source_attestor_and_signature_io_even_when_expired() -> None:
    source = _source()
    repository = _Repository(source)
    attestor = _Attestor()
    verifier = _Verifier()
    service = _service(repository, attestor, verifier)
    lease = await _authorize(service, source)
    source_calls = repository.source_calls
    attestor_calls = len(attestor.requests)
    lifecycle_calls = verifier.lifecycle_calls
    receipt_calls = verifier.receipt_calls
    expired = _rebuild(
        lease,
        issued_at=source.result.recorded_at,
        valid_until=PREFLIGHT_AT,
        effective_until=PREFLIGHT_AT,
    )
    repository.preflight_status = (
        WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightStatus.REPLAY
    )
    repository.replay_lease = expired

    replay = await _authorize(service, source)

    assert replay is expired
    assert replay.is_active(evaluated_at=PREFLIGHT_AT) is False
    assert repository.source_calls == source_calls
    assert len(attestor.requests) == attestor_calls
    assert verifier.lifecycle_calls == lifecycle_calls
    assert verifier.receipt_calls == receipt_calls
    assert len(repository.authorizations) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsafe_field",
    (
        "runtime_handle_material_included",
        "runtime_payload_included",
        "runtime_context_injection_authorized",
        "injection_consumption_outstanding",
    ),
)
async def test_signed_adr_168_hardening_fields_fail_closed_when_true(
    unsafe_field: str,
) -> None:
    source = _source()
    repository = _Repository(source)
    attestor = _Attestor(overrides={unsafe_field: True})
    verifier = _Verifier()

    with pytest.raises(
        WorkflowProtectedRuntimeContextInjectionAuthorizationError,
        match="denied",
    ):
        await _authorize(_service(repository, attestor, verifier), source)

    assert repository.authorizations == []
    assert verifier.lifecycle_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsafe_field",
    (
        "runtime_handle_material_included",
        "runtime_payload_included",
        "runtime_context_injection_authorized",
        "injection_consumption_outstanding",
    ),
)
async def test_offline_repository_validation_rejects_signed_hardening_violation(
    unsafe_field: str,
) -> None:
    source = _source()
    repository = _Repository(source)
    await _authorize(
        _service(repository, _Attestor(), _Verifier()),
        source,
    )
    request = repository.authorizations[0]
    unsafe_attestation = _rebuild(
        request.lifecycle_attestation,
        **{unsafe_field: True},
    )
    assert unsafe_attestation.canonical_digest == canonical_digest(
        unsafe_attestation.digest_payload()
    )
    unsafe_candidate = _rebuild(
        request.candidate,
        lifecycle_attestation_digest=unsafe_attestation.canonical_digest,
    )
    unsafe_request = replace(
        request,
        lifecycle_attestation=unsafe_attestation,
        candidate=unsafe_candidate,
    )

    with pytest.raises(ValueError, match="evidence is invalid"):
        validate_workflow_protected_runtime_context_injection_authorization_request(unsafe_request)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field_name",
    (
        "runtime_handle_present",
        "runtime_handle_unexpired",
        "runtime_handle_unrevoked",
        "runtime_handle_undestroyed",
        "runtime_handle_uninjected",
        "runtime_handle_unused",
        "destination_generation_current",
        "destination_fence_current",
        "injector_profile_eligible",
        "runtime_slot_profile_eligible",
    ),
)
async def test_negative_lifecycle_or_injection_eligibility_fails_closed(
    field_name: str,
) -> None:
    source = _source()
    repository = _Repository(source)

    with pytest.raises(WorkflowProtectedRuntimeContextInjectionAuthorizationError):
        await _authorize(
            _service(
                repository,
                _Attestor(overrides={field_name: False}),
                _Verifier(),
            ),
            source,
        )

    assert repository.authorizations == []


@pytest.mark.asyncio
async def test_non_consumer_identity_fails_before_preflight() -> None:
    source = _source()
    repository = _Repository(source)
    context = replace(_context(), subject_id="user.admin", actor_type="human")
    service = _service(repository, _Attestor(), _Verifier())

    with pytest.raises(WorkflowProtectedRuntimeContextInjectionAuthorizationError) as caught:
        await service.authorize(
            access_result_id=source.result.access_id,
            access_result_digest=source.result.canonical_digest,
            policy_id=service.policy.policy_id,
            policy_version=service.policy.policy_version,
            idempotency_key="imp-218-human-denied",
            context=context,
        )

    assert caught.value.code.endswith("consumer_identity_required")
    assert repository.preflights == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    (
        WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightStatus.IDEMPOTENCY_CONFLICT,
        WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightStatus.EVIDENCE_CONFLICT,
        WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightStatus.ALREADY_AUTHORIZED,
    ),
)
async def test_changed_or_competing_replay_fails_before_external_io(
    status: WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightStatus,
) -> None:
    source = _source()
    repository = _Repository(source)
    repository.preflight_status = status
    attestor = _Attestor()

    with pytest.raises(WorkflowProtectedRuntimeContextInjectionAuthorizationError):
        await _authorize(_service(repository, attestor, _Verifier()), source)

    assert repository.source_calls == 0
    assert attestor.requests == []
    assert repository.authorizations == []


@pytest.mark.asyncio
async def test_presentation_projects_authority_only_for_active_unconsumed_lease() -> None:
    source = _source()
    repository = _Repository(source)
    lease = await _authorize(_service(repository, _Attestor(), _Verifier()), source)

    active = WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation(
        lease=lease,
        consumed=False,
        evaluated_at=lease.issued_at,
        effective_state=(
            WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState.ACTIVE
        ),
        protected_runtime_context_injection_authority_granted=True,
    )
    consumed = WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation(
        lease=lease,
        consumed=True,
        evaluated_at=lease.issued_at,
        effective_state=(
            WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState.EXPIRED
        ),
        protected_runtime_context_injection_authority_granted=False,
    )
    expired = WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation(
        lease=lease,
        consumed=False,
        evaluated_at=lease.valid_until,
        effective_state=(
            WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState.EXPIRED
        ),
        protected_runtime_context_injection_authority_granted=False,
    )

    assert active.protected_runtime_context_injection_authority_granted is True
    assert consumed.protected_runtime_context_injection_authority_granted is False
    assert expired.protected_runtime_context_injection_authority_granted is False
    with pytest.raises(ValueError, match="inconsistent"):
        WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation(
            lease=lease,
            consumed=True,
            evaluated_at=lease.issued_at,
            effective_state=(
                WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState.ACTIVE
            ),
            protected_runtime_context_injection_authority_granted=True,
        )
