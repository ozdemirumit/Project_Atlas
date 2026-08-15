from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest
from test_workflow_credential_access_authorization_leases import (
    LEASE_NOW,
    accessor_context,
    authorize,
)
from test_workflow_credential_access_authorization_leases import (
    service_fixture as authorization_service_fixture,
)
from test_workflow_route_freshness_admissions import CollectingAuditSink

from atlas.modules.workflows.application import (
    WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest,
    WorkflowEventPhysicalTransportCredentialMaterializationClaimResult,
    WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus,
    WorkflowEventPhysicalTransportCredentialMaterializationError,
    WorkflowEventPhysicalTransportCredentialMaterializationResultRequest,
    WorkflowEventPhysicalTransportCredentialMaterializationResultStatus,
    WorkflowEventPhysicalTransportCredentialMaterializationResultWrite,
    WorkflowEventPhysicalTransportCredentialMaterializationService,
    WorkflowEventPhysicalTransportCredentialMaterializationUncertainError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportCredentialMaterializationAttempt,
    WorkflowEventPhysicalTransportCredentialMaterializationAttemptState,
    WorkflowEventPhysicalTransportCredentialMaterializationAuthority,
    WorkflowEventPhysicalTransportCredentialMaterializationFailureClass,
    WorkflowEventPhysicalTransportCredentialMaterializationInstruction,
    WorkflowEventPhysicalTransportCredentialMaterializationPolicy,
    WorkflowEventPhysicalTransportCredentialMaterializationReceipt,
    WorkflowEventPhysicalTransportCredentialMaterializationResult,
    WorkflowEventPhysicalTransportCredentialMaterializationResultState,
    WorkflowScope,
    canonical_digest,
)

MATERIALIZATION_NOW = LEASE_NOW + timedelta(seconds=1)


def _payload(values: dict[str, Any]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in values.items():
        if isinstance(value, datetime):
            result[name] = value.isoformat()
        elif isinstance(value, StrEnum):
            result[name] = value.value
        elif hasattr(value, "canonical_value"):
            result[name] = value.canonical_value()
        else:
            result[name] = value
    return result


class SelectiveAuditSink(CollectingAuditSink):
    def __init__(self, *, fail_suffix: str) -> None:
        super().__init__()
        self.fail_suffix = fail_suffix

    async def record(self, event: Any) -> None:
        if event.event_type.endswith(self.fail_suffix):
            raise RuntimeError("audit unavailable")
        await super().record(event)


class InMemoryCredentialMaterializationRepository:
    def __init__(self, *, source: Any, lease: Any) -> None:
        self.admission = source.admission
        self.binding = source.binding
        self.snapshot = source.snapshot
        self.head = source.head
        self.lease = lease
        self.now = MATERIALIZATION_NOW
        self.claims: dict[
            str, WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim
        ] = {}
        self.attempts: dict[
            str, WorkflowEventPhysicalTransportCredentialMaterializationAttempt
        ] = {}
        self.results: dict[str, WorkflowEventPhysicalTransportCredentialMaterializationResult] = {}
        self.adapter_call_observed_claim = False
        self.force_result_conflict = False

    @property
    def durable(self) -> bool:
        return True

    async def get_authoritative_time(self) -> datetime:
        return self.now

    async def get_credential_access_authorization_lease_by_id(
        self, *, authorization_lease_id: str
    ) -> Any:
        return self.lease if self.lease.authorization_lease_id == authorization_lease_id else None

    async def get_credential_assignment_freshness_admission_by_id(
        self, *, freshness_admission_id: str
    ) -> Any:
        return (
            self.admission
            if self.admission.freshness_admission_id == freshness_admission_id
            else None
        )

    async def get_credential_assignment_binding_by_id(self, *, binding_id: str) -> Any:
        return self.binding if self.binding.binding_id == binding_id else None

    async def get_credential_assignment_snapshot_by_id(self, *, snapshot_id: str) -> Any:
        return self.snapshot if self.snapshot.snapshot_id == snapshot_id else None

    async def get_current_credential_assignment_head(self, *, assignment_id: str) -> Any:
        return self.head if self.head.assignment_id == assignment_id else None

    async def get_credential_materialization_claim_by_lease(
        self, *, authorization_lease_id: str
    ) -> Any:
        return self.claims.get(authorization_lease_id)

    async def get_credential_materialization_attempt_by_lease(
        self, *, authorization_lease_id: str
    ) -> Any:
        return self.attempts.get(authorization_lease_id)

    async def list_credential_materialization_attempts(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportCredentialMaterializationAttempt, ...]:
        return tuple(value for value in self.attempts.values() if value.scope == scope)[:limit]

    async def get_credential_materialization_result_by_lease(
        self, *, authorization_lease_id: str
    ) -> Any:
        return self.results.get(authorization_lease_id)

    async def claim_credential_materialization(
        self, request: WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationClaimResult:
        prior = self.claims.get(request.authorization_lease_id)
        if prior is not None:
            if prior.request_fingerprint != request.request_fingerprint:
                return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
                    WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus.IDEMPOTENCY_CONFLICT,
                    prior,
                    self.attempts[request.authorization_lease_id],
                    self.results.get(request.authorization_lease_id),
                )
            result = self.results.get(request.authorization_lease_id)
            return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
                (
                    WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus.REPLAY_COMPLETED
                    if result is not None
                    else (
                        WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus
                    ).CLAIM_ONLY_UNCERTAIN
                ),
                prior,
                self.attempts[request.authorization_lease_id],
                result,
            )
        expected = (
            request.expected_freshness_admission_id,
            request.expected_freshness_admission_digest,
            request.expected_freshness_valid_until,
            request.expected_credential_assignment_binding_id,
            request.expected_credential_assignment_binding_digest,
            request.expected_credential_assignment_snapshot_id,
            request.expected_credential_assignment_snapshot_digest,
            request.expected_assignment_id,
            request.expected_assignment_revision,
            request.expected_source_assignment_digest,
            request.expected_credential_generation,
            request.expected_rotation_epoch,
            request.expected_assignment_activated_at,
            request.expected_assignment_expires_at,
            request.expected_assignment_active,
            request.expected_assignment_revoked,
        )
        actual = (
            self.admission.freshness_admission_id,
            self.admission.canonical_digest,
            self.admission.valid_until,
            self.binding.binding_id,
            self.binding.canonical_digest,
            self.snapshot.snapshot_id,
            self.snapshot.canonical_digest,
            self.head.assignment_id,
            self.head.assignment_revision,
            self.head.canonical_digest,
            self.head.credential_generation,
            self.head.rotation_epoch,
            self.head.activated_at,
            self.head.expires_at,
            self.head.active,
            self.head.revoked,
        )
        if (
            expected != actual
            or not self.lease.issued_at <= self.now < self.lease.valid_until
            or not self.admission.evaluated_at <= self.now < self.admission.valid_until
        ):
            return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
                WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus.EVIDENCE_CONFLICT,
                None,
                None,
                None,
            )
        try:
            await request.required_precommit_audit()
        except Exception:
            return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
                WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus.PRECOMMIT_AUDIT_FAILED,
                None,
                None,
                None,
            )
        authority = WorkflowEventPhysicalTransportCredentialMaterializationAuthority()
        claim_values: dict[str, Any] = {
            "claim_id": request.claim_id,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "freshness_admission_id": request.expected_freshness_admission_id,
            "freshness_admission_digest": request.expected_freshness_admission_digest,
            "attempt_id": request.attempt_id,
            "materialization_id": request.materialization_id,
            "scope": request.scope,
            "accessor_subject_id": request.accessor_subject_id,
            "claimed_at": self.now,
            "request_fingerprint": request.request_fingerprint,
            "idempotency_digest": request.idempotency_digest,
            "authority": authority,
        }
        claim = WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim(
            **cast(Any, claim_values), canonical_digest=canonical_digest(_payload(claim_values))
        )
        attempt_values: dict[str, Any] = {
            "attempt_id": request.attempt_id,
            "materialization_id": request.materialization_id,
            "consumption_claim_id": request.claim_id,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "freshness_admission_id": request.expected_freshness_admission_id,
            "freshness_admission_digest": request.expected_freshness_admission_digest,
            "physical_transport_credential_assignment_binding_id": (
                request.expected_credential_assignment_binding_id
            ),
            "physical_transport_credential_assignment_binding_digest": (
                request.expected_credential_assignment_binding_digest
            ),
            "credential_assignment_snapshot_id": request.expected_credential_assignment_snapshot_id,
            "credential_assignment_snapshot_digest": (
                request.expected_credential_assignment_snapshot_digest
            ),
            "assignment_id": request.expected_assignment_id,
            "assignment_revision": request.expected_assignment_revision,
            "source_assignment_digest": request.expected_source_assignment_digest,
            "credential_generation": request.expected_credential_generation,
            "rotation_epoch": request.expected_rotation_epoch,
            "scope": request.scope,
            "accessor_subject_id": request.accessor_subject_id,
            "policy_id": request.expected_materialization_policy_id,
            "policy_version": request.expected_materialization_policy_version,
            "policy_digest": request.expected_materialization_policy_digest,
            "started_at": self.now,
            "freshness_valid_until": request.expected_freshness_valid_until,
            "lease_valid_until": self.lease.valid_until,
            "state": (
                WorkflowEventPhysicalTransportCredentialMaterializationAttemptState
            ).MATERIALIZATION_STARTED,
            "authority": authority,
        }
        attempt = WorkflowEventPhysicalTransportCredentialMaterializationAttempt(
            **cast(Any, attempt_values), canonical_digest=canonical_digest(_payload(attempt_values))
        )
        self.claims[request.authorization_lease_id] = claim
        self.attempts[request.authorization_lease_id] = attempt
        return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
            WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus.CLAIMED,
            claim,
            attempt,
            None,
        )

    async def record_credential_materialization_result(
        self, request: WorkflowEventPhysicalTransportCredentialMaterializationResultRequest
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationResultWrite:
        if self.force_result_conflict:
            return WorkflowEventPhysicalTransportCredentialMaterializationResultWrite(
                WorkflowEventPhysicalTransportCredentialMaterializationResultStatus.CONFLICT,
                None,
            )
        prior = self.results.get(request.result.authorization_lease_id)
        if prior is not None:
            return WorkflowEventPhysicalTransportCredentialMaterializationResultWrite(
                WorkflowEventPhysicalTransportCredentialMaterializationResultStatus.REPLAY
                if prior == request.result
                else WorkflowEventPhysicalTransportCredentialMaterializationResultStatus.CONFLICT,
                prior,
            )
        claim = self.claims[request.result.authorization_lease_id]
        attempt = self.attempts[request.result.authorization_lease_id]
        if (
            claim.canonical_digest != request.expected_claim_digest
            or attempt.canonical_digest != request.expected_attempt_digest
        ):
            return WorkflowEventPhysicalTransportCredentialMaterializationResultWrite(
                WorkflowEventPhysicalTransportCredentialMaterializationResultStatus.CONFLICT,
                None,
            )
        self.results[request.result.authorization_lease_id] = request.result
        return WorkflowEventPhysicalTransportCredentialMaterializationResultWrite(
            WorkflowEventPhysicalTransportCredentialMaterializationResultStatus.RECORDED,
            request.result,
        )


class ObservingMaterializer:
    def __init__(self, repository: InMemoryCredentialMaterializationRepository) -> None:
        self.repository = repository
        self.calls: list[WorkflowEventPhysicalTransportCredentialMaterializationInstruction] = []
        self.failure_class: (
            WorkflowEventPhysicalTransportCredentialMaterializationFailureClass | None
        ) = None
        self.clock: Callable[[], datetime] = lambda: (
            MATERIALIZATION_NOW + timedelta(milliseconds=100)
        )
        self.materialized_at_delta = timedelta(milliseconds=10)
        self.usable_lifetime = timedelta(seconds=1)
        self.cleanup_calls = 0

    @property
    def available(self) -> bool:
        return True

    @property
    def materializer_contract_id(self) -> str:
        return "contract.workflow-physical-transport-credential-materializer.v1"

    async def materialize(
        self, instruction: WorkflowEventPhysicalTransportCredentialMaterializationInstruction
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationReceipt:
        self.repository.adapter_call_observed_claim = (
            instruction.authorization_lease_id in self.repository.claims
        )
        self.calls.append(instruction)
        completed_at = self.clock()
        success = self.failure_class is None
        values: dict[str, Any] = {
            "materialization_id": instruction.materialization_id,
            "attempt_id": instruction.attempt_id,
            "consumption_claim_id": instruction.consumption_claim_id,
            "instruction_digest": instruction.canonical_digest,
            "materializer_contract_id": instruction.materializer_contract_id,
            "materializer_id": "materializer.credential.test",
            "materializer_version": "1.0",
            "attested_by": instruction.materializer_attestor_id,
            "accessor_subject_id": instruction.accessor_subject_id,
            "state": (
                WorkflowEventPhysicalTransportCredentialMaterializationResultState.MATERIALIZED_PROTECTED
                if success
                else (
                    WorkflowEventPhysicalTransportCredentialMaterializationResultState
                ).MATERIALIZATION_FAILED
            ),
            "failure_class": self.failure_class,
            "protected_artifact_id": "protected-credential-artifact.test" if success else None,
            "protected_artifact_digest": "a" * 64 if success else None,
            "protected_artifact_schema_id": instruction.protected_artifact_schema_id,
            "protected_artifact_schema_version": instruction.protected_artifact_schema_version,
            "protected_artifact_profile_digest": instruction.protected_artifact_profile_digest,
            "source_assignment_digest": instruction.source_assignment_digest,
            "credential_generation": instruction.credential_generation,
            "rotation_epoch": instruction.rotation_epoch,
            "materialized_at": completed_at - self.materialized_at_delta if success else None,
            "completed_at": completed_at,
            "usable_until": completed_at + self.usable_lifetime if success else None,
            "source_commitment_verified": success,
            "encrypted_at_rest": success,
            "accessor_bound": success,
            "lineage_bound": success,
            "raw_credential_returned": False,
            "secret_locator_returned": False,
            "provider_payload_returned": False,
            "network_activity_performed": False,
            "process_activity_performed": False,
            "protected_artifact_revoked": not success,
            "cleanup_confirmed": True,
            "signature_verified": True,
        }
        return WorkflowEventPhysicalTransportCredentialMaterializationReceipt(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    async def revoke_or_destroy(
        self, receipt: WorkflowEventPhysicalTransportCredentialMaterializationReceipt
    ) -> bool:
        self.cleanup_calls += 1
        return True


class ExplodingMaterializer(ObservingMaterializer):
    async def materialize(
        self, instruction: WorkflowEventPhysicalTransportCredentialMaterializationInstruction
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationReceipt:
        self.repository.adapter_call_observed_claim = (
            instruction.authorization_lease_id in self.repository.claims
        )
        self.calls.append(instruction)
        raise RuntimeError("protected boundary lost")


async def fixture(
    *,
    materializer_type: type[ObservingMaterializer] = ObservingMaterializer,
    audit: CollectingAuditSink | None = None,
) -> tuple[
    WorkflowEventPhysicalTransportCredentialMaterializationService,
    InMemoryCredentialMaterializationRepository,
    ObservingMaterializer,
    CollectingAuditSink,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
]:
    authorization_service, authorization_repository, _ = await authorization_service_fixture()
    lease = await authorize(authorization_service, authorization_repository)
    repository = InMemoryCredentialMaterializationRepository(
        source=authorization_repository, lease=lease
    )
    materializer = materializer_type(repository)
    sink = audit or CollectingAuditSink()
    service = WorkflowEventPhysicalTransportCredentialMaterializationService(
        repository=cast(Any, repository),
        materializer=materializer,
        audit_sink=sink,
    )
    return service, repository, materializer, sink, lease


async def materialize(
    service: WorkflowEventPhysicalTransportCredentialMaterializationService,
    lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    **changes: Any,
) -> WorkflowEventPhysicalTransportCredentialMaterializationResult:
    values: dict[str, Any] = {
        "authorization_lease_id": lease.authorization_lease_id,
        "authorization_lease_digest": lease.canonical_digest,
        "materialization_policy_id": service.policy.policy_id,
        "materialization_policy_version": service.policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "credential-materialization-0001",
        "context": accessor_context(scope=lease.scope),
    }
    values.update(changes)
    return await service.materialize(**cast(Any, values))


@pytest.mark.asyncio
async def test_claims_before_materializer_and_records_minimized_success() -> None:
    service, repository, adapter, audit, lease = await fixture()

    result = await materialize(service, lease)

    assert repository.adapter_call_observed_claim is True
    assert len(adapter.calls) == 1
    assert (
        result.state
        is WorkflowEventPhysicalTransportCredentialMaterializationResultState.MATERIALIZED_PROTECTED
    )
    assert len(result.authority.canonical_value()) == 17
    assert all(value is False for value in result.authority.canonical_value().values())
    assert all(
        all(value is False for value in evidence.authority.canonical_value().values())
        for evidence in (
            repository.claims[lease.authorization_lease_id],
            repository.attempts[lease.authorization_lease_id],
            result,
        )
    )
    assert [record.event_type.rsplit(".", 1)[-1] for record in audit.records] == [
        "requested",
        "authorized",
        "completed",
    ]


@pytest.mark.asyncio
async def test_exact_replay_returns_result_and_claim_only_is_never_retried() -> None:
    service, _, adapter, _, lease = await fixture()
    first = await materialize(service, lease)
    assert await materialize(service, lease) == first
    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationError) as conflict:
        await materialize(
            service,
            lease,
            idempotency_key="credential-materialization-changed",
        )
    assert conflict.value.code.endswith("_idempotency_conflict")
    assert len(adapter.calls) == 1

    service2, repository2, adapter2, _, lease2 = await fixture(
        materializer_type=ExplodingMaterializer
    )
    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationUncertainError):
        await materialize(service2, lease2)
    assert lease2.authorization_lease_id in repository2.claims
    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationUncertainError):
        await materialize(service2, lease2)
    assert len(adapter2.calls) == 1


@pytest.mark.asyncio
async def test_known_failure_is_terminal_and_minimized() -> None:
    service, repository, adapter, _, lease = await fixture()
    adapter.failure_class = (
        WorkflowEventPhysicalTransportCredentialMaterializationFailureClass
    ).CREDENTIAL_SOURCE_INVALID

    result = await materialize(service, lease)

    assert (
        result.state
        is WorkflowEventPhysicalTransportCredentialMaterializationResultState.MATERIALIZATION_FAILED
    )
    assert result.protected_artifact_id is None
    assert result.protected_artifact_digest is None
    assert result.protected_artifact_revoked is True
    assert repository.results[lease.authorization_lease_id] == result


@pytest.mark.asyncio
async def test_wrong_identity_or_missing_ack_fails_before_claim() -> None:
    service, repository, _, _, lease = await fixture()
    for changes in (
        {"context": accessor_context(scope=lease.scope, subject_id="service.other")},
        {"context": accessor_context(scope=lease.scope, audience="audience.other")},
        {"irreversible_consumption_acknowledged": False},
        {"uncertain_outcome_requires_new_authorization_acknowledged": False},
    ):
        with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationError):
            await materialize(service, lease, **changes)
    assert repository.claims == {}


@pytest.mark.asyncio
async def test_late_receipt_is_cleaned_and_remains_uncertain() -> None:
    service, repository, adapter, _, lease = await fixture()
    adapter.clock = lambda: lease.valid_until

    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationUncertainError):
        await materialize(service, lease)

    assert lease.authorization_lease_id in repository.claims
    assert lease.authorization_lease_id not in repository.results
    assert adapter.cleanup_calls == 1


@pytest.mark.asyncio
async def test_audit_failure_respects_irreversible_boundary() -> None:
    requested = SelectiveAuditSink(fail_suffix=".requested")
    service, repository, _, _, lease = await fixture(audit=requested)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await materialize(service, lease)
    assert repository.claims == {}

    authorized = SelectiveAuditSink(fail_suffix=".authorized")
    service, repository, adapter, _, lease = await fixture(audit=authorized)
    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationError) as error:
        await materialize(service, lease)
    assert error.value.code.endswith("_precommit_audit_failed")
    assert lease.authorization_lease_id not in repository.claims
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_post_materialization_failures_cleanup_live_artifact() -> None:
    completed = SelectiveAuditSink(fail_suffix=".completed")
    service, repository, adapter, _, lease = await fixture(audit=completed)
    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationUncertainError):
        await materialize(service, lease)
    assert lease.authorization_lease_id in repository.claims
    assert lease.authorization_lease_id not in repository.results
    assert adapter.cleanup_calls == 1

    service, repository, adapter, _, lease = await fixture()
    repository.force_result_conflict = True
    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationUncertainError):
        await materialize(service, lease)
    assert lease.authorization_lease_id not in repository.results
    assert adapter.cleanup_calls == 1


@pytest.mark.asyncio
async def test_receipt_must_start_after_attempt_and_respect_policy_lifetime() -> None:
    service, _, adapter, _, lease = await fixture()
    adapter.materialized_at_delta = timedelta(seconds=2)
    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationUncertainError):
        await materialize(service, lease)
    assert adapter.cleanup_calls == 1

    service, repository, adapter, audit, lease = await fixture()
    policy_values = service.policy.digest_payload()
    policy_values["maximum_artifact_lifetime_seconds"] = 1
    policy = WorkflowEventPhysicalTransportCredentialMaterializationPolicy(
        **cast(Any, policy_values), canonical_digest=canonical_digest(policy_values)
    )
    adapter.usable_lifetime = timedelta(seconds=2)
    service = WorkflowEventPhysicalTransportCredentialMaterializationService(
        repository=cast(Any, repository),
        materializer=adapter,
        audit_sink=audit,
        policy=policy,
    )
    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationUncertainError):
        await materialize(service, lease)
    assert adapter.cleanup_calls == 1


@pytest.mark.asyncio
async def test_attempt_rejects_start_outside_freshness_or_lease_window() -> None:
    service, repository, _, _, lease = await fixture()
    result = await materialize(service, lease)
    attempt = repository.attempts[result.authorization_lease_id]
    for started_at in (attempt.freshness_valid_until, attempt.lease_valid_until):
        with pytest.raises(ValueError, match="outside validity window"):
            replace(attempt, started_at=started_at)


def test_public_contract_has_no_secret_retry_or_caller_owned_lineage_fields() -> None:
    parameters = inspect.signature(
        WorkflowEventPhysicalTransportCredentialMaterializationService.materialize
    ).parameters
    assert set(parameters) == {
        "self",
        "authorization_lease_id",
        "authorization_lease_digest",
        "materialization_policy_id",
        "materialization_policy_version",
        "irreversible_consumption_acknowledged",
        "uncertain_outcome_requires_new_authorization_acknowledged",
        "idempotency_key",
        "context",
    }
    forbidden = {
        "username",
        "password",
        "token",
        "private_key",
        "secret",
        "vault_path",
        "provider_payload",
        "retry",
        "endpoint",
        "destination",
    }
    for model in (
        WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim,
        WorkflowEventPhysicalTransportCredentialMaterializationAttempt,
        WorkflowEventPhysicalTransportCredentialMaterializationInstruction,
        WorkflowEventPhysicalTransportCredentialMaterializationReceipt,
        WorkflowEventPhysicalTransportCredentialMaterializationResult,
    ):
        assert not forbidden & set(model.__dataclass_fields__)
    assert not hasattr(WorkflowEventPhysicalTransportCredentialMaterializationService, "retry")
