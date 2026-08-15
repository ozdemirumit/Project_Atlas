from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters.credential_materialization_synthetic import (
    SyntheticWorkflowPhysicalTransportCredentialMaterializer,
)
from atlas.modules.workflows.adapters.credential_materialization_unavailable import (
    UnavailableWorkflowPhysicalTransportCredentialMaterializer,
)
from atlas.modules.workflows.application.credential_access_authorization_leases import (
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
)
from atlas.modules.workflows.application.credential_materialization_ports import (
    WorkflowEventPhysicalTransportCredentialMaterializationError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportCredentialMaterializationFailureClass,
    WorkflowEventPhysicalTransportCredentialMaterializationInstruction,
    WorkflowEventPhysicalTransportCredentialMaterializationReceipt,
    WorkflowEventPhysicalTransportCredentialMaterializationResultState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_materialization_policy,
)

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _canonical_payload(values: dict[str, Any]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value.canonical_value()
            if isinstance(value, WorkflowScope)
            else value
        )
        for name, value in values.items()
    }


def _instruction(
    **changes: Any,
) -> WorkflowEventPhysicalTransportCredentialMaterializationInstruction:
    policy = code_owned_workflow_event_physical_transport_credential_materialization_policy()

    def digest(character: str) -> str:
        return character * 64

    values: dict[str, Any] = {
        "materialization_id": "credential-materialization.test",
        "attempt_id": "credential-materialization-attempt.test",
        "consumption_claim_id": "credential-consumption-claim.test",
        "authorization_lease_id": "credential-access-lease.test",
        "authorization_lease_digest": digest("1"),
        "credential_assignment_snapshot_id": "credential-assignment-snapshot.test",
        "credential_assignment_snapshot_digest": digest("2"),
        "assignment_id": "credential-assignment.test",
        "assignment_revision": "7",
        "source_assignment_digest": digest("3"),
        "credential_requirement_profile_id": "credential-requirement-profile.test",
        "credential_requirement_profile_version": "1.0",
        "credential_requirement_profile_digest": digest("4"),
        "credential_profile_id": "credential-profile.test",
        "credential_profile_version": "1.0",
        "credential_profile_digest": digest("5"),
        "authentication_mechanism_class": "token",
        "principal_class": "service-account",
        "privilege_class": "read-only",
        "target_scope_commitment": digest("6"),
        "credential_generation": 3,
        "rotation_epoch": 5,
        "broker_policy_id": "broker-policy.test",
        "broker_policy_version": "1.0",
        "broker_policy_digest": digest("7"),
        "scope": WorkflowScope("organization.test", "environment.test", "site.test"),
        "accessor_subject_id": WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
        "materializer_contract_id": policy.required_materializer_contract_id,
        "materializer_attestor_id": policy.required_materializer_attestor_id,
        "protected_artifact_schema_id": policy.protected_artifact_schema_id,
        "protected_artifact_schema_version": policy.protected_artifact_schema_version,
        "protected_artifact_profile_digest": policy.protected_artifact_profile_digest,
        "lease_valid_until": NOW + timedelta(seconds=15),
    }
    values.update(changes)
    return WorkflowEventPhysicalTransportCredentialMaterializationInstruction(
        **cast(Any, values),
        canonical_digest=canonical_digest(_canonical_payload(values)),
    )


@pytest.mark.asyncio
async def test_synthetic_materializer_returns_deterministic_minimized_metadata() -> None:
    adapter = SyntheticWorkflowPhysicalTransportCredentialMaterializer(clock=lambda: NOW)
    instruction = _instruction()

    first = await adapter.materialize(instruction)
    second = await adapter.materialize(instruction)

    assert first == second
    assert first.state is (
        WorkflowEventPhysicalTransportCredentialMaterializationResultState.MATERIALIZED_PROTECTED
    )
    assert first.protected_artifact_id is not None
    assert first.protected_artifact_digest is not None
    assert first.usable_until == instruction.lease_valid_until
    assert first.source_assignment_digest == instruction.source_assignment_digest
    assert first.credential_generation == instruction.credential_generation
    assert first.rotation_epoch == instruction.rotation_epoch
    assert first.signature_verified is True
    assert first.raw_credential_returned is False
    assert first.secret_locator_returned is False
    assert first.provider_payload_returned is False
    assert first.network_activity_performed is False
    assert first.process_activity_performed is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "replacement"),
    (
        ("accessor_subject_id", "service.other"),
        ("materializer_contract_id", "contract.other"),
        ("materializer_attestor_id", "attestor.other"),
        ("protected_artifact_schema_id", "schema.other"),
        ("protected_artifact_schema_version", "2.0"),
        ("protected_artifact_profile_digest", "8" * 64),
    ),
)
async def test_synthetic_materializer_rejects_changed_instruction_commitments(
    field_name: str, replacement: str
) -> None:
    adapter = SyntheticWorkflowPhysicalTransportCredentialMaterializer(clock=lambda: NOW)

    with pytest.raises(
        WorkflowEventPhysicalTransportCredentialMaterializationError,
        match="instruction_commitment_mismatch",
    ):
        await adapter.materialize(_instruction(**{field_name: replacement}))


@pytest.mark.asyncio
async def test_synthetic_materializer_rejects_tampered_instruction_digest() -> None:
    adapter = SyntheticWorkflowPhysicalTransportCredentialMaterializer(clock=lambda: NOW)
    instruction = _instruction()
    object.__setattr__(instruction, "source_assignment_digest", "9" * 64)

    with pytest.raises(
        WorkflowEventPhysicalTransportCredentialMaterializationError,
        match="instruction_commitment_mismatch",
    ):
        await adapter.materialize(instruction)


@pytest.mark.asyncio
async def test_deadline_expiry_returns_cleaned_failure_without_artifact() -> None:
    instruction = _instruction()
    adapter = SyntheticWorkflowPhysicalTransportCredentialMaterializer(
        clock=lambda: instruction.lease_valid_until
    )

    receipt = await adapter.materialize(instruction)

    assert receipt.state is (
        WorkflowEventPhysicalTransportCredentialMaterializationResultState.MATERIALIZATION_FAILED
    )
    assert (
        receipt.failure_class
        is WorkflowEventPhysicalTransportCredentialMaterializationFailureClass.DEADLINE_EXPIRED
    )
    assert receipt.protected_artifact_id is None
    assert receipt.protected_artifact_digest is None
    assert receipt.protected_artifact_revoked is True
    assert receipt.cleanup_confirmed is True


@pytest.mark.asyncio
async def test_revoke_tracks_only_minimized_receipt_digest_and_rejects_tamper() -> None:
    adapter = SyntheticWorkflowPhysicalTransportCredentialMaterializer(clock=lambda: NOW)
    receipt = await adapter.materialize(_instruction())

    assert await adapter.revoke_or_destroy(receipt) is True
    assert adapter.revoked_receipt_digests == [receipt.canonical_digest]

    object.__setattr__(receipt, "source_assignment_digest", "9" * 64)
    assert await adapter.revoke_or_destroy(receipt) is False
    assert adapter.revoked_receipt_digests == [receipt.canonical_digest]


@pytest.mark.asyncio
async def test_unavailable_materializer_fails_closed_for_materialize_and_cleanup() -> None:
    adapter = UnavailableWorkflowPhysicalTransportCredentialMaterializer()
    instruction = _instruction()
    synthetic = SyntheticWorkflowPhysicalTransportCredentialMaterializer(clock=lambda: NOW)
    receipt = await synthetic.materialize(instruction)

    assert adapter.available is False
    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationError):
        await adapter.materialize(instruction)
    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationError):
        await adapter.revoke_or_destroy(receipt)


def test_adapter_contract_has_no_secret_material_fields() -> None:
    forbidden = {
        "password",
        "private_key",
        "raw_credential",
        "secret",
        "secret_locator",
        "token",
        "vault_path",
    }
    receipt_fields = {
        field.name
        for field in fields(WorkflowEventPhysicalTransportCredentialMaterializationReceipt)
    }
    adapter_fields = set(
        SyntheticWorkflowPhysicalTransportCredentialMaterializer(clock=lambda: NOW).__dict__
    )

    assert not forbidden & receipt_fields
    assert not forbidden & adapter_fields
