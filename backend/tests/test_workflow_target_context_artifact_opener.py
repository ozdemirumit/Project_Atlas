from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters import (
    SyntheticWorkflowPhysicalTransportTargetContextArtifactOpener,
    UnavailableWorkflowPhysicalTransportTargetContextArtifactOpener,
)
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy,
)

NOW = datetime(2026, 8, 15, 12, 0, 2, tzinfo=UTC)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")


def _payload(values: dict[str, object]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value.canonical_value()
            if hasattr(value, "canonical_value")
            else value
        )
        for name, value in values.items()
    }


def instruction() -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction:
    policy = code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy()
    values: dict[str, object] = {
        "opening_id": "workflow-target-context-artifact-opening.imp-210",
        "attempt_id": "workflow-target-context-artifact-opening-attempt.imp-210",
        "consumption_claim_id": "workflow-target-context-access-consumption-claim.imp-210",
        "authorization_lease_id": "workflow-target-context-access-lease.imp-210",
        "authorization_lease_digest": "1" * 64,
        "target_context_binding_id": "workflow-target-context-binding.imp-210",
        "target_context_binding_digest": "2" * 64,
        "target_context_commitment": "3" * 64,
        "endpoint_materialization_id": "endpoint-materialization.imp-210",
        "endpoint_materialization_digest": "4" * 64,
        "endpoint_protected_artifact_id": "protected-endpoint-artifact.imp-210",
        "endpoint_protected_artifact_digest": "5" * 64,
        "endpoint_status_attestation_digest": "6" * 64,
        "credential_materialization_id": "credential-materialization.imp-210",
        "credential_materialization_digest": "7" * 64,
        "credential_protected_artifact_id": "protected-credential-artifact.imp-210",
        "credential_protected_artifact_digest": "8" * 64,
        "credential_status_attestation_digest": "9" * 64,
        "scope": SCOPE,
        "accessor_subject_id": WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "opener_contract_id": policy.required_opener_contract_id,
        "opener_attestor_id": policy.required_opener_attestor_id,
        "capsule_schema_id": policy.capsule_schema_id,
        "capsule_schema_version": policy.capsule_schema_version,
        "started_at": NOW,
        "lease_valid_until": NOW + timedelta(seconds=4),
        "joint_usable_until": NOW + timedelta(seconds=20),
        "evidence_valid_until": NOW + timedelta(seconds=10),
    }
    return WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


@pytest.mark.asyncio
async def test_synthetic_opener_emits_signed_opaque_lineage_without_raw_material() -> None:
    opener = SyntheticWorkflowPhysicalTransportTargetContextArtifactOpener(
        clock=lambda: NOW + timedelta(milliseconds=100)
    )

    receipt = await opener.open_paired_artifacts(instruction())

    assert receipt.state is (
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState.OPENED_PROTECTED
    )
    assert receipt.sealed_capsule_id is not None
    assert receipt.sealed_capsule_digest is not None
    assert receipt.capsule_is_bearer_capability is False
    assert receipt.endpoint_opened is True and receipt.credential_opened is True
    assert receipt.pair_commitment_verified is True
    assert receipt.raw_endpoint_returned is False
    assert receipt.raw_credential_returned is False
    assert receipt.network_activity_performed is False
    assert receipt.delivery_performed is False
    assert receipt.runtime_use_performed is False
    assert opener.verify_receipt(receipt) is True
    assert await opener.destroy_capsule(receipt) is True
    assert opener.destroyed_capsule_digests == [receipt.sealed_capsule_digest]


@pytest.mark.asyncio
async def test_synthetic_opener_rejects_tampering_and_never_contains_raw_fields() -> None:
    opener = SyntheticWorkflowPhysicalTransportTargetContextArtifactOpener(
        clock=lambda: NOW + timedelta(milliseconds=100)
    )
    receipt = await opener.open_paired_artifacts(instruction())

    tampered_values = {
        field.name: getattr(receipt, field.name)
        for field in fields(type(receipt))
        if field.name != "canonical_digest"
    }
    tampered_values["integrity_signature"] = "0" * 64
    tampered = WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt(
        **cast(Any, tampered_values),
        canonical_digest=canonical_digest(_payload(tampered_values)),
    )
    assert opener.verify_receipt(tampered) is False
    assert (
        not {
            "endpoint",
            "hostname",
            "url",
            "ip_address",
            "port",
            "username",
            "password",
            "token",
            "private_key",
            "secret",
            "provider_payload",
            "runtime_handle",
        }
        & receipt.digest_payload().keys()
    )


@pytest.mark.asyncio
async def test_unavailable_opener_fails_closed() -> None:
    opener = UnavailableWorkflowPhysicalTransportTargetContextArtifactOpener()

    assert opener.available is False
    with pytest.raises(
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningError,
        match="trusted_opener_unavailable",
    ):
        await opener.open_paired_artifacts(instruction())
