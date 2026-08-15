from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import datetime, timedelta
from enum import StrEnum
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_workflow_target_context_access_authorization_leases import (
    DB_NOW,
    SCOPE,
    CollectingAuditSink,
    FakeStatusAttestor,
    HmacStatusSignatureVerifier,
    accessor_context,
    authorize,
)
from test_workflow_target_context_access_authorization_leases import (
    service_fixture as access_service_fixture,
)

from atlas.modules.workflows.adapters import (
    SyntheticWorkflowPhysicalTransportTargetContextArtifactOpener,
    UnavailableWorkflowPhysicalTransportTargetContextArtifactOpener,
)
from atlas.modules.workflows.application import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningError,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningService,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningUncertainError,
    WorkflowTargetContextArtifactOpeningClaimRequest,
    WorkflowTargetContextArtifactOpeningClaimResult,
    WorkflowTargetContextArtifactOpeningClaimStatus,
    WorkflowTargetContextArtifactOpeningResultRequest,
    WorkflowTargetContextArtifactOpeningResultStatus,
    WorkflowTargetContextArtifactOpeningResultWrite,
    validate_workflow_target_context_artifact_opening_claim_request,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportCredentialMaterializationAuthority,
    WorkflowEventPhysicalTransportCredentialMaterializationResultState,
    WorkflowEventPhysicalTransportEndpointMaterializationAuthority,
    WorkflowEventPhysicalTransportEndpointMaterializationResultState,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    WorkflowEventPhysicalTransportTargetContextAccessLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttempt,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttemptState,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningFailureClass,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState,
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowProtectedArtifactKind,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy,
)

OPENING_NOW = DB_NOW + timedelta(seconds=1)


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


class InMemoryTargetContextArtifactOpeningRepository:
    def __init__(
        self,
        *,
        lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        calls: list[str],
        durable: bool = True,
    ) -> None:
        self.lease = lease
        self.binding = binding
        self.calls = calls
        self._durable = durable
        self.now = OPENING_NOW
        self.endpoint = SimpleNamespace(
            materialization_id=binding.endpoint_materialization_id,
            canonical_digest=binding.endpoint_materialization_digest,
            state=(
                WorkflowEventPhysicalTransportEndpointMaterializationResultState
            ).MATERIALIZED_PROTECTED,
            protected_artifact_id="protected-endpoint-artifact.imp-210",
            protected_artifact_digest="a" * 64,
            usable_until=OPENING_NOW + timedelta(seconds=10),
            protected_artifact_revoked=False,
            authority=WorkflowEventPhysicalTransportEndpointMaterializationAuthority(),
        )
        self.credential = SimpleNamespace(
            materialization_id=binding.credential_materialization_id,
            canonical_digest=binding.credential_materialization_digest,
            state=(
                WorkflowEventPhysicalTransportCredentialMaterializationResultState
            ).MATERIALIZED_PROTECTED,
            protected_artifact_id="protected-credential-artifact.imp-210",
            protected_artifact_digest="b" * 64,
            usable_until=OPENING_NOW + timedelta(seconds=10),
            protected_artifact_revoked=False,
            authority=WorkflowEventPhysicalTransportCredentialMaterializationAuthority(),
        )
        self.claims: dict[
            str, WorkflowEventPhysicalTransportTargetContextAccessLeaseConsumptionClaim
        ] = {}
        self.attempts: dict[
            str, WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttempt
        ] = {}
        self.results: dict[
            str, WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult
        ] = {}
        self.force_result_conflict = False

    @property
    def durable(self) -> bool:
        return self._durable

    async def get_authoritative_time(self) -> datetime:
        self.calls.append("authoritative-time")
        return self.now

    async def get_target_context_access_authorization_lease_by_id(
        self, *, authorization_lease_id: str
    ) -> Any:
        self.calls.append("load-lease")
        return self.lease if self.lease.authorization_lease_id == authorization_lease_id else None

    async def get_target_context_binding_by_id(self, *, binding_id: str) -> Any:
        self.calls.append("load-binding")
        return self.binding if self.binding.binding_id == binding_id else None

    async def get_endpoint_materialization_result_by_id(self, *, materialization_id: str) -> Any:
        self.calls.append("load-endpoint-result")
        return self.endpoint if self.endpoint.materialization_id == materialization_id else None

    async def get_credential_materialization_result_by_id(self, *, materialization_id: str) -> Any:
        self.calls.append("load-credential-result")
        return self.credential if self.credential.materialization_id == materialization_id else None

    async def claim_target_context_artifact_opening(
        self, request: WorkflowTargetContextArtifactOpeningClaimRequest
    ) -> WorkflowTargetContextArtifactOpeningClaimResult:
        self.calls.append("claim-transaction")
        validate_workflow_target_context_artifact_opening_claim_request(request)
        prior = self.claims.get(request.authorization_lease_id)
        if prior is not None:
            if prior.request_fingerprint != request.request_fingerprint:
                return WorkflowTargetContextArtifactOpeningClaimResult(
                    WorkflowTargetContextArtifactOpeningClaimStatus.IDEMPOTENCY_CONFLICT,
                    prior,
                    self.attempts[request.authorization_lease_id],
                    self.results.get(request.authorization_lease_id),
                )
            result = self.results.get(request.authorization_lease_id)
            return WorkflowTargetContextArtifactOpeningClaimResult(
                (
                    WorkflowTargetContextArtifactOpeningClaimStatus.REPLAY_COMPLETED
                    if result is not None
                    else WorkflowTargetContextArtifactOpeningClaimStatus.CLAIM_ONLY_UNCERTAIN
                ),
                prior,
                self.attempts[request.authorization_lease_id],
                result,
            )
        if (
            request.expected_target_context_binding_digest != self.binding.canonical_digest
            or request.expected_endpoint_materialization_digest != self.endpoint.canonical_digest
            or request.expected_credential_materialization_digest
            != self.credential.canonical_digest
            or not self.lease.issued_at <= self.now < self.lease.valid_until
            or self.now
            >= min(
                request.expected_endpoint_usable_until,
                request.expected_credential_usable_until,
                request.endpoint_status_attestation.valid_until,
                request.credential_status_attestation.valid_until,
            )
        ):
            return WorkflowTargetContextArtifactOpeningClaimResult(
                WorkflowTargetContextArtifactOpeningClaimStatus.EVIDENCE_CONFLICT,
                None,
                None,
                None,
            )
        try:
            await request.required_precommit_audit()
        except Exception:
            return WorkflowTargetContextArtifactOpeningClaimResult(
                WorkflowTargetContextArtifactOpeningClaimStatus.PRECOMMIT_AUDIT_FAILED,
                None,
                None,
                None,
            )
        authority = WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority()
        claim_values: dict[str, object] = {
            "claim_id": request.claim_id,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "target_context_binding_id": request.expected_target_context_binding_id,
            "target_context_binding_digest": request.expected_target_context_binding_digest,
            "target_context_commitment": request.expected_target_context_commitment,
            "attempt_id": request.attempt_id,
            "opening_id": request.opening_id,
            "scope": request.scope,
            "accessor_subject_id": request.accessor_subject_id,
            "claimed_at": self.now,
            "request_fingerprint": request.request_fingerprint,
            "idempotency_digest": request.idempotency_digest,
            "authority": authority,
        }
        claim = WorkflowEventPhysicalTransportTargetContextAccessLeaseConsumptionClaim(
            **cast(Any, claim_values), canonical_digest=canonical_digest(_payload(claim_values))
        )
        attempt_values: dict[str, object] = {
            "attempt_id": request.attempt_id,
            "opening_id": request.opening_id,
            "consumption_claim_id": request.claim_id,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "target_context_binding_id": request.expected_target_context_binding_id,
            "target_context_binding_digest": request.expected_target_context_binding_digest,
            "target_context_commitment": request.expected_target_context_commitment,
            "endpoint_materialization_id": request.expected_endpoint_materialization_id,
            "endpoint_materialization_digest": request.expected_endpoint_materialization_digest,
            "endpoint_protected_artifact_id": request.expected_endpoint_protected_artifact_id,
            "endpoint_protected_artifact_digest": (
                request.expected_endpoint_protected_artifact_digest
            ),
            "endpoint_status_attestation_id": request.endpoint_status_attestation.attestation_id,
            "endpoint_status_attestation_digest": (
                request.endpoint_status_attestation.canonical_digest
            ),
            "credential_materialization_id": request.expected_credential_materialization_id,
            "credential_materialization_digest": (
                request.expected_credential_materialization_digest
            ),
            "credential_protected_artifact_id": (request.expected_credential_protected_artifact_id),
            "credential_protected_artifact_digest": (
                request.expected_credential_protected_artifact_digest
            ),
            "credential_status_attestation_id": (
                request.credential_status_attestation.attestation_id
            ),
            "credential_status_attestation_digest": (
                request.credential_status_attestation.canonical_digest
            ),
            "scope": request.scope,
            "accessor_subject_id": request.accessor_subject_id,
            "policy_id": request.expected_policy_id,
            "policy_version": request.expected_policy_version,
            "policy_digest": request.expected_policy_digest,
            "started_at": self.now,
            "lease_valid_until": self.lease.valid_until,
            "joint_usable_until": self.binding.joint_usable_until,
            "evidence_valid_until": min(
                request.expected_endpoint_usable_until,
                request.expected_credential_usable_until,
                request.endpoint_status_attestation.valid_until,
                request.credential_status_attestation.valid_until,
            ),
            "state": (
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttemptState
            ).OPENING_STARTED,
            "authority": authority,
        }
        attempt = WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttempt(
            **cast(Any, attempt_values), canonical_digest=canonical_digest(_payload(attempt_values))
        )
        self.claims[request.authorization_lease_id] = claim
        self.attempts[request.authorization_lease_id] = attempt
        return WorkflowTargetContextArtifactOpeningClaimResult(
            WorkflowTargetContextArtifactOpeningClaimStatus.CLAIMED,
            claim,
            attempt,
            None,
        )

    async def record_target_context_artifact_opening_result(
        self, request: WorkflowTargetContextArtifactOpeningResultRequest
    ) -> WorkflowTargetContextArtifactOpeningResultWrite:
        self.calls.append("record-result")
        if self.force_result_conflict:
            return WorkflowTargetContextArtifactOpeningResultWrite(
                WorkflowTargetContextArtifactOpeningResultStatus.CONFLICT, None
            )
        prior = self.results.get(request.result.authorization_lease_id)
        if prior is not None:
            return WorkflowTargetContextArtifactOpeningResultWrite(
                (
                    WorkflowTargetContextArtifactOpeningResultStatus.REPLAY
                    if prior == request.result
                    else WorkflowTargetContextArtifactOpeningResultStatus.CONFLICT
                ),
                prior,
            )
        claim = self.claims[request.result.authorization_lease_id]
        attempt = self.attempts[request.result.authorization_lease_id]
        if (
            claim.canonical_digest != request.expected_claim_digest
            or attempt.canonical_digest != request.expected_attempt_digest
        ):
            return WorkflowTargetContextArtifactOpeningResultWrite(
                WorkflowTargetContextArtifactOpeningResultStatus.CONFLICT, None
            )
        self.results[request.result.authorization_lease_id] = request.result
        return WorkflowTargetContextArtifactOpeningResultWrite(
            WorkflowTargetContextArtifactOpeningResultStatus.RECORDED, request.result
        )

    async def list_target_context_artifact_opening_results(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult, ...]:
        return tuple(result for result in self.results.values() if result.scope == scope)[:limit]


class ObservingOpener(SyntheticWorkflowPhysicalTransportTargetContextArtifactOpener):
    def __init__(
        self, repository: InMemoryTargetContextArtifactOpeningRepository, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.repository = repository
        self.claim_observed = False

    async def open_paired_artifacts(
        self, instruction: WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction
    ) -> Any:
        self.claim_observed = (
            instruction.authorization_lease_id in self.repository.claims
            and instruction.authorization_lease_id in self.repository.attempts
        )
        self.repository.calls.append("trusted-opener")
        return await super().open_paired_artifacts(instruction)


class ExplodingOpener(ObservingOpener):
    async def open_paired_artifacts(
        self, instruction: WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction
    ) -> Any:
        self.claim_observed = instruction.authorization_lease_id in self.repository.claims
        self.repository.calls.append("trusted-opener")
        self.calls.append(instruction)
        raise RuntimeError("protected paired opener outcome lost")


async def fixture(
    *,
    opener_type: type[ObservingOpener] = ObservingOpener,
    failure_class: (
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningFailureClass | None
    ) = None,
    durable: bool = True,
) -> tuple[
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningService,
    InMemoryTargetContextArtifactOpeningRepository,
    ObservingOpener,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    list[str],
]:
    access_service, access_repository, _, _, verifier, _, calls = access_service_fixture()
    lease = await authorize(access_service)
    repository = InMemoryTargetContextArtifactOpeningRepository(
        lease=lease,
        binding=access_repository.binding,
        calls=calls,
        durable=durable,
    )
    endpoint = FakeStatusAttestor(kind=WorkflowProtectedArtifactKind.ENDPOINT, calls=calls)
    credential = FakeStatusAttestor(kind=WorkflowProtectedArtifactKind.CREDENTIAL, calls=calls)
    opener = opener_type(
        repository,
        clock=lambda: OPENING_NOW + timedelta(milliseconds=100),
        failure_class=failure_class,
    )
    service = WorkflowEventPhysicalTransportTargetContextArtifactOpeningService(
        repository=cast(Any, repository),
        endpoint_status_attestor=endpoint,
        credential_status_attestor=credential,
        status_signature_verifier=verifier,
        opener=opener,
        audit_sink=CollectingAuditSink(),
    )
    return service, repository, opener, lease, calls


async def open_artifacts(
    service: WorkflowEventPhysicalTransportTargetContextArtifactOpeningService,
    lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    **changes: Any,
) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult:
    values: dict[str, Any] = {
        "authorization_lease_id": lease.authorization_lease_id,
        "authorization_lease_digest": lease.canonical_digest,
        "policy_id": service.policy.policy_id,
        "policy_version": service.policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "target-context-artifact-opening-0001",
        "context": accessor_context(),
    }
    values.update(changes)
    return await service.open_artifacts(**cast(Any, values))


def test_policy_authority_and_public_contract_are_strict() -> None:
    policy = code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy()
    assert policy.paired_open_required is True
    assert policy.raw_material_return_forbidden is True
    assert policy.network_activity_forbidden is True
    assert policy.delivery_forbidden is True
    assert policy.runtime_use_forbidden is True
    assert policy.canonical_digest == canonical_digest(policy.digest_payload())

    authority = WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority()
    assert len(authority.canonical_value()) == 17
    assert set(authority.canonical_value().values()) == {False}
    with pytest.raises(ValueError, match="cannot grant authority"):
        replace(authority, network_access_authorized=True)

    parameters = inspect.signature(
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningService.open_artifacts
    ).parameters
    assert set(parameters) == {
        "self",
        "authorization_lease_id",
        "authorization_lease_digest",
        "policy_id",
        "policy_version",
        "irreversible_consumption_acknowledged",
        "uncertain_outcome_requires_new_authorization_acknowledged",
        "idempotency_key",
        "context",
    }
    forbidden = {
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
        "network_connection",
        "runtime_handle",
    }
    for model in (
        WorkflowEventPhysicalTransportTargetContextAccessLeaseConsumptionClaim,
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttempt,
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction,
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult,
    ):
        assert forbidden.isdisjoint(field.name for field in fields(model))


@pytest.mark.asyncio
async def test_claim_and_attempt_commit_before_paired_opener_and_result_is_zero_authority() -> None:
    service, repository, opener, lease, calls = await fixture()

    result = await open_artifacts(service, lease)

    assert opener.claim_observed is True
    assert calls.index("claim-transaction") < calls.index("trusted-opener")
    assert result.state is (
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState.OPENED_PROTECTED
    )
    assert result.sealed_capsule_id is not None
    assert result.sealed_capsule_digest is not None
    assert result.capsule_is_bearer_capability is False
    assert all(value is False for value in result.authority.canonical_value().values())
    assert all(
        all(value is False for value in evidence.authority.canonical_value().values())
        for evidence in (
            repository.claims[lease.authorization_lease_id],
            repository.attempts[lease.authorization_lease_id],
            result,
        )
    )
    assert await service.list_results(scope=SCOPE) == (result,)


@pytest.mark.asyncio
async def test_exact_terminal_replay_never_calls_opener_again() -> None:
    service, _, opener, lease, _ = await fixture()
    first = await open_artifacts(service, lease)

    second = await open_artifacts(service, lease)

    assert second == first
    assert len(opener.calls) == 1


@pytest.mark.asyncio
async def test_claim_only_is_outcome_uncertain_and_never_retries_opener() -> None:
    service, repository, opener, lease, _ = await fixture(opener_type=ExplodingOpener)

    with pytest.raises(
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningUncertainError,
        match="target_context_artifact_opening_outcome_uncertain",
    ):
        await open_artifacts(service, lease)
    assert lease.authorization_lease_id in repository.claims
    assert lease.authorization_lease_id not in repository.results

    with pytest.raises(WorkflowEventPhysicalTransportTargetContextArtifactOpeningUncertainError):
        await open_artifacts(service, lease)
    assert len(opener.calls) == 1


@pytest.mark.asyncio
async def test_known_paired_open_rejection_is_terminal_without_capsule() -> None:
    service, repository, opener, lease, _ = await fixture(
        failure_class=(
            WorkflowEventPhysicalTransportTargetContextArtifactOpeningFailureClass
        ).PAIR_INTEGRITY_INVALID
    )

    result = await open_artifacts(service, lease)

    assert result.state is (
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState.OPENING_FAILED
    )
    assert result.failure_class is (
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningFailureClass.PAIR_INTEGRITY_INVALID
    )
    assert result.sealed_capsule_id is None
    assert result.sealed_capsule_digest is None
    assert repository.results[lease.authorization_lease_id] == result
    assert len(opener.calls) == 1


@pytest.mark.asyncio
async def test_identity_acknowledgement_and_production_availability_fail_before_claim() -> None:
    service, repository, _, lease, _ = await fixture()
    for changes in (
        {"context": accessor_context(subject_id="service.other")},
        {"context": accessor_context(audience="audience.other")},
        {"irreversible_consumption_acknowledged": False},
        {"uncertain_outcome_requires_new_authorization_acknowledged": False},
    ):
        with pytest.raises(WorkflowEventPhysicalTransportTargetContextArtifactOpeningError):
            await open_artifacts(service, lease, **changes)
    assert repository.claims == {}

    unavailable_service, repository, _, lease, _ = await fixture()
    calls: list[str] = []
    unavailable_service = WorkflowEventPhysicalTransportTargetContextArtifactOpeningService(
        repository=cast(Any, repository),
        endpoint_status_attestor=FakeStatusAttestor(
            kind=WorkflowProtectedArtifactKind.ENDPOINT, calls=calls
        ),
        credential_status_attestor=FakeStatusAttestor(
            kind=WorkflowProtectedArtifactKind.CREDENTIAL, calls=calls
        ),
        status_signature_verifier=HmacStatusSignatureVerifier(calls),
        opener=UnavailableWorkflowPhysicalTransportTargetContextArtifactOpener(),
        audit_sink=CollectingAuditSink(),
    )
    with pytest.raises(
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningError,
        match="trusted_opener_unavailable",
    ):
        await open_artifacts(unavailable_service, lease)
    assert repository.claims == {}
