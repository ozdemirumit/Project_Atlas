from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import SimpleNamespace
from typing import Any, cast

import pytest

from atlas.modules.workflows import domain

_REQUIRED_DOMAIN_NAMES = (
    "WorkflowProtectedResidentContextAccessConsumptionFailureClass",
    "WorkflowProtectedResidentContextAccessConsumptionPolicy",
    "WorkflowProtectedResidentContextAccessConsumptionResultState",
    "WorkflowProtectedResidentContextTrustedAccessorInstruction",
    "WorkflowProtectedResidentContextTrustedAccessorReceipt",
    "code_owned_workflow_protected_resident_context_access_consumption_policy",
)
if not all(hasattr(domain, name) for name in _REQUIRED_DOMAIN_NAMES):
    pytest.skip("IMP-217 domain slice is merged separately", allow_module_level=True)

from atlas.modules.workflows.adapters import (  # noqa: E402
    protected_resident_context_accessors as adapters,
)
from atlas.modules.workflows.application.protected_resident_context_access_consumption_ports import (  # noqa: E402, E501
    WorkflowProtectedResidentContextAccessConsumptionError,
    WorkflowProtectedResidentContextAccessorReadinessAttestationRequest,
)
from atlas.modules.workflows.domain import WorkflowScope, canonical_digest  # noqa: E402

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


class _State(StrEnum):
    HANDLE_ESTABLISHED_IN_PROTECTED_BOUNDARY = "handle_established_in_protected_boundary"
    RESIDENT_CONTEXT_ACCESS_FAILED = "resident_context_access_failed"


@dataclass(frozen=True, slots=True)
class _Instruction:
    access_id: str
    attempt_id: str
    consumption_claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_resident_context_id: str
    protected_resident_context_digest: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    accessor_contract_id: str
    accessor_contract_version: str
    accessor_id: str
    accessor_version: str
    runtime_handle_profile_id: str
    runtime_handle_profile_version: str
    runtime_handle_profile_digest: str
    started_at: datetime
    access_deadline: datetime
    protected_resident_context_usable_until: datetime
    canonical_digest: str

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class _Receipt:
    access_id: str
    attempt_id: str
    consumption_claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_resident_context_id: str
    protected_resident_context_digest: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    accessor_contract_id: str
    accessor_contract_version: str
    accessor_id: str
    accessor_version: str
    runtime_handle_profile_id: str
    runtime_handle_profile_version: str
    runtime_handle_profile_digest: str
    access_deadline: datetime
    protected_resident_context_usable_until: datetime
    instruction_digest: str
    state: _State
    failure_class: object | None
    protected_runtime_handle_id: str | None
    protected_runtime_handle_digest: str | None
    protected_runtime_handle_created_at: datetime | None
    protected_runtime_handle_usable_until: datetime | None
    protected_resident_context_consumed: bool
    runtime_handle_established_in_protected_boundary: bool
    protected_runtime_handle_is_bearer_capability: bool
    runtime_handle_absence_confirmed: bool
    raw_context_returned: bool
    runtime_handle_locator_returned: bool
    endpoint_returned: bool
    credential_returned: bool
    secret_returned: bool
    bearer_token_returned: bool
    provider_payload_returned: bool
    network_activity_performed: bool
    delivery_performed: bool
    execution_performed: bool
    infrastructure_mutation_performed: bool
    completed_at: datetime
    attested_by: str
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def signature_payload(self) -> dict[str, object]:
        return {
            name: value
            for name, value in self.digest_payload().items()
            if name != "integrity_signature"
        }

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def _policy() -> Any:
    return SimpleNamespace(
        required_readiness_attestor_id="attestor.readiness",
        required_readiness_attestor_version="1.0",
        verification_signing_key_id="key.test",
        required_accessor_contract_id="contract.accessor",
        required_accessor_contract_version="1.0",
        approved_accessor_id="accessor.test",
        approved_accessor_version="1.0",
        runtime_handle_profile_id="profile.handle",
        runtime_handle_profile_version="1.0",
        runtime_handle_profile_digest="a" * 64,
    )


def _instruction() -> _Instruction:
    values: dict[str, object] = {
        "access_id": "consumption.test",
        "attempt_id": "attempt.test",
        "consumption_claim_id": "claim.test",
        "authorization_lease_id": "lease.test",
        "authorization_lease_digest": "b" * 64,
        "protected_resident_context_id": "resident.test",
        "protected_resident_context_digest": "c" * 64,
        "destination_boundary_id": "boundary.test",
        "destination_deployment_id": "deployment.test",
        "destination_generation": 1,
        "destination_fencing_token_digest": "d" * 64,
        "accessor_contract_id": "contract.accessor",
        "accessor_contract_version": "1.0",
        "accessor_id": "accessor.test",
        "accessor_version": "1.0",
        "runtime_handle_profile_id": "profile.handle",
        "runtime_handle_profile_version": "1.0",
        "runtime_handle_profile_digest": "a" * 64,
        "started_at": NOW,
        "access_deadline": NOW + timedelta(seconds=1),
        "protected_resident_context_usable_until": NOW + timedelta(milliseconds=900),
    }
    return _Instruction(
        **values,  # type: ignore[arg-type]
        canonical_digest=canonical_digest(_payload_dict(values)),
    )


def test_unavailable_adapters_fail_closed_without_activity() -> None:
    readiness = adapters.UnavailableWorkflowProtectedResidentContextAccessorReadinessAttestor()
    accessor = adapters.UnavailableWorkflowProtectedResidentContextTrustedAccessor()
    assert readiness.available is False
    assert accessor.available is False
    assert accessor.verify_receipt(object()) is False  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_development_readiness_attestation_is_signed_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapters, "_policy", _policy)
    attestor = (
        adapters.DeterministicDevelopmentWorkflowProtectedResidentContextAccessorReadinessAttestor(
            development_enabled=True, clock=lambda: NOW
        )
    )
    request = WorkflowProtectedResidentContextAccessorReadinessAttestationRequest(
        authorization_lease_id="lease.test",
        authorization_lease_digest="b" * 64,
        protected_resident_context_id="resident.test",
        protected_resident_context_digest="c" * 64,
        protected_resident_context_usable_until=NOW + timedelta(seconds=1),
        destination_boundary_id="boundary.test",
        destination_deployment_id="deployment.test",
        destination_generation=1,
        destination_fencing_token_digest="d" * 64,
        scope=WorkflowScope("organization.test", "environment.test", "site.test"),
        consumer_subject_id="service.consumer",
        consumer_audience="audience.consumer",
        consumer_contract_id="contract.consumer",
        consumer_contract_version="1.0",
        accessor_contract_id="contract.accessor",
        accessor_contract_version="1.0",
        accessor_id="accessor.test",
        accessor_version="1.0",
        runtime_handle_profile_id="profile.handle",
        runtime_handle_profile_version="1.0",
        runtime_handle_profile_digest="a" * 64,
        request_nonce_digest="e" * 64,
        requested_at=NOW,
    )

    evidence = await attestor.attest_accessor_readiness(request)

    assert attestor.verify_accessor_readiness_attestation(evidence) is True
    assert evidence.raw_context_included is False
    assert evidence.runtime_handle_locator_included is False
    assert evidence.endpoint_included is False
    assert evidence.credential_included is False
    assert evidence.provider_payload_included is False


@pytest.mark.asyncio
async def test_development_accessor_enforces_single_atomic_cas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapters, "_policy", _policy)
    monkeypatch.setattr(
        adapters, "WorkflowProtectedResidentContextTrustedAccessorReceipt", _Receipt
    )
    monkeypatch.setattr(
        adapters, "WorkflowProtectedResidentContextAccessConsumptionResultState", _State
    )
    accessor = adapters.DeterministicDevelopmentWorkflowProtectedResidentContextTrustedAccessor(
        development_enabled=True,
        clock=lambda: NOW + timedelta(milliseconds=100),
    )
    instruction = _instruction()

    receipt = await accessor.establish_access(instruction)  # type: ignore[arg-type]

    assert accessor.verify_receipt(receipt) is True
    assert receipt.protected_resident_context_consumed is True
    assert receipt.runtime_handle_established_in_protected_boundary is True
    assert receipt.protected_runtime_handle_is_bearer_capability is False
    assert receipt.runtime_handle_locator_returned is False
    assert receipt.raw_context_returned is False
    assert receipt.network_activity_performed is False
    with pytest.raises(WorkflowProtectedResidentContextAccessConsumptionError):
        await accessor.establish_access(instruction)  # type: ignore[arg-type]
    assert len(accessor.calls) == 1


@pytest.mark.asyncio
async def test_development_accessor_requires_explicit_enablement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapters, "_policy", _policy)
    accessor = adapters.DeterministicDevelopmentWorkflowProtectedResidentContextTrustedAccessor(
        development_enabled=False, clock=lambda: NOW
    )
    with pytest.raises(WorkflowProtectedResidentContextAccessConsumptionError):
        await accessor.establish_access(_instruction())  # type: ignore[arg-type]


def _payload(value: object, *, exclude: tuple[str, ...]) -> dict[str, object]:
    return _payload_dict(
        {
            field.name: getattr(value, field.name)
            for field in fields(cast(Any, value))
            if field.name not in exclude
        }
    )


def _payload_dict(values: dict[str, object]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if hasattr(value, "value")
            else value.canonical_value()
            if hasattr(value, "canonical_value")
            else value
        )
        for name, value in values.items()
    }
