from __future__ import annotations

from dataclasses import fields, replace
from datetime import timedelta
from typing import Any, cast

import pytest
from test_workflow_protected_runtime_context_injection_authorizations import (
    PREFLIGHT_AT,
    _source,
)

from atlas.modules.workflows.adapters import (
    DeterministicDevelopmentWorkflowProtectedRuntimeHandleLifecycleAttestor,
    UnavailableWorkflowProtectedRuntimeHandleLifecycleAttestor,
)
from atlas.modules.workflows.application import (
    WorkflowProtectedRuntimeContextInjectionAuthorizationError,
    WorkflowProtectedRuntimeHandleLifecycleAttestationRequest,
)
from atlas.modules.workflows.domain import (
    code_owned_workflow_protected_runtime_context_injection_authorization_policy,
)


def _request(*, nonce: str = "9" * 64) -> WorkflowProtectedRuntimeHandleLifecycleAttestationRequest:
    source = _source()
    policy = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
    return WorkflowProtectedRuntimeHandleLifecycleAttestationRequest(
        access_result_id=source.result.access_id,
        access_result_digest=source.result.canonical_digest,
        access_attempt_id=source.attempt.attempt_id,
        access_attempt_digest=source.attempt.canonical_digest,
        access_consumption_claim_id=source.consumption_claim.claim_id,
        access_consumption_claim_digest=source.consumption_claim.canonical_digest,
        access_authorization_lease_id=source.access_authorization_lease.authorization_lease_id,
        access_authorization_lease_digest=source.access_authorization_lease.canonical_digest,
        accessor_receipt_digest=source.accessor_receipt_digest,
        accessor_receipt_signing_key_id=source.accessor_receipt_signing_key_id,
        protected_runtime_handle_id=source.protected_runtime_handle_id,
        protected_runtime_handle_digest=source.protected_runtime_handle_digest,
        protected_runtime_handle_created_at=source.protected_runtime_handle_created_at,
        protected_runtime_handle_usable_until=source.protected_runtime_handle_usable_until,
        destination_boundary_id=source.destination_boundary_id,
        destination_deployment_id=source.destination_deployment_id,
        destination_generation=source.destination_generation,
        destination_fencing_token_digest=source.destination_fencing_token_digest,
        runtime_handle_profile_id=source.runtime_handle_profile_id,
        runtime_handle_profile_version=source.runtime_handle_profile_version,
        runtime_handle_profile_digest=source.runtime_handle_profile_digest,
        injector_contract_id=policy.required_injector_contract_id,
        injector_contract_version=policy.required_injector_contract_version,
        injector_id=policy.approved_injector_id,
        injector_version=policy.approved_injector_version,
        runtime_slot_profile_id=policy.runtime_slot_profile_id,
        runtime_slot_profile_version=policy.runtime_slot_profile_version,
        runtime_slot_profile_digest=policy.runtime_slot_profile_digest,
        scope=source.result.scope,
        consumer_subject_id=source.consumer_subject_id,
        consumer_audience=source.consumer_audience,
        consumer_contract_id=source.consumer_contract_id,
        consumer_contract_version=source.consumer_contract_version,
        purpose_id=policy.purpose_id,
        request_nonce_digest=nonce,
        requested_at=PREFLIGHT_AT,
    )


@pytest.mark.asyncio
async def test_development_attestor_is_signed_deterministic_and_metadata_only() -> None:
    attestor = DeterministicDevelopmentWorkflowProtectedRuntimeHandleLifecycleAttestor(
        development_enabled=True,
        clock=lambda: PREFLIGHT_AT + timedelta(milliseconds=25),
    )

    first = await attestor.attest_runtime_handle_lifecycle(_request())
    second = await attestor.attest_runtime_handle_lifecycle(_request())

    assert first == second
    assert first.runtime_handle_present is True
    assert first.runtime_handle_unexpired is True
    assert first.runtime_handle_unrevoked is True
    assert first.runtime_handle_undestroyed is True
    assert first.runtime_handle_uninjected is True
    assert first.runtime_handle_unused is True
    assert first.destination_generation_current is True
    assert first.destination_fence_current is True
    assert first.injector_profile_eligible is True
    assert first.runtime_slot_profile_eligible is True
    assert all(
        value is False
        for value in (
            first.runtime_handle_is_bearer_capability,
            first.raw_context_included,
            first.runtime_handle_material_included,
            first.runtime_payload_included,
            first.runtime_handle_locator_included,
            first.endpoint_included,
            first.credential_included,
            first.secret_included,
            first.bearer_token_included,
            first.provider_payload_included,
            first.handle_lookup_authorized,
            first.handle_retrieval_authorized,
            first.handle_use_authorized,
            first.runtime_use_authorized,
            first.runtime_context_injection_authorized,
            first.injection_consumption_outstanding,
            first.connector_activity_authorized,
            first.network_activity_authorized,
            first.readiness_probe_authorized,
            first.publication_authorized,
            first.delivery_authorized,
            first.dispatch_authorized,
            first.execution_authorized,
            first.infrastructure_mutation_authorized,
        )
    )
    assert attestor.verify_runtime_handle_lifecycle_attestation(first) is True
    assert (
        attestor.verify_runtime_handle_lifecycle_attestation(
            replace(first, integrity_signature="0" * 64)
        )
        is False
    )
    assert {
        "raw_context",
        "runtime_handle_material",
        "runtime_payload",
        "runtime_handle_locator",
        "endpoint",
        "credential",
        "secret",
        "bearer_token",
        "provider_payload",
    }.isdisjoint(field.name for field in fields(first))

    changed_nonce = await attestor.attest_runtime_handle_lifecycle(_request(nonce="8" * 64))
    assert changed_nonce.attestation_id != first.attestation_id
    assert changed_nonce.integrity_signature != first.integrity_signature


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("option", "field_name"),
    (
        ({"runtime_handle_revoked": True}, "runtime_handle_unrevoked"),
        ({"runtime_handle_injected": True}, "runtime_handle_uninjected"),
        ({"runtime_handle_used": True}, "runtime_handle_unused"),
        ({"injection_consumption_outstanding": True}, "injection_consumption_outstanding"),
        ({"destination_fence_current": False}, "destination_fence_current"),
        ({"injector_profile_eligible": False}, "injector_profile_eligible"),
    ),
)
async def test_development_attestor_preserves_negative_lifecycle_evidence(
    option: dict[str, bool], field_name: str
) -> None:
    attestor = DeterministicDevelopmentWorkflowProtectedRuntimeHandleLifecycleAttestor(
        development_enabled=True,
        clock=lambda: PREFLIGHT_AT + timedelta(milliseconds=25),
        **cast(Any, option),
    )

    attestation = await attestor.attest_runtime_handle_lifecycle(_request())

    assert getattr(attestation, field_name) is (field_name == "injection_consumption_outstanding")
    assert attestor.verify_runtime_handle_lifecycle_attestation(attestation) is True


@pytest.mark.asyncio
async def test_unavailable_and_disabled_attestors_fail_closed_without_request_leakage() -> None:
    request = _request()
    disabled = DeterministicDevelopmentWorkflowProtectedRuntimeHandleLifecycleAttestor()
    unavailable = UnavailableWorkflowProtectedRuntimeHandleLifecycleAttestor()

    for attestor in (disabled, unavailable):
        with pytest.raises(WorkflowProtectedRuntimeContextInjectionAuthorizationError) as caught:
            await attestor.attest_runtime_handle_lifecycle(request)
        rendered = f"{caught.value} {caught.value.detail}"
        assert request.protected_runtime_handle_id not in rendered
        assert request.request_nonce_digest not in rendered
        if hasattr(attestor, "calls"):
            assert attestor.calls == []
        assert attestor.verify_runtime_handle_lifecycle_attestation(cast(Any, None)) is False
