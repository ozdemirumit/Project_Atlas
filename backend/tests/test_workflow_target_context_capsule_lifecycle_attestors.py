from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters import (
    DenyAllWorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier,
    UnavailableWorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor,
)
from atlas.modules.workflows.application import (
    WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError,
)
from atlas.modules.workflows.domain import WorkflowScope


def _request() -> WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest:
    requested_at = datetime(2026, 8, 16, 4, 30, tzinfo=UTC)
    return WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest(
        opening_result_id="opening.secret-result",
        opening_result_digest="1" * 64,
        consumer_binding_id="binding.secret-consumer",
        consumer_binding_digest="2" * 64,
        sealed_capsule_id="capsule.secret-value",
        sealed_capsule_digest="3" * 64,
        capsule_schema_id="schema.secret-value",
        capsule_schema_version="1.0",
        scope=WorkflowScope(
            organization_id="org.secret",
            environment_id="env.secret",
            site_id="site.secret",
        ),
        consumer_subject_id="workload.secret-consumer",
        request_nonce_digest="4" * 64,
        requested_at=requested_at,
    )


def test_unavailable_capsule_lifecycle_attestor_fails_closed_without_request_leakage() -> None:
    attestor = UnavailableWorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor()
    request = _request()

    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError
    ) as caught:
        asyncio.run(attestor.attest_capsule_lifecycle(request))

    assert caught.value.code == (
        "workflow_target_context_capsule_lifecycle_status_attestor_unavailable"
    )
    rendered_error = f"{caught.value} {caught.value.detail}"
    for sensitive_value in (
        request.opening_result_id,
        request.consumer_binding_id,
        request.sealed_capsule_id,
        request.consumer_subject_id,
        request.request_nonce_digest,
        request.scope.organization_id,
        request.scope.environment_id,
    ):
        assert sensitive_value not in rendered_error


def test_capsule_lifecycle_signature_verifier_always_denies() -> None:
    verifier = DenyAllWorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier()

    assert verifier.verify_capsule_lifecycle_attestation(cast(Any, None)) is False
