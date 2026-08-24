from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint, Table, UniqueConstraint, delete, func, text, update
from sqlalchemy.ext.asyncio import create_async_engine
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import (
    FailSecondAuditSink,
    activate_runtime,
    runtime_activation_fixture,
    runtime_activation_operator,
)
from test_secret_brokerage import RuntimeFixture

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.persistence.models import (
    ConnectorTargetSessionClaimModel,
    ConnectorTargetSessionVerificationModel,
)
from atlas.modules.connectors.adapters.target_session_memory import (
    InMemoryConnectorTargetSessionPolicySource,
    InMemoryConnectorTargetSessionProfileSource,
    InMemoryConnectorTargetSessionRepository,
)
from atlas.modules.connectors.adapters.target_session_postgres import (
    PostgreSQLConnectorTargetSessionRepository,
)
from atlas.modules.connectors.adapters.target_session_synthetic import (
    SyntheticConnectorTargetSessionAdapter,
)
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
)
from atlas.modules.connectors.application.secret_brokerage import ConnectorSecretBrokerageService
from atlas.modules.connectors.application.target_session import (
    ConnectorTargetSessionService,
    _signed_snapshot,
    build_connector_target_session_profile,
    build_development_connector_target_session_policy,
)
from atlas.modules.connectors.application.target_session_ports import ConnectorTargetSessionError
from atlas.modules.connectors.domain.runtime_activation import ConnectorRuntimeActivationRecord
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionClaim,
    ConnectorTargetSessionPolicySnapshot,
    ConnectorTargetSessionProfileSnapshot,
    ConnectorTargetSessionVerificationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

ACKNOWLEDGEMENT_FIELD = "acknowledged_bounded_session_grants_no_invocation_execution_or_deployment"


def target_session_operator(
    subject_id: str = "subject.connector-independent-target-session-operator",
) -> AuthenticatedSubject:
    return runtime_activation_operator(subject_id)


def development_target_session_operator(
    subject_id: str = "subject.connector-independent-target-session-operator",
) -> AuthenticatedSubject:
    return replace(
        target_session_operator(subject_id),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )


class GateTargetSessionAdapter(SyntheticConnectorTargetSessionAdapter):
    def __init__(self, *, clock) -> None:  # type: ignore[no-untyped-def]
        super().__init__(clock=clock)
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.verify_calls = 0

    async def verify(self, instruction):  # type: ignore[no-untyped-def]
        self.verify_calls += 1
        self.started.set()
        await self.release.wait()
        return await super().verify(instruction)


class TimeoutTargetSessionAdapter(SyntheticConnectorTargetSessionAdapter):
    def __init__(self, *, clock) -> None:  # type: ignore[no-untyped-def]
        super().__init__(clock=clock)
        self.attempt_id: str | None = None

    async def verify(self, instruction):  # type: ignore[no-untyped-def]
        self.attempt_id = instruction.verification_attempt_id
        await asyncio.sleep(2)
        return await super().verify(instruction)


class UncertainPublishTargetSessionRepository(InMemoryConnectorTargetSessionRepository):
    async def publish(self, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("synthetic uncertain commit")


class StallSecondAuditSink(CollectingAuditSink):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def record(self, event: AuditRecord) -> None:
        self.calls += 1
        if self.calls == 2:
            await asyncio.Event().wait()
        await super().record(event)


async def target_session_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    ConnectorTargetSessionService,
    ConnectorRuntimeActivationService,
    ConnectorSecretBrokerageService,
    RuntimeFixture,
    ConnectorRuntimeActivationRecord,
    ConnectorSecretBrokerageAuthorizationRecord,
    ConnectorRuntimeTrustGrantRecord,
    ConnectorTargetSessionProfileSnapshot,
    ConnectorTargetSessionPolicySnapshot,
    SyntheticConnectorTargetSessionAdapter,
]:
    (
        runtime_service,
        brokerage_service,
        runtime_fixture,
        runtime_trust,
        brokerage,
        runtime_profile,
        runtime_policy,
        _,
    ) = await runtime_activation_fixture()
    activation = await activate_runtime(runtime_service, brokerage, runtime_profile, runtime_policy)
    profile = build_connector_target_session_profile(
        activation=activation,
        brokerage=brokerage,
        runtime_trust=runtime_trust,
        issued_at=activation.healthy_at,
        expires_at=activation.healthy_at + timedelta(days=10),
    )
    policy = build_development_connector_target_session_policy(
        organization_id=activation.organization_id,
        environment_id=activation.environment_id,
        issued_at=activation.healthy_at - timedelta(hours=1),
        expires_at=activation.healthy_at + timedelta(days=10),
    )
    if policy.required_assurance_level is not required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_snapshot(policy))
    adapter = SyntheticConnectorTargetSessionAdapter(clock=lambda: activation.healthy_at)
    service = ConnectorTargetSessionService(
        repository=InMemoryConnectorTargetSessionRepository(),
        source=runtime_service,
        profile_source=InMemoryConnectorTargetSessionProfileSource((profile,)),
        policy_source=InMemoryConnectorTargetSessionPolicySource((policy,)),
        adapter=adapter,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=activation.environment_id,
        clock=lambda: activation.healthy_at,
    )
    return (
        service,
        runtime_service,
        brokerage_service,
        runtime_fixture,
        activation,
        brokerage,
        runtime_trust,
        profile,
        policy,
        adapter,
    )


async def verify_target_session(
    service: ConnectorTargetSessionService,
    activation: ConnectorRuntimeActivationRecord,
    profile: ConnectorTargetSessionProfileSnapshot,
    policy: ConnectorTargetSessionPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "target-session-001",
) -> ConnectorTargetSessionVerificationRecord:
    return await service.create(
        actor=actor or target_session_operator(),
        source_runtime_activation_id=activation.activation_id,
        source_runtime_activation_digest=activation.canonical_digest,
        package_digest=activation.package_digest,
        session_profile_id=profile.profile_id,
        session_profile_digest=profile.canonical_digest,
        session_policy_id=policy.policy_id,
        session_policy_digest=policy.canonical_digest,
        purpose="Verify one bounded read-only target session and close every ephemeral handle.",
        bounded_session_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_target_session",
    )


@pytest.mark.asyncio
async def test_target_session_is_bounded_read_only_closed_and_idempotent() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture(
        audit_sink=audit
    )
    record = await verify_target_session(service, activation, profile, policy)
    repeated = await verify_target_session(service, activation, profile, policy)

    assert record.instance_state == "enabled_target_session_verified"
    assert record.target_connection_authorized and record.target_connectivity_verified
    assert record.target_identity_verified and record.read_only_session_verified
    assert record.target_session_established and record.target_session_closed
    assert record.delivery_channel_closed and record.lease_revocation_confirmed
    assert record.eligible_for_capability_invocation_governance
    assert not record.target_connected and not record.capability_invoked
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and repeated.verification_id == record.verification_id
    assert [item.result_code for item in audit.records] == [
        "connector_target_session_requested",
        "connector_target_session_completed",
    ]


@pytest.mark.asyncio
async def test_target_session_accepts_development_identity_under_default_policy() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()

    record = await verify_target_session(
        service,
        activation,
        profile,
        policy,
        actor=development_target_session_operator(),
    )

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.verified_by == "subject.connector-independent-target-session-operator"
    assert record.target_session_closed and not record.target_connected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "required_assurance_level",
    (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED),
)
async def test_target_session_enforces_explicit_step_up_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(ConnectorTargetSessionError, match="target_session_invalid"):
        await verify_target_session(
            service,
            activation,
            profile,
            policy,
            actor=development_target_session_operator(),
        )


@pytest.mark.asyncio
async def test_target_session_denies_non_human_identity() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    actor = replace(development_target_session_operator(), kind=SubjectKind.SERVICE)

    with pytest.raises(ConnectorTargetSessionError, match="target_session_human_required"):
        await verify_target_session(service, activation, profile, policy, actor=actor)


@pytest.mark.asyncio
async def test_target_session_foreign_and_missing_sources_are_indistinguishable() -> None:
    service, _, _, _, activation, _, _, _, _, _ = await target_session_fixture()
    foreign_actor = replace(target_session_operator(), organization_id="org-foreign")
    failures: list[str] = []
    for actor, activation_id in (
        (foreign_actor, activation.activation_id),
        (target_session_operator(), "connector-runtime-activation.missing"),
    ):
        with pytest.raises(ConnectorTargetSessionError) as captured:
            await service.list_options(
                actor=actor,
                source_runtime_activation_id=activation_id,
                correlation_id="cor_target_session_non_discovery",
            )
        failures.append(str(captured.value))
    assert failures == ["target_session_source_not_found"] * 2


@pytest.mark.asyncio
async def test_target_session_rejects_actor_reuse_and_altered_network_policy() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    with pytest.raises(ConnectorTargetSessionError, match="separation_required"):
        await verify_target_session(
            service,
            activation,
            profile,
            policy,
            actor=target_session_operator(activation.activated_by),
        )

    unsafe = replace(profile, network_path_policy_digest="f" * 64, canonical_digest="0" * 64)
    unsafe = replace(unsafe, canonical_digest=_signed_snapshot(unsafe))
    unsafe_service = ConnectorTargetSessionService(
        repository=InMemoryConnectorTargetSessionRepository(),
        source=service._source,
        profile_source=InMemoryConnectorTargetSessionProfileSource((unsafe,)),
        policy_source=InMemoryConnectorTargetSessionPolicySource((policy,)),
        adapter=SyntheticConnectorTargetSessionAdapter(clock=service._clock),
        audit_sink=CollectingAuditSink(),
        environment_id=activation.environment_id,
        clock=service._clock,
    )
    with pytest.raises(ConnectorTargetSessionError, match="invalid"):
        await verify_target_session(
            unsafe_service, activation, unsafe, policy, key="unsafe-session-001"
        )


@pytest.mark.asyncio
async def test_target_session_completion_audit_failure_compensates() -> None:
    service, _, _, _, activation, _, _, profile, policy, adapter = await target_session_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(ConnectorTargetSessionError, match="failed"):
        await verify_target_session(service, activation, profile, policy)
    seed = ConnectorTargetSessionService._digest(
        [activation.activation_id, profile.profile_id, profile.canonical_digest]
    )
    verification_id = f"connector-target-session-verification.{seed[:24]}"
    assert len(adapter.compensated) == 1
    assert next(iter(adapter.compensated)).startswith("connector-target-session-attempt.")
    assert await service.repository.get(verification_id=verification_id) is None


@pytest.mark.asyncio
async def test_target_session_stalled_completion_audit_is_bounded_and_compensates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "atlas.modules.connectors.application.target_session."
        "TARGET_SESSION_REQUIRED_AUDIT_TIMEOUT_SECONDS",
        0.01,
    )
    audit = StallSecondAuditSink()
    service, _, _, _, activation, _, _, profile, policy, adapter = await target_session_fixture(
        audit_sink=audit
    )

    with pytest.raises(
        ConnectorTargetSessionError,
        match="target_session_completion_audit_failed",
    ):
        await asyncio.wait_for(
            verify_target_session(service, activation, profile, policy),
            timeout=1,
        )

    assert len(adapter.compensated) == 1
    assert audit.calls == 3
    assert [record.result_code for record in audit.records] == [
        "connector_target_session_requested",
        "connector_target_session_failed",
    ]


@pytest.mark.asyncio
async def test_target_session_distributed_claim_allows_only_one_adapter_attempt() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    repository = InMemoryConnectorTargetSessionRepository()
    adapter = GateTargetSessionAdapter(clock=service._clock)

    def clone() -> ConnectorTargetSessionService:
        return ConnectorTargetSessionService(
            repository=repository,
            source=service._source,
            profile_source=InMemoryConnectorTargetSessionProfileSource((profile,)),
            policy_source=InMemoryConnectorTargetSessionPolicySource((policy,)),
            adapter=adapter,
            audit_sink=CollectingAuditSink(),
            environment_id=activation.environment_id,
            clock=service._clock,
        )

    first = asyncio.create_task(
        verify_target_session(clone(), activation, profile, policy, key="parallel-session-001")
    )
    await asyncio.wait_for(adapter.started.wait(), timeout=1)
    with pytest.raises(ConnectorTargetSessionError, match="target_session_in_progress"):
        await asyncio.wait_for(
            verify_target_session(clone(), activation, profile, policy, key="parallel-session-001"),
            timeout=1,
        )
    adapter.release.set()
    record = await asyncio.wait_for(first, timeout=1)

    assert adapter.verify_calls == 1
    assert record.verification_attempt_id.startswith("connector-target-session-attempt.")
    assert (
        await repository.get_claim_by_source_in_scope(
            source_runtime_activation_id=activation.activation_id,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_target_session_adapter_timeout_compensates_exact_attempt() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    profile = replace(profile, session_timeout_seconds=1, canonical_digest="0" * 64)
    profile = replace(profile, canonical_digest=_signed_snapshot(profile))
    repository = InMemoryConnectorTargetSessionRepository()
    adapter = TimeoutTargetSessionAdapter(clock=service._clock)
    timed_service = ConnectorTargetSessionService(
        repository=repository,
        source=service._source,
        profile_source=InMemoryConnectorTargetSessionProfileSource((profile,)),
        policy_source=InMemoryConnectorTargetSessionPolicySource((policy,)),
        adapter=adapter,
        audit_sink=CollectingAuditSink(),
        environment_id=activation.environment_id,
        clock=service._clock,
    )

    with pytest.raises(ConnectorTargetSessionError, match="target_session_adapter_timeout"):
        await verify_target_session(
            timed_service, activation, profile, policy, key="timeout-session-001"
        )

    assert adapter.attempt_id is not None
    assert adapter.compensated == {adapter.attempt_id}
    assert (
        await repository.get_claim_by_source_in_scope(
            source_runtime_activation_id=activation.activation_id,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_target_session_uncertain_publish_fails_closed_without_wrong_compensation() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    repository = UncertainPublishTargetSessionRepository()
    adapter = SyntheticConnectorTargetSessionAdapter(clock=service._clock)
    audit = CollectingAuditSink()
    uncertain_service = ConnectorTargetSessionService(
        repository=repository,
        source=service._source,
        profile_source=InMemoryConnectorTargetSessionProfileSource((profile,)),
        policy_source=InMemoryConnectorTargetSessionPolicySource((policy,)),
        adapter=adapter,
        audit_sink=audit,
        environment_id=activation.environment_id,
        clock=service._clock,
    )

    with pytest.raises(
        ConnectorTargetSessionError,
        match="target_session_persistence_outcome_uncertain",
    ):
        await verify_target_session(
            uncertain_service,
            activation,
            profile,
            policy,
            key="uncertain-publish-session-001",
        )

    assert not adapter.compensated
    assert audit.records[-1].result_code == "connector_target_session_persistence_uncertain"
    assert audit.records[-1].outcome == "failed"


@pytest.mark.asyncio
async def test_target_session_expired_claim_requires_fenced_recovery_owner() -> None:
    repository = InMemoryConnectorTargetSessionRepository()
    now = datetime.now(UTC)
    base_claim = ConnectorTargetSessionClaim(
        verification_attempt_id="connector-target-session-attempt.expired-claim",
        verification_id="connector-target-session-verification.expired-claim",
        source_runtime_activation_id="connector-runtime-activation.expired-claim",
        organization_id="org-atlas",
        environment_id="development",
        verified_by_digest="1" * 64,
        idempotency_digest="2" * 64,
        replay_digest="3" * 64,
        claimed_at=now - timedelta(minutes=2),
        expires_at=now - timedelta(minutes=1),
        canonical_digest="0" * 64,
    )
    claim = replace(
        base_claim,
        canonical_digest=ConnectorTargetSessionService._digest(
            ConnectorTargetSessionService._claim_payload(base_claim)
        ),
    )
    assert await repository.claim(claim)
    assert await repository.fence_expired_claim(
        claim=claim,
        recovery_attempt_id="connector-target-session-attempt.recovery-owner",
        now=now,
    )
    assert not await repository.release_claim(claim, now=now)
    assert not await repository.release_claim(
        claim,
        now=now,
        recovery_attempt_id="connector-target-session-attempt.foreign-owner",
    )
    assert await repository.release_claim(
        claim,
        now=now,
        recovery_attempt_id="connector-target-session-attempt.recovery-owner",
    )


@pytest.mark.asyncio
async def test_target_session_rejects_receipt_outside_attempt_window() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    adapter = SyntheticConnectorTargetSessionAdapter(
        clock=lambda: activation.healthy_at - timedelta(seconds=1)
    )
    unsafe_service = ConnectorTargetSessionService(
        repository=InMemoryConnectorTargetSessionRepository(),
        source=service._source,
        profile_source=InMemoryConnectorTargetSessionProfileSource((profile,)),
        policy_source=InMemoryConnectorTargetSessionPolicySource((policy,)),
        adapter=adapter,
        audit_sink=CollectingAuditSink(),
        environment_id=activation.environment_id,
        clock=service._clock,
    )

    with pytest.raises(ConnectorTargetSessionError, match="target_session_receipt_invalid"):
        await verify_target_session(
            unsafe_service, activation, profile, policy, key="stale-receipt-session-001"
        )
    assert len(adapter.compensated) == 1


@pytest.mark.asyncio
async def test_target_session_postgres_round_trip_excludes_sensitive_material() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    record = await verify_target_session(service, activation, profile, policy)
    raw = PostgreSQLConnectorTargetSessionRepository._storage_payload(record)
    model = PostgreSQLConnectorTargetSessionRepository._model(record, payload=raw)
    restored = PostgreSQLConnectorTargetSessionRepository._to_domain(model)
    assert restored == record
    assert "reused" not in raw
    rendered = repr(raw).lower()
    for hidden in (
        "target_address",
        "target_endpoint",
        "target_port",
        "credential_profile_id",
        "secret_reference_id",
        "secret_store_profile_id",
        "broker_id",
        "lease_handle",
        "session_handle",
        "certificate_body",
        "raw_vendor_output",
        "transcript",
        "password",
        "access_token",
    ):
        assert hidden not in rendered


@pytest.mark.asyncio
async def test_target_session_legacy_attempt_backfill_preserves_canonical_lineage() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    record = await verify_target_session(service, activation, profile, policy)
    legacy_attempt = replace(
        record,
        verification_attempt_id=(
            "connector-target-session-attempt.legacy-"
            f"{ConnectorTargetSessionService._identifier_digest(record.verification_id)[:24]}"
        ),
        canonical_digest="0" * 64,
    )
    legacy_payload = ConnectorTargetSessionService._record_payload(legacy_attempt)
    legacy_payload.pop("verification_attempt_id")
    legacy = replace(
        legacy_attempt,
        canonical_digest=ConnectorTargetSessionService._digest(legacy_payload),
    )
    ConnectorTargetSessionService._verify_record(legacy)
    with pytest.raises(ConnectorTargetSessionError, match="record_integrity_failed"):
        ConnectorTargetSessionService._verify_record(
            replace(
                legacy,
                verification_attempt_id=(
                    "connector-target-session-attempt.legacy-ffffffffffffffffffffffff"
                ),
            )
        )


def test_target_session_persistence_constraints_are_tenant_scoped() -> None:
    table = ConnectorTargetSessionVerificationModel.__table__
    assert isinstance(table, Table)
    unique_columns = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_columns["uq_connector_target_sessions_runtime_activation"] == (
        "organization_id",
        "environment_id",
        "source_runtime_activation_id",
    )
    assert unique_columns["uq_connector_target_sessions_actor_idempotency"] == (
        "organization_id",
        "environment_id",
        "verified_by_digest",
        "idempotency_digest",
    )
    claim_table = ConnectorTargetSessionClaimModel.__table__
    assert isinstance(claim_table, Table)
    claim_unique_columns = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in claim_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert claim_unique_columns["uq_connector_target_session_claims_source"] == (
        "organization_id",
        "environment_id",
        "source_runtime_activation_id",
    )
    assert claim_unique_columns["uq_connector_target_session_claims_actor_key"] == (
        "organization_id",
        "environment_id",
        "verified_by_digest",
        "idempotency_digest",
    )
    claim_checks = {
        constraint.name
        for constraint in claim_table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_connector_target_session_claims_state" in claim_checks


@pytest.mark.asyncio
async def test_live_postgres_target_session_claim_and_publish_share_lock() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    template = await verify_target_session(service, activation, profile, policy)
    suffix = uuid4().hex[:12]
    source_id = f"connector-runtime-activation.target-race-{suffix}"
    actor_digest = ConnectorTargetSessionService._identifier_digest(template.verified_by)
    base_claim = ConnectorTargetSessionClaim(
        verification_attempt_id=f"connector-target-session-attempt.race-{suffix}",
        verification_id=f"connector-target-session-verification.race-{suffix}",
        source_runtime_activation_id=source_id,
        organization_id=template.organization_id,
        environment_id=template.environment_id,
        verified_by_digest=actor_digest,
        idempotency_digest=ConnectorTargetSessionService._digest(["claim", suffix]),
        replay_digest=ConnectorTargetSessionService._digest(["replay", suffix]),
        claimed_at=template.verified_at,
        expires_at=template.verified_at + timedelta(minutes=5),
        canonical_digest="0" * 64,
    )
    claim = replace(
        base_claim,
        canonical_digest=ConnectorTargetSessionService._digest(
            ConnectorTargetSessionService._claim_payload(base_claim)
        ),
    )
    final_record = replace(
        template,
        verification_id=f"connector-target-session-verification.final-{suffix}",
        verification_attempt_id=f"connector-target-session-attempt.final-{suffix}",
        source_runtime_activation_id=source_id,
        instance_id=f"connector-instance.target-race-{suffix}",
        idempotency_digest=ConnectorTargetSessionService._digest(["final-key", suffix]),
        replay_digest=ConnectorTargetSessionService._digest(["final-replay", suffix]),
        canonical_digest=ConnectorTargetSessionService._digest(["final-record", suffix]),
    )
    first_engine = create_async_engine(database_url)
    second_engine = create_async_engine(database_url)
    first_repository = PostgreSQLConnectorTargetSessionRepository(first_engine)
    second_repository = PostgreSQLConnectorTargetSessionRepository(second_engine)
    try:
        results = await asyncio.gather(
            first_repository.claim(claim),
            second_repository.add(final_record),
        )
        assert sorted(results) == [False, True]
    finally:
        async with first_engine.begin() as connection:
            await connection.execute(
                delete(ConnectorTargetSessionClaimModel).where(
                    ConnectorTargetSessionClaimModel.source_runtime_activation_id == source_id
                )
            )
            await connection.execute(
                delete(ConnectorTargetSessionVerificationModel).where(
                    ConnectorTargetSessionVerificationModel.source_runtime_activation_id
                    == source_id
                )
            )
        await first_repository.close()
        await second_repository.close()


@pytest.mark.asyncio
async def test_live_postgres_expired_recovery_lease_rejects_stale_owner() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    suffix = uuid4().hex[:12]
    now = datetime.now(UTC)
    base_claim = ConnectorTargetSessionClaim(
        verification_attempt_id=f"connector-target-session-attempt.recovery-{suffix}",
        verification_id=f"connector-target-session-verification.recovery-{suffix}",
        source_runtime_activation_id=f"connector-runtime-activation.recovery-{suffix}",
        organization_id="org-atlas",
        environment_id="development",
        verified_by_digest=ConnectorTargetSessionService._digest(["actor", suffix]),
        idempotency_digest=ConnectorTargetSessionService._digest(["key", suffix]),
        replay_digest=ConnectorTargetSessionService._digest(["replay", suffix]),
        claimed_at=now - timedelta(minutes=2),
        expires_at=now - timedelta(minutes=1),
        canonical_digest="0" * 64,
    )
    claim = replace(
        base_claim,
        canonical_digest=ConnectorTargetSessionService._digest(
            ConnectorTargetSessionService._claim_payload(base_claim)
        ),
    )
    owner_a = f"connector-target-session-attempt.owner-a-{suffix}"
    owner_b = f"connector-target-session-attempt.owner-b-{suffix}"
    engine = create_async_engine(database_url)
    repository = PostgreSQLConnectorTargetSessionRepository(engine)
    try:
        assert await repository.claim(claim)
        assert await repository.fence_expired_claim(
            claim=claim,
            recovery_attempt_id=owner_a,
            now=now,
        )
        async with engine.begin() as connection:
            await connection.execute(
                update(ConnectorTargetSessionClaimModel)
                .where(
                    ConnectorTargetSessionClaimModel.verification_attempt_id
                    == claim.verification_attempt_id
                )
                .values(recovery_lease_expires_at=func.now() - text("INTERVAL '1 second'"))
            )
        assert not await repository._recovery_fence_exists_exact(claim, owner_a)
        assert await repository.fence_expired_claim(
            claim=claim,
            recovery_attempt_id=owner_b,
            now=now,
        )
        assert not await repository.release_claim(
            claim,
            now=now,
            recovery_attempt_id=owner_a,
        )
        assert await repository.release_claim(
            claim,
            now=now,
            recovery_attempt_id=owner_b,
        )
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(ConnectorTargetSessionClaimModel).where(
                    ConnectorTargetSessionClaimModel.verification_attempt_id
                    == claim.verification_attempt_id
                )
            )
        await repository.close()


def test_target_session_api_is_csrf_protected_forbids_coordinates_and_is_minimized(
    tmp_path: Path,
) -> None:
    (
        service,
        runtime_service,
        brokerage_service,
        runtime_fixture,
        activation,
        _,
        _,
        profile,
        policy,
        _,
    ) = asyncio.run(target_session_fixture())
    (
        runtime_trust_service,
        enablement_service,
        validation_service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        *_rest,
    ) = runtime_fixture
    subject = development_target_session_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.connector-target-session-input.v1",
        "source_runtime_activation_id": activation.activation_id,
        "source_runtime_activation_digest": activation.canonical_digest,
        "package_digest": activation.package_digest,
        "session_profile_id": profile.profile_id,
        "session_profile_digest": profile.canonical_digest,
        "session_policy_id": policy.policy_id,
        "session_policy_digest": policy.canonical_digest,
        "purpose": "Verify one bounded read-only target session and close every ephemeral handle.",
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
            runtime_trust_service=runtime_trust_service,
            secret_brokerage_service=brokerage_service,
            runtime_activation_service=runtime_service,
            target_session_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/target-session-verifications"
        options = client.get(
            f"{endpoint}/options",
            params={"source_runtime_activation_id": activation.activation_id},
        )
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "session-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "target_address": "192.0.2.10"},
            headers={
                "Idempotency-Key": "session-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "session-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        verification_id = created.json()["data"]["verification_id"]
        read = client.get(f"{endpoint}/{verification_id}")
        inventory = client.get(
            endpoint,
            params={"source_runtime_activation_id": activation.activation_id},
        )

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert options.status_code == 200 and len(options.json()["data"]) == 1
    assert read.status_code == 200
    assert inventory.status_code == 200 and len(inventory.json()["data"]) == 1
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["target_connectivity_verified"] is True
    assert data["session_profile_digest"] == profile.canonical_digest
    assert data["session_policy_digest"] == policy.canonical_digest
    assert data["target_session_closed"] is True
    assert data["target_connected"] is False
    rendered = created.text.lower()
    for hidden in (
        "target_address",
        "target_endpoint",
        "target_port",
        "credential_profile_id",
        "secret_reference_id",
        "secret_store_profile_id",
        "broker_id",
        "lease_handle",
        "session_handle",
        "certificate_body",
        "raw_vendor_output",
        "transcript",
        "request_fingerprint",
        "idempotency_key",
        "password",
        "access_token",
        "command",
        "connector_id",
        "release_version",
        "instance_id",
        "display_name",
        "session_profile_id",
        "session_policy_id",
        "verified_by",
        "purpose",
        "reused",
    ):
        assert hidden not in rendered
