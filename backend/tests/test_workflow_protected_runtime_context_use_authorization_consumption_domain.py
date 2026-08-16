from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_consumption_domain import (  # noqa: E501
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionState,
    code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_domain import (
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseState,
)

NOW = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.test", "environment.test", "site.test")


def _canonical_mapping(values: dict[str, object]) -> dict[str, object]:
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


def _claim(**changes: object) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim:
    policy = code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy()
    values: dict[str, object] = {
        "consumption_claim_id": "use-authorization-consumption-claim.imp-221",
        "consumption_id": "use-authorization-consumption.imp-221",
        "authorization_lease_id": "use-authorization-lease.imp-220",
        "authorization_lease_digest": "1" * 64,
        "authorization_claim_id": "use-authorization-claim.imp-220",
        "authorization_claim_digest": "2" * 64,
        "injection_result_id": "injection-result.imp-219",
        "injection_result_digest": "3" * 64,
        "destination_deployment_id": "deployment.imp-221",
        "destination_generation": 7,
        "destination_fencing_token_digest": "4" * 64,
        "runtime_slot_commitment": "5" * 64,
        "runtime_slot_post_generation": 11,
        "injected_context_usable_until": NOW + timedelta(milliseconds=800),
        "use_profile_id": "profile.workflow-protected-runtime-context-use",
        "use_profile_version": "1.0",
        "use_profile_digest": "6" * 64,
        "source_lease_state": (
            WorkflowProtectedRuntimeContextUseAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        "source_lease_issued_at": NOW - timedelta(milliseconds=100),
        "source_lease_valid_until": NOW + timedelta(milliseconds=700),
        "source_lease_effective_until": NOW + timedelta(milliseconds=700),
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "source_policy_id": policy.source_policy_id,
        "source_policy_version": policy.source_policy_version,
        "source_policy_digest": policy.source_policy_digest,
        "idempotency_digest": "7" * 64,
        "request_fingerprint": "8" * 64,
        "irreversible_consumption_acknowledged": True,
        "consumption_audit_digest": "9" * 64,
        "claimed_at": NOW,
        "authority": (WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority()),
    }
    values.update(changes)
    return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim(
        **cast(Any, values),
        canonical_digest=canonical_digest(_canonical_mapping(values)),
    )


def _result(
    claim: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim | None = None,
    **changes: object,
) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult:
    claim = claim or _claim()
    values: dict[str, object] = {
        "result_id": "use-authorization-consumption-result.imp-221",
        "consumption_id": claim.consumption_id,
        "consumption_claim_id": claim.consumption_claim_id,
        "consumption_claim_digest": claim.canonical_digest,
        "authorization_lease_id": claim.authorization_lease_id,
        "authorization_lease_digest": claim.authorization_lease_digest,
        "scope": claim.scope,
        "consumer_subject_id": claim.consumer_subject_id,
        "consumer_audience": claim.consumer_audience,
        "consumer_contract_id": claim.consumer_contract_id,
        "consumer_contract_version": claim.consumer_contract_version,
        "purpose_id": claim.purpose_id,
        "policy_id": claim.policy_id,
        "policy_version": claim.policy_version,
        "policy_digest": claim.policy_digest,
        "source_policy_id": claim.source_policy_id,
        "source_policy_version": claim.source_policy_version,
        "source_policy_digest": claim.source_policy_digest,
        "state": (
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionState.AUTHORIZATION_CONSUMED_WITHOUT_RUNTIME_USE
        ),
        "consumed_at": claim.claimed_at,
        "recorded_at": claim.claimed_at,
        "authorization_lease_consumed": True,
        "historical_result_only": True,
        "context_accessed": False,
        "context_used": False,
        "runtime_started": False,
        "runtime_resumed": False,
        "network_activity_performed": False,
        "connector_activity_performed": False,
        "readiness_probe_performed": False,
        "publication_performed": False,
        "delivery_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
        "renewal_created": False,
        "transfer_created": False,
        "replacement_created": False,
        "retry_created": False,
        "authority": (WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority()),
    }
    values.update(changes)
    return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult(
        **cast(Any, values),
        canonical_digest=canonical_digest(_canonical_mapping(values)),
    )


def test_policy_is_code_owned_and_forbids_external_or_operational_work() -> None:
    policy = code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy()

    assert policy.durable_replay_required is True
    assert policy.atomic_claim_and_result_required is True
    assert policy.external_io_forbidden is True
    assert policy.context_access_forbidden is True
    assert policy.context_use_forbidden is True
    assert policy.runtime_start_forbidden is True
    assert policy.runtime_resume_forbidden is True
    assert policy.network_activity_forbidden is True
    assert policy.connector_activity_forbidden is True
    assert policy.dispatch_forbidden is True
    assert policy.execution_forbidden is True
    assert policy.infrastructure_mutation_forbidden is True

    with pytest.raises(ValueError, match="not code-owned"):
        replace(policy, retry_forbidden=False)


def test_consumption_authority_requires_all_twenty_six_fields_false() -> None:
    authority = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority()

    assert len(authority.canonical_value()) == 26
    assert not any(authority.canonical_value().values())
    with pytest.raises(ValueError, match="cannot grant authority"):
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority(
            protected_runtime_context_use_authority_granted=True
        )
    with pytest.raises(ValueError, match="cannot grant authority"):
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority(
            execution_authorized=True
        )


def test_claim_is_immutable_exact_lineage_and_excludes_lease_deadline() -> None:
    claim = _claim()

    assert claim.source_lease_state.value == "authorized_unconsumed"
    assert claim.irreversible_consumption_acknowledged is True
    assert not any(claim.authority.canonical_value().values())

    with pytest.raises(ValueError, match="claim is invalid"):
        _claim(claimed_at=claim.source_lease_valid_until)
    with pytest.raises(ValueError, match="claim is invalid"):
        _claim(irreversible_consumption_acknowledged=False)
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(claim, canonical_digest="f" * 64)


@pytest.mark.parametrize(
    "field",
    [
        "context_accessed",
        "context_used",
        "runtime_started",
        "runtime_resumed",
        "network_activity_performed",
        "connector_activity_performed",
        "readiness_probe_performed",
        "publication_performed",
        "delivery_performed",
        "dispatch_performed",
        "execution_performed",
        "infrastructure_mutation_performed",
        "renewal_created",
        "transfer_created",
        "replacement_created",
        "retry_created",
    ],
)
def test_terminal_result_rejects_every_operational_or_reissue_effect(field: str) -> None:
    with pytest.raises(ValueError, match="result is invalid"):
        _result(None, **{field: True})


def test_terminal_result_is_historical_consumption_without_runtime_use() -> None:
    result = _result()

    assert result.state.value == "authorization_consumed_without_runtime_use"
    assert result.authorization_lease_consumed is True
    assert result.historical_result_only is True
    assert not any(result.authority.canonical_value().values())
    assert result.context_accessed is False
    assert result.context_used is False
    assert result.runtime_started is False
    assert result.execution_performed is False
    assert result.infrastructure_mutation_performed is False

    with pytest.raises(ValueError, match="result is invalid"):
        _result(historical_result_only=False)
    with pytest.raises(ValueError, match="result is invalid"):
        _result(recorded_at=NOW - timedelta(microseconds=1))
