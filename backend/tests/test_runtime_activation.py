from __future__ import annotations

import asyncio
import os
import runpy
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Table, UniqueConstraint, delete
from sqlalchemy.ext.asyncio import create_async_engine
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink
from test_secret_brokerage import (
    RuntimeFixture,
    authorize_secret_brokerage,
    secret_brokerage_authorizer,
    secret_brokerage_fixture,
)

from atlas.api.app import create_app
from atlas.api.runtime_activation_schemas import (
    ConnectorRuntimeActivationInventoryData,
    ConnectorRuntimeActivationOptionData,
)
from atlas.core.audit import AuditRecord
from atlas.core.persistence.models import (
    ConnectorRuntimeActivationClaimModel,
    ConnectorRuntimeActivationModel,
)
from atlas.modules.connectors.adapters.runtime_activation_memory import (
    InMemoryConnectorRuntimeActivationPolicySource,
    InMemoryConnectorRuntimeActivationProfileSource,
    InMemoryConnectorRuntimeActivationRepository,
)
from atlas.modules.connectors.adapters.runtime_activation_postgres import (
    PostgreSQLConnectorRuntimeActivationRepository,
)
from atlas.modules.connectors.adapters.runtime_activation_synthetic import (
    SyntheticConnectorRuntimeActivator,
)
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
    _signed_snapshot,
    build_connector_runtime_activation_profile,
    build_development_connector_runtime_activation_policy,
)
from atlas.modules.connectors.application.runtime_activation_ports import (
    ConnectorRuntimeActivationError,
)
from atlas.modules.connectors.application.secret_brokerage import ConnectorSecretBrokerageService
from atlas.modules.connectors.domain.runtime_activation import (
    ConnectorRuntimeActivationClaim,
    ConnectorRuntimeActivationInstruction,
    ConnectorRuntimeActivationPolicySnapshot,
    ConnectorRuntimeActivationProfileSnapshot,
    ConnectorRuntimeActivationReceipt,
    ConnectorRuntimeActivationRecord,
)
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

ACKNOWLEDGEMENT_FIELD = (
    "acknowledged_activation_grants_no_target_connection_invocation_execution_or_deployment"
)
EXPECTED_RUNTIME_ACTIVATION_INVENTORY_FIELDS = {
    "activation_id",
    "source_brokerage_authorization_id",
    "connector_id",
    "release_version",
    "instance_id",
    "display_name",
    "activation_profile_id",
    "activation_policy_id",
    "activation_policy_version",
    "activation_adapter_id",
    "health_probe_results",
    "instance_state",
    "activated_by",
    "purpose",
    "activated_at",
    "healthy_at",
    "runtime_boundary_bound",
    "runtime_trust_granted",
    "secret_brokerage_governed",
    "credential_resolution_authorized",
    "secret_lease_issued",
    "credentials_resolved",
    "runner_started",
    "package_loaded",
    "runtime_health_verified",
    "lease_delivery_completed",
    "delivery_channel_closed",
    "lease_revocation_confirmed",
    "eligible_for_target_session_authorization",
    "target_connected",
    "target_connection_authorized",
    "capability_invocation_authorized",
    "capability_invoked",
    "execution_authorized",
    "deployment_approved",
    "infrastructure_mutation_performed",
}
EXPECTED_RUNTIME_ACTIVATION_OPTION_FIELDS = {
    "source_brokerage_authorization_id",
    "source_brokerage_authorization_digest",
    "package_digest",
    "activation_profile_id",
    "activation_profile_digest",
    "activation_profile_expires_at",
    "activation_policy_id",
    "activation_policy_digest",
    "activation_policy_version",
    "activation_policy_expires_at",
    "required_assurance_level",
    "health_probe_ids",
    "resulting_instance_state",
    "secret_lease_issued",
    "credentials_resolved",
    "runner_started",
    "package_loaded",
    "runtime_health_verified",
    "delivery_channel_closed",
    "lease_revocation_confirmed",
    "eligible_for_target_session_authorization",
    "target_connected",
    "target_connection_authorized",
    "capability_invocation_authorized",
    "capability_invoked",
    "execution_authorized",
    "deployment_approved",
    "infrastructure_mutation_performed",
}


class MaliciousReceiptRuntimeActivator(SyntheticConnectorRuntimeActivator):
    def __init__(
        self,
        *,
        clock: Callable[[], datetime],
        mode: str,
        profile: ConnectorRuntimeActivationProfileSnapshot,
    ) -> None:
        super().__init__(clock=clock)
        self._mode = mode
        self._profile = profile

    async def activate(
        self, instruction: ConnectorRuntimeActivationInstruction
    ) -> ConnectorRuntimeActivationReceipt:
        receipt = await super().activate(instruction)
        if self._mode == "slow":
            receipt = replace(
                receipt,
                healthy_at=receipt.started_at
                + timedelta(seconds=self._profile.startup_timeout_seconds + 1),
                canonical_digest="0" * 64,
            )
        elif self._mode == "future":
            future = receipt.started_at + timedelta(seconds=1)
            receipt = replace(
                receipt,
                started_at=future,
                healthy_at=future,
                canonical_digest="0" * 64,
            )
        elif self._mode == "before_profile":
            receipt = replace(
                receipt,
                started_at=self._profile.issued_at - timedelta(seconds=1),
                healthy_at=self._profile.issued_at,
                canonical_digest="0" * 64,
            )
        elif self._mode == "reversed":
            receipt = replace(receipt, canonical_digest="0" * 64)
            object.__setattr__(
                receipt,
                "healthy_at",
                receipt.started_at - timedelta(seconds=1),
            )
        elif self._mode == "stale_attempt":
            pass
        else:
            raise AssertionError(f"Unknown malicious receipt mode: {self._mode}")
        object.__setattr__(receipt, "canonical_digest", self._digest(receipt))
        return receipt


class RaceRuntimeActivator(SyntheticConnectorRuntimeActivator):
    def __init__(self, *, clock: Callable[[], datetime]) -> None:
        super().__init__(clock=clock)

    async def activate(
        self, instruction: ConnectorRuntimeActivationInstruction
    ) -> ConnectorRuntimeActivationReceipt:
        await asyncio.sleep(0.01)
        return await super().activate(instruction)


class FailSecondAuditSink:
    def __init__(self) -> None:
        self.calls = 0

    async def record(self, event: AuditRecord) -> None:
        del event
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("audit unavailable")


class ClaimUncertainRuntimeActivationRepository(InMemoryConnectorRuntimeActivationRepository):
    async def claim(self, claim: ConnectorRuntimeActivationClaim) -> bool:
        del claim
        raise RuntimeError("claim outcome unavailable")


class PublishUncertainRuntimeActivationRepository(InMemoryConnectorRuntimeActivationRepository):
    async def publish(
        self,
        *,
        claim: ConnectorRuntimeActivationClaim,
        record: ConnectorRuntimeActivationRecord,
        now: datetime,
    ) -> bool:
        del claim, record, now
        raise RuntimeError("publish outcome unavailable")


class RecoveryFenceUncertainRuntimeActivationRepository(
    InMemoryConnectorRuntimeActivationRepository
):
    async def fence_expired_claim(
        self,
        *,
        claim: ConnectorRuntimeActivationClaim,
        recovery_attempt_id: str,
        now: datetime,
    ) -> bool:
        del claim, recovery_attempt_id, now
        raise RuntimeError("recovery fence unavailable")


def runtime_activation_operator(
    subject_id: str = "subject.connector-independent-runtime-activation-operator",
) -> AuthenticatedSubject:
    return secret_brokerage_authorizer(subject_id)


async def runtime_activation_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    ConnectorRuntimeActivationService,
    ConnectorSecretBrokerageService,
    RuntimeFixture,
    ConnectorRuntimeTrustGrantRecord,
    ConnectorSecretBrokerageAuthorizationRecord,
    ConnectorRuntimeActivationProfileSnapshot,
    ConnectorRuntimeActivationPolicySnapshot,
    SyntheticConnectorRuntimeActivator,
]:
    (
        brokerage_service,
        runtime_fixture,
        runtime_trust,
        brokerage_profile,
        brokerage_policy,
    ) = await secret_brokerage_fixture()
    brokerage = await authorize_secret_brokerage(
        brokerage_service, runtime_trust, brokerage_profile, brokerage_policy
    )
    profile = build_connector_runtime_activation_profile(
        source=brokerage,
        runtime_trust=runtime_trust,
        issued_at=runtime_trust.granted_at,
        expires_at=runtime_trust.granted_at + timedelta(days=10),
    )
    policy = build_development_connector_runtime_activation_policy(
        organization_id=runtime_trust.organization_id,
        environment_id=runtime_trust.environment_id,
        issued_at=runtime_trust.granted_at - timedelta(hours=1),
        expires_at=runtime_trust.granted_at + timedelta(days=10),
    )
    if required_assurance_level is not policy.required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_snapshot(policy))
    activator = SyntheticConnectorRuntimeActivator(clock=lambda: runtime_trust.granted_at)
    service = ConnectorRuntimeActivationService(
        repository=InMemoryConnectorRuntimeActivationRepository(),
        source=brokerage_service,
        profile_source=InMemoryConnectorRuntimeActivationProfileSource((profile,)),
        policy_source=InMemoryConnectorRuntimeActivationPolicySource((policy,)),
        activator=activator,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=runtime_trust.environment_id,
        clock=lambda: runtime_trust.granted_at,
    )
    return (
        service,
        brokerage_service,
        runtime_fixture,
        runtime_trust,
        brokerage,
        profile,
        policy,
        activator,
    )


async def activate_runtime(
    service: ConnectorRuntimeActivationService,
    brokerage: ConnectorSecretBrokerageAuthorizationRecord,
    profile: ConnectorRuntimeActivationProfileSnapshot,
    policy: ConnectorRuntimeActivationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "runtime-activation-001",
) -> ConnectorRuntimeActivationRecord:
    return await service.create(
        actor=actor or runtime_activation_operator(),
        source_brokerage_authorization_id=brokerage.authorization_id,
        source_brokerage_authorization_digest=brokerage.canonical_digest,
        package_digest=brokerage.package_digest,
        activation_profile_id=profile.profile_id,
        activation_profile_digest=profile.canonical_digest,
        activation_policy_id=policy.policy_id,
        activation_policy_digest=policy.canonical_digest,
        purpose="Activate the exact isolated connector runtime and verify local health only.",
        activation_boundary_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_runtime_activation",
    )


@pytest.mark.asyncio
async def test_runtime_activation_proves_health_without_target_authority() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture(
        audit_sink=audit
    )
    record = await activate_runtime(service, brokerage, profile, policy)
    repeated = await activate_runtime(service, brokerage, profile, policy)

    assert record.instance_state == "enabled_runtime_healthy"
    assert record.secret_lease_issued and record.credentials_resolved
    assert record.runner_started and record.package_loaded and record.runtime_health_verified
    assert record.delivery_channel_closed and record.lease_revocation_confirmed
    assert record.eligible_for_target_session_authorization
    assert not record.target_connected and not record.target_connection_authorized
    assert not record.capability_invocation_authorized and not record.capability_invoked
    assert not record.execution_authorized and not record.deployment_approved
    assert repeated.reused and repeated.activation_id == record.activation_id
    assert [item.result_code for item in audit.records] == [
        "connector_runtime_activation_requested",
        "connector_runtime_activation_completed",
    ]


@pytest.mark.asyncio
async def test_runtime_activation_accepts_development_identity_under_default_policy() -> None:
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture()
    development_actor = replace(
        runtime_activation_operator(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    record = await activate_runtime(service, brokerage, profile, policy, actor=development_actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.activated_by == development_actor.subject_id


@pytest.mark.parametrize(
    "required_assurance_level",
    [AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED],
)
@pytest.mark.asyncio
async def test_runtime_activation_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture(
        required_assurance_level=required_assurance_level
    )
    development_actor = replace(
        runtime_activation_operator(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(ConnectorRuntimeActivationError, match="invalid"):
        await activate_runtime(service, brokerage, profile, policy, actor=development_actor)


@pytest.mark.asyncio
async def test_runtime_activation_rejects_non_human_actor() -> None:
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture()
    service_actor = replace(
        runtime_activation_operator(),
        kind=SubjectKind.SERVICE,
        authentication_method=AuthenticationMethod.WORKLOAD_TOKEN,
    )

    with pytest.raises(ConnectorRuntimeActivationError, match="human_required"):
        await activate_runtime(service, brokerage, profile, policy, actor=service_actor)


@pytest.mark.asyncio
async def test_runtime_activation_rejects_actor_reuse_and_altered_profile() -> None:
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture()
    with pytest.raises(ConnectorRuntimeActivationError, match="separation_required"):
        await activate_runtime(
            service,
            brokerage,
            profile,
            policy,
            actor=runtime_activation_operator(brokerage.authorized_by),
        )

    unsafe = replace(profile, egress_policy_digest="f" * 64, canonical_digest="0" * 64)
    unsafe = replace(unsafe, canonical_digest=_signed_snapshot(unsafe))
    unsafe_service = ConnectorRuntimeActivationService(
        repository=InMemoryConnectorRuntimeActivationRepository(),
        source=service._source,
        profile_source=InMemoryConnectorRuntimeActivationProfileSource((unsafe,)),
        policy_source=InMemoryConnectorRuntimeActivationPolicySource((policy,)),
        activator=SyntheticConnectorRuntimeActivator(clock=service._clock),
        audit_sink=CollectingAuditSink(),
        environment_id=brokerage.environment_id,
        clock=service._clock,
    )
    with pytest.raises(ConnectorRuntimeActivationError, match="invalid"):
        await activate_runtime(unsafe_service, brokerage, unsafe, policy, key="unsafe-runtime-001")


@pytest.mark.asyncio
async def test_completion_audit_failure_compensates_and_does_not_persist() -> None:
    service, _, _, _, brokerage, profile, policy, activator = await runtime_activation_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(ConnectorRuntimeActivationError, match="failed"):
        await activate_runtime(service, brokerage, profile, policy)
    expected_id = (
        "connector-runtime-activation."
        + ConnectorRuntimeActivationService._digest(
            [
                brokerage.organization_id,
                brokerage.environment_id,
                brokerage.authorization_id,
                profile.profile_id,
                profile.canonical_digest,
            ]
        )[:24]
    )
    assert len(activator.compensated) == 1
    assert next(iter(activator.compensated)).startswith("connector-runtime-activation-attempt.")
    assert await service.repository.get(activation_id=expected_id) is None


@pytest.mark.asyncio
async def test_claim_uncertainty_is_audited_and_fails_closed() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, brokerage, profile, policy, activator = await runtime_activation_fixture(
        audit_sink=audit
    )
    service._repository = ClaimUncertainRuntimeActivationRepository()

    with pytest.raises(ConnectorRuntimeActivationError, match="claim_outcome_uncertain"):
        await activate_runtime(service, brokerage, profile, policy)

    uncertainty = audit.records[-1]
    assert uncertainty.result_code == "connector_runtime_activation_claim_uncertain"
    assert uncertainty.outcome == "failed"
    assert uncertainty.target_metadata == (("failure_class", "claim_outcome_uncertain"),)
    assert not activator.activated


@pytest.mark.asyncio
async def test_publish_uncertainty_is_audited_without_unsafe_compensation() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, brokerage, profile, policy, activator = await runtime_activation_fixture(
        audit_sink=audit
    )
    repository = PublishUncertainRuntimeActivationRepository()
    service._repository = repository

    with pytest.raises(ConnectorRuntimeActivationError, match="persistence_outcome_uncertain"):
        await activate_runtime(service, brokerage, profile, policy)

    uncertainty = audit.records[-1]
    assert uncertainty.result_code == "connector_runtime_activation_persistence_uncertain"
    assert uncertainty.outcome == "failed"
    assert uncertainty.target_metadata == (("failure_class", "persistence_outcome_uncertain"),)
    assert not activator.compensated
    assert (
        await repository.get_claim_by_source_in_scope(
            source_brokerage_authorization_id=brokerage.authorization_id,
            organization_id=brokerage.organization_id,
            environment_id=brokerage.environment_id,
        )
        is not None
    )


@pytest.mark.asyncio
async def test_cross_service_activation_race_compensates_only_losing_attempt() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture(
        audit_sink=audit
    )
    activator = RaceRuntimeActivator(clock=service._clock)
    service._activator = activator
    competing_service = ConnectorRuntimeActivationService(
        repository=service.repository,
        source=service._source,
        profile_source=service._profile_source,
        policy_source=service._policy_source,
        activator=activator,
        audit_sink=audit,
        environment_id=brokerage.environment_id,
        clock=service._clock,
    )

    results = await asyncio.gather(
        activate_runtime(service, brokerage, profile, policy, key="runtime-race-first"),
        activate_runtime(
            competing_service,
            brokerage,
            profile,
            policy,
            actor=runtime_activation_operator("subject.connector-runtime-race-operator"),
            key="runtime-race-second",
        ),
        return_exceptions=True,
    )

    assert len(activator.activated) == 1
    assert not activator.compensated
    records = await service.repository.list_scope(
        organization_id=brokerage.organization_id,
        environment_id=brokerage.environment_id,
    )
    assert len(records) == 1
    assert sum(not isinstance(item, Exception) for item in results) == 1
    assert (
        sum(item.result_code == "connector_runtime_activation_completed" for item in audit.records)
        == 1
    )


@pytest.mark.asyncio
async def test_expired_claim_is_compensated_before_fenced_recovery() -> None:
    service, _, _, _, brokerage, profile, policy, activator = await runtime_activation_fixture()
    now = service._clock()
    stale_base = ConnectorRuntimeActivationClaim(
        activation_attempt_id="connector-runtime-activation-attempt.stale-recovery",
        activation_id="connector-runtime-activation.stale-recovery",
        source_brokerage_authorization_id=brokerage.authorization_id,
        organization_id=brokerage.organization_id,
        environment_id=brokerage.environment_id,
        activated_by_digest=ConnectorRuntimeActivationService._digest("stale-actor"),
        idempotency_digest=ConnectorRuntimeActivationService._digest("stale-key"),
        replay_digest=ConnectorRuntimeActivationService._digest("stale-replay"),
        claimed_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=5),
        canonical_digest="0" * 64,
    )
    stale = replace(
        stale_base,
        canonical_digest=ConnectorRuntimeActivationService._digest(
            ConnectorRuntimeActivationService._claim_payload(stale_base)
        ),
    )
    assert await service.repository.claim(stale)

    record = await activate_runtime(service, brokerage, profile, policy)

    assert record.runtime_health_verified
    assert stale.activation_attempt_id in activator.compensated


@pytest.mark.asyncio
async def test_stale_recovery_fence_uncertainty_is_audited_and_preserves_claim() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture(
        audit_sink=audit
    )
    repository = RecoveryFenceUncertainRuntimeActivationRepository()
    service._repository = repository
    now = service._clock()
    stale_base = ConnectorRuntimeActivationClaim(
        activation_attempt_id="connector-runtime-activation-attempt.stale-fence-uncertain",
        activation_id="connector-runtime-activation.stale-fence-uncertain",
        source_brokerage_authorization_id=brokerage.authorization_id,
        organization_id=brokerage.organization_id,
        environment_id=brokerage.environment_id,
        activated_by_digest=ConnectorRuntimeActivationService._digest("stale-fence-actor"),
        idempotency_digest=ConnectorRuntimeActivationService._digest("stale-fence-key"),
        replay_digest=ConnectorRuntimeActivationService._digest("stale-fence-replay"),
        claimed_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=5),
        canonical_digest="0" * 64,
    )
    stale = replace(
        stale_base,
        canonical_digest=ConnectorRuntimeActivationService._digest(
            ConnectorRuntimeActivationService._claim_payload(stale_base)
        ),
    )
    assert await repository.claim(stale)

    with pytest.raises(ConnectorRuntimeActivationError, match="stale_claim_recovery_failed"):
        await activate_runtime(service, brokerage, profile, policy)

    failure = audit.records[-1]
    assert failure.result_code == "connector_runtime_activation_stale_recovery_failed"
    assert failure.outcome == "failed"
    assert failure.target_metadata == (("failure_class", "recovery_fence_uncertain"),)
    assert (
        await repository.get_claim_by_source_in_scope(
            source_brokerage_authorization_id=brokerage.authorization_id,
            organization_id=brokerage.organization_id,
            environment_id=brokerage.environment_id,
        )
        == stale
    )


@pytest.mark.asyncio
async def test_recovery_fence_rejects_expired_attempt_publication() -> None:
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture()
    template = await activate_runtime(service, brokerage, profile, policy)
    repository = InMemoryConnectorRuntimeActivationRepository()
    now = service._clock()
    stale_base = ConnectorRuntimeActivationClaim(
        activation_attempt_id="connector-runtime-activation-attempt.fenced-publication",
        activation_id="connector-runtime-activation.fenced-publication",
        source_brokerage_authorization_id="brokerage.fenced-publication",
        organization_id=template.organization_id,
        environment_id=template.environment_id,
        activated_by_digest=ConnectorRuntimeActivationService._identifier_digest(
            template.activated_by
        ),
        idempotency_digest=template.idempotency_digest,
        replay_digest=template.replay_digest,
        claimed_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=5),
        canonical_digest="0" * 64,
    )
    stale = replace(
        stale_base,
        canonical_digest=ConnectorRuntimeActivationService._digest(
            ConnectorRuntimeActivationService._claim_payload(stale_base)
        ),
    )
    candidate = replace(
        template,
        activation_id=stale.activation_id,
        source_brokerage_authorization_id=stale.source_brokerage_authorization_id,
    )

    assert await repository.claim(stale)
    assert await repository.fence_expired_claim(
        claim=stale,
        recovery_attempt_id="connector-runtime-activation-attempt.recovery-owner",
        now=now,
    )
    assert not await repository.publish(claim=stale, record=candidate, now=now)
    assert not await repository.release_claim(stale, now=now)
    assert await repository.release_claim(
        stale,
        now=now,
        recovery_attempt_id="connector-runtime-activation-attempt.recovery-owner",
    )


@pytest.mark.asyncio
async def test_expired_recovery_lease_allows_exact_attempt_takeover() -> None:
    service, _, _, _, brokerage, _, _, _ = await runtime_activation_fixture()
    now = service._clock()
    claim_base = ConnectorRuntimeActivationClaim(
        activation_attempt_id="connector-runtime-activation-attempt.recovery-takeover",
        activation_id="connector-runtime-activation.recovery-takeover",
        source_brokerage_authorization_id=brokerage.authorization_id,
        organization_id=brokerage.organization_id,
        environment_id=brokerage.environment_id,
        activated_by_digest=ConnectorRuntimeActivationService._identifier_digest(
            "subject.recovery-takeover"
        ),
        idempotency_digest=ConnectorRuntimeActivationService._digest("recovery-takeover-key"),
        replay_digest=ConnectorRuntimeActivationService._digest("recovery-takeover-replay"),
        claimed_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=5),
        canonical_digest="0" * 64,
    )
    claim = replace(
        claim_base,
        canonical_digest=ConnectorRuntimeActivationService._digest(
            ConnectorRuntimeActivationService._claim_payload(claim_base)
        ),
    )
    repository = InMemoryConnectorRuntimeActivationRepository()
    first_owner = "connector-runtime-activation-attempt.recovery-owner-one"
    second_owner = "connector-runtime-activation-attempt.recovery-owner-two"

    assert await repository.claim(claim)
    assert await repository.fence_expired_claim(
        claim=claim, recovery_attempt_id=first_owner, now=now
    )
    assert not await repository.fence_expired_claim(
        claim=claim,
        recovery_attempt_id=second_owner,
        now=now + timedelta(minutes=1),
    )
    assert not await repository.release_claim(
        claim,
        now=now + timedelta(minutes=3),
        recovery_attempt_id=first_owner,
    )
    assert await repository.fence_expired_claim(
        claim=claim,
        recovery_attempt_id=second_owner,
        now=now + timedelta(minutes=3),
    )
    assert not await repository.release_claim(
        claim,
        now=now + timedelta(minutes=3),
        recovery_attempt_id=first_owner,
    )
    assert await repository.release_claim(
        claim,
        now=now + timedelta(minutes=3),
        recovery_attempt_id=second_owner,
    )


@pytest.mark.asyncio
async def test_final_record_blocks_same_actor_idempotency_claim_for_different_source() -> None:
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture()
    record = await activate_runtime(service, brokerage, profile, policy)
    claim_base = ConnectorRuntimeActivationClaim(
        activation_attempt_id="connector-runtime-activation-attempt.create-key-conflict",
        activation_id="connector-runtime-activation.create-key-conflict",
        source_brokerage_authorization_id="brokerage.different-source",
        organization_id=record.organization_id,
        environment_id=record.environment_id,
        activated_by_digest=ConnectorRuntimeActivationService._identifier_digest(
            record.activated_by
        ),
        idempotency_digest=record.idempotency_digest,
        replay_digest=record.replay_digest,
        claimed_at=record.activated_at,
        expires_at=record.activated_at + timedelta(minutes=10),
        canonical_digest="0" * 64,
    )
    claim = replace(
        claim_base,
        canonical_digest=ConnectorRuntimeActivationService._digest(
            ConnectorRuntimeActivationService._claim_payload(claim_base)
        ),
    )

    assert not await service.repository.claim(claim)


@pytest.mark.asyncio
async def test_runtime_activation_postgres_round_trip_excludes_sensitive_material() -> None:
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture()
    record = await activate_runtime(service, brokerage, profile, policy)
    raw = PostgreSQLConnectorRuntimeActivationRepository._storage_payload(record)
    model = PostgreSQLConnectorRuntimeActivationRepository._model(
        record,
        payload=raw,
        activation_attempt_id="connector-runtime-activation-attempt.round-trip",
    )
    restored = PostgreSQLConnectorRuntimeActivationRepository._to_domain(model)
    assert restored == record
    rendered = repr(raw).lower()
    for hidden in (
        "secret_reference_id",
        "secret_store_profile_id",
        "secret_value",
        "password",
        "lease_handle",
        "access_token",
        "bearer_token",
        "raw_health_output",
        "process_output",
        "request_fingerprint",
        "idempotency_key",
    ):
        assert hidden not in rendered


def test_runtime_activation_api_is_csrf_protected_and_minimized(tmp_path: Path) -> None:
    (
        service,
        brokerage_service,
        runtime_fixture,
        _,
        brokerage,
        profile,
        policy,
        _,
    ) = asyncio.run(runtime_activation_fixture())
    (
        runtime_service,
        enablement_service,
        validation_service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        *_rest,
    ) = runtime_fixture
    subject = runtime_activation_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.connector-runtime-activation-input.v1",
        "source_brokerage_authorization_id": brokerage.authorization_id,
        "source_brokerage_authorization_digest": brokerage.canonical_digest,
        "package_digest": brokerage.package_digest,
        "activation_profile_id": profile.profile_id,
        "activation_profile_digest": profile.canonical_digest,
        "activation_policy_id": policy.policy_id,
        "activation_policy_digest": policy.canonical_digest,
        "purpose": "Activate the exact isolated connector runtime and verify local health only.",
        ACKNOWLEDGEMENT_FIELD: True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_registration_service=registration_service,
            package_installation_service=installation_service,
            connector_instance_creation_service=instance_service,
            target_configuration_service=target_service,
            credential_assignment_service=assignment_service,
            configuration_validation_service=validation_service,
            capability_enablement_service=enablement_service,
            runtime_trust_service=runtime_service,
            secret_brokerage_service=brokerage_service,
            runtime_activation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/runtime-activations"
        options = client.get(
            f"{endpoint}/options",
            params={"source_brokerage_authorization_id": brokerage.authorization_id},
        )
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "runtime-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "lease_handle": "attacker-controlled"},
            headers={
                "Idempotency-Key": "runtime-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "runtime-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        activation_id = created.json()["data"]["activation_id"]
        read = client.get(f"{endpoint}/{activation_id}")
        inventory = client.get(
            endpoint,
            params={"source_brokerage_authorization_id": brokerage.authorization_id},
        )
        missing_inventory = client.get(
            endpoint,
            params={"source_brokerage_authorization_id": "connector-secret-brokerage.missing"},
        )
        missing_options = client.get(
            f"{endpoint}/options",
            params={"source_brokerage_authorization_id": "connector-secret-brokerage.missing"},
        )

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert options.status_code == 200 and len(options.json()["data"]) == 1
    assert read.status_code == inventory.status_code == missing_inventory.status_code == 200
    assert missing_inventory.json()["data"] == []
    assert missing_options.status_code == 404
    assert (
        created.headers["Cache-Control"]
        == read.headers["Cache-Control"]
        == inventory.headers["Cache-Control"]
        == options.headers["Cache-Control"]
        == "no-store"
    )
    data = created.json()["data"]
    assert set(ConnectorRuntimeActivationInventoryData.model_fields) == (
        EXPECTED_RUNTIME_ACTIVATION_INVENTORY_FIELDS
    )
    assert set(ConnectorRuntimeActivationOptionData.model_fields) == (
        EXPECTED_RUNTIME_ACTIVATION_OPTION_FIELDS
    )
    assert set(data) == EXPECTED_RUNTIME_ACTIVATION_INVENTORY_FIELDS
    assert set(options.json()["data"][0]) == EXPECTED_RUNTIME_ACTIVATION_OPTION_FIELDS
    assert inventory.json()["data"] == [data]
    assert data["runtime_health_verified"] is True
    assert data["target_connection_authorized"] is False
    rendered = created.text.lower()
    for hidden in (
        "credential_profile_id",
        "secret_reference_id",
        "secret_store_profile_id",
        "broker_id",
        "lease_handle",
        "request_fingerprint",
        "idempotency_key",
        "password",
        "access_token",
        "bearer_token",
        "raw_health_output",
        "process_output",
        "command",
        "workload_identity",
        "startup_timeout_seconds",
        "isolation_profile",
        "filesystem_policy",
        "egress_policy",
    ):
        assert hidden not in rendered and hidden not in options.text.lower()


@pytest.mark.asyncio
async def test_runtime_activation_inventory_options_are_scoped_and_revalidated() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture(
        audit_sink=audit
    )
    actor = runtime_activation_operator()

    options = await service.list_options(
        actor=actor,
        source_brokerage_authorization_id=brokerage.authorization_id,
        correlation_id="cor_runtime_options",
    )
    assert len(options) == 1
    assert options[0].activation_profile_digest == profile.canonical_digest
    assert options[0].activation_policy_digest == policy.canonical_digest

    foreign_actor = replace(actor, organization_id="org.foreign")
    for source_id in (brokerage.authorization_id, "connector-secret-brokerage.missing"):
        with pytest.raises(ConnectorRuntimeActivationError, match="source_not_found"):
            await service.list_options(
                actor=foreign_actor,
                source_brokerage_authorization_id=source_id,
                correlation_id="cor_runtime_foreign",
            )

    record = await activate_runtime(service, brokerage, profile, policy, actor=actor)
    listed = await service.list_activations(
        actor=actor,
        source_brokerage_authorization_id=brokerage.authorization_id,
        correlation_id="cor_runtime_list",
    )
    assert listed == (record,)
    assert (
        await service.list_activations(
            actor=foreign_actor,
            source_brokerage_authorization_id=brokerage.authorization_id,
            correlation_id="cor_runtime_foreign_list",
        )
        == ()
    )

    expired_profile = replace(
        profile,
        expires_at=profile.issued_at + timedelta(hours=1),
        canonical_digest="0" * 64,
    )
    expired_profile = replace(expired_profile, canonical_digest=_signed_snapshot(expired_profile))
    service._profile_source = InMemoryConnectorRuntimeActivationProfileSource((expired_profile,))
    service._clock = lambda: profile.issued_at + timedelta(hours=2)
    with pytest.raises(ConnectorRuntimeActivationError, match="invalid"):
        await service.get(
            actor=actor,
            activation_id=record.activation_id,
            correlation_id="cor_runtime_expired",
        )
    with pytest.raises(ConnectorRuntimeActivationError, match="invalid"):
        await service.target_session_source(activation_id=record.activation_id)
    with pytest.raises(ConnectorRuntimeActivationError, match="invalid"):
        await activate_runtime(service, brokerage, profile, policy, actor=actor)

    assert all(item.idempotency_key is None for item in audit.records)


@pytest.mark.asyncio
async def test_runtime_activation_and_options_reject_expired_credential_lineage() -> None:
    (
        service,
        _,
        runtime_fixture,
        runtime_trust,
        brokerage,
        profile,
        policy,
        _,
    ) = await runtime_activation_fixture()
    assignment_service = runtime_fixture[3]
    _, credential_profile, _ = await assignment_service.secret_brokerage_source(
        credential_profile_id=runtime_trust.credential_profile_id,
        instance_id=runtime_trust.instance_id,
    )
    assignment_service._clock = lambda: credential_profile.expires_at + timedelta(seconds=1)

    with pytest.raises(ConnectorRuntimeActivationError, match="source_not_found"):
        await service.list_options(
            actor=runtime_activation_operator(),
            source_brokerage_authorization_id=brokerage.authorization_id,
            correlation_id="cor_runtime_expired_credential_options",
        )
    with pytest.raises(ConnectorRuntimeActivationError, match="source_not_found"):
        await activate_runtime(service, brokerage, profile, policy)


@pytest.mark.parametrize("mode", ("slow", "future", "before_profile", "reversed", "stale_attempt"))
@pytest.mark.asyncio
async def test_malicious_runtime_receipt_compensates_without_persistence(mode: str) -> None:
    audit = CollectingAuditSink()
    service, _, _, runtime_trust, brokerage, profile, policy, _ = await runtime_activation_fixture(
        audit_sink=audit
    )
    malicious = MaliciousReceiptRuntimeActivator(
        clock=lambda: runtime_trust.granted_at,
        mode=mode,
        profile=profile,
    )
    service._activator = malicious
    if mode == "slow":
        service._clock = lambda: (
            runtime_trust.granted_at + timedelta(seconds=profile.startup_timeout_seconds + 2)
        )
    elif mode == "stale_attempt":
        service._clock = lambda: runtime_trust.granted_at + timedelta(seconds=1)

    with pytest.raises(ConnectorRuntimeActivationError, match="receipt_invalid"):
        await activate_runtime(service, brokerage, profile, policy)

    assert malicious.compensated
    failure = next(
        item for item in audit.records if item.result_code == "connector_runtime_activation_failed"
    )
    assert failure.outcome == "failed"
    assert failure.target_metadata == (("failure_class", "runtime_activation_receipt_invalid"),)
    assert (
        await service.repository.list_scope(
            organization_id=runtime_trust.organization_id,
            environment_id=runtime_trust.environment_id,
        )
        == ()
    )


@pytest.mark.asyncio
async def test_runtime_activation_repository_keys_and_ids_are_tenant_scoped() -> None:
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture()
    record = await activate_runtime(service, brokerage, profile, policy)
    expected_seed = ConnectorRuntimeActivationService._digest(
        [
            record.organization_id,
            record.environment_id,
            brokerage.authorization_id,
            profile.profile_id,
            profile.canonical_digest,
        ]
    )
    assert record.activation_id == f"connector-runtime-activation.{expected_seed[:24]}"

    foreign = replace(
        record,
        activation_id="connector-runtime-activation.foreign-tenant",
        organization_id="org.foreign",
        canonical_digest="0" * 64,
    )
    foreign = replace(
        foreign,
        canonical_digest=ConnectorRuntimeActivationService._digest(
            ConnectorRuntimeActivationService._record_payload(foreign)
        ),
    )
    assert await service.repository.add(foreign)
    assert (
        await service.repository.get_by_brokerage_authorization_in_scope(
            source_brokerage_authorization_id=record.source_brokerage_authorization_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        == record
    )
    assert (
        await service.repository.get_by_brokerage_authorization_in_scope(
            source_brokerage_authorization_id=foreign.source_brokerage_authorization_id,
            organization_id=foreign.organization_id,
            environment_id=foreign.environment_id,
        )
        == foreign
    )


def test_runtime_activation_persistence_constraints_and_migration_are_tenant_scoped() -> None:
    table = ConnectorRuntimeActivationModel.__table__
    assert isinstance(table, Table)
    unique_columns = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_columns["uq_connector_runtime_activations_activation_attempt"] == (
        "activation_attempt_id",
    )
    assert unique_columns["uq_connector_runtime_activations_brokerage_authorization"] == (
        "organization_id",
        "environment_id",
        "source_brokerage_authorization_id",
    )
    assert unique_columns["uq_connector_runtime_activations_actor_idempotency"] == (
        "organization_id",
        "environment_id",
        "activated_by_digest",
        "idempotency_digest",
    )
    claim_table = ConnectorRuntimeActivationClaimModel.__table__
    assert isinstance(claim_table, Table)
    claim_unique_columns = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in claim_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert claim_unique_columns["uq_connector_runtime_activation_claims_source"] == (
        "organization_id",
        "environment_id",
        "source_brokerage_authorization_id",
    )
    assert claim_unique_columns["uq_connector_runtime_activation_claims_actor_idempotency"] == (
        "organization_id",
        "environment_id",
        "activated_by_digest",
        "idempotency_digest",
    )
    assert all(index.name is not None and len(index.name) <= 63 for index in claim_table.indexes)
    assert "ix_connector_rt_activation_claims_source" in {
        index.name for index in claim_table.indexes
    }

    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260824_0159_scope_connector_runtime_activations.py"
    ).read_text(encoding="ascii")
    assert "GROUP BY source_brokerage_authorization_id HAVING COUNT(*) > 1" in migration
    assert "GROUP BY activated_by, idempotency_digest HAVING COUNT(*) > 1" in migration
    assert "LOCK TABLE connector_runtime_activations IN ACCESS EXCLUSIVE MODE" in migration
    actor_constraint_drop = migration.index(
        'op.drop_constraint(\n        "uq_connector_runtime_activations_actor_idempotency"'
    )
    assert actor_constraint_drop < migration.index("for row in legacy_rows:")
    downgrade_start = migration.index("def downgrade() -> None:")
    downgrade_lock = migration.index(
        '"LOCK TABLE connector_runtime_activations, "', downgrade_start
    )
    downgrade_count = migration.index('sa.text("SELECT COUNT(*)', downgrade_start)
    downgrade_guard = migration.index("if activation_count or claim_count:", downgrade_start)
    downgrade_drop = migration.index(
        'op.drop_table("connector_runtime_activation_claims")', downgrade_start
    )
    assert downgrade_lock < downgrade_count < downgrade_guard < downgrade_drop

    migration_namespace = runpy.run_path(
        str(
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "versions"
            / "20260824_0159_scope_connector_runtime_activations.py"
        )
    )
    actor = "subject.legacy-runtime-operator"
    organization_id = "org-atlas"
    environment_id = "development"
    idempotency_key = "legacy-runtime-key"
    request_fingerprint = "a" * 64
    collision_key = ConnectorRuntimeActivationService._digest(
        [organization_id, environment_id, actor, idempotency_key]
    )
    assert collision_key != idempotency_key
    assert len(collision_key) == 64
    assert migration_namespace["_legacy_digests"](
        organization_id=organization_id,
        environment_id=environment_id,
        activated_by=actor,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    ) == (
        ConnectorRuntimeActivationService._identifier_digest(actor),
        ConnectorRuntimeActivationService._digest(
            [organization_id, environment_id, actor, idempotency_key]
        ),
        ConnectorRuntimeActivationService._digest(
            [
                organization_id,
                environment_id,
                ConnectorRuntimeActivationService._identifier_digest(actor),
                ConnectorRuntimeActivationService._digest(
                    [organization_id, environment_id, actor, idempotency_key]
                ),
                request_fingerprint,
            ]
        ),
    )


@pytest.mark.asyncio
async def test_live_postgres_claim_and_final_publish_share_coordination_lock() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture()
    template = await activate_runtime(service, brokerage, profile, policy)
    suffix = uuid4().hex[:12]
    source_id = f"connector-secret-brokerage-authorization.race-{suffix}"
    base_claim = ConnectorRuntimeActivationClaim(
        activation_attempt_id=f"connector-runtime-activation-attempt.race-a-{suffix}",
        activation_id=f"connector-runtime-activation.race-{suffix}",
        source_brokerage_authorization_id=source_id,
        organization_id=template.organization_id,
        environment_id=template.environment_id,
        activated_by_digest=ConnectorRuntimeActivationService._digest("race-actor-a"),
        idempotency_digest=ConnectorRuntimeActivationService._digest("race-key-a"),
        replay_digest=ConnectorRuntimeActivationService._digest("race-request"),
        claimed_at=template.activated_at,
        expires_at=template.activated_at + timedelta(minutes=5),
        canonical_digest="0" * 64,
    )
    first = replace(
        base_claim,
        canonical_digest=ConnectorRuntimeActivationService._digest(
            ConnectorRuntimeActivationService._claim_payload(base_claim)
        ),
    )
    final_record = replace(
        template,
        activation_id=f"connector-runtime-activation.final-{suffix}",
        source_brokerage_authorization_id=source_id,
        activated_by=f"subject.connector-runtime-final-{suffix}",
        idempotency_digest=ConnectorRuntimeActivationService._digest("final-key"),
        replay_digest=ConnectorRuntimeActivationService._digest("final-replay"),
    )
    first_engine = create_async_engine(database_url)
    second_engine = create_async_engine(database_url)
    first_repository = PostgreSQLConnectorRuntimeActivationRepository(first_engine)
    second_repository = PostgreSQLConnectorRuntimeActivationRepository(second_engine)
    try:
        results = await asyncio.gather(
            first_repository.claim(first),
            second_repository.add(final_record),
        )
        assert sorted(results) == [False, True]
    finally:
        async with first_engine.begin() as connection:
            await connection.execute(
                delete(ConnectorRuntimeActivationClaimModel).where(
                    ConnectorRuntimeActivationClaimModel.source_brokerage_authorization_id
                    == source_id
                )
            )
            await connection.execute(
                delete(ConnectorRuntimeActivationModel).where(
                    ConnectorRuntimeActivationModel.source_brokerage_authorization_id == source_id
                )
            )
        await first_repository.close()
        await second_repository.close()
