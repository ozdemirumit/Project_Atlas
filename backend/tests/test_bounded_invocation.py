from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_invocation_authorization import (
    authorize_invocation,
    invocation_fixture,
)
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import FailSecondAuditSink
from test_secret_brokerage import RuntimeFixture
from test_target_session import (
    development_target_session_operator,
    target_session_operator,
)

from atlas.api.app import create_app
from atlas.core.persistence.models import (
    ConnectorBoundedInvocationModel,
    ConnectorInvocationConsumptionClaimModel,
)
from atlas.modules.connectors.adapters.bounded_invocation_memory import (
    InMemoryConnectorBoundedInvocationPolicySource,
    InMemoryConnectorBoundedInvocationRepository,
)
from atlas.modules.connectors.adapters.bounded_invocation_postgres import (
    PostgreSQLConnectorBoundedInvocationRepository,
)
from atlas.modules.connectors.adapters.bounded_invocation_synthetic import (
    SyntheticConnectorBoundedInvocationAdapter,
)
from atlas.modules.connectors.application.bounded_invocation import (
    ConnectorBoundedInvocationService,
    _signed_policy,
    build_development_connector_bounded_invocation_policy,
)
from atlas.modules.connectors.application.bounded_invocation_ports import (
    ConnectorBoundedInvocationError,
    ConnectorBoundedInvocationUncertainError,
)
from atlas.modules.connectors.application.invocation_authorization import (
    ConnectorInvocationAuthorizationService,
)
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
)
from atlas.modules.connectors.application.secret_brokerage import (
    ConnectorSecretBrokerageService,
)
from atlas.modules.connectors.application.target_session import ConnectorTargetSessionService
from atlas.modules.connectors.domain.bounded_invocation import (
    ConnectorBoundedInvocationInstruction,
    ConnectorBoundedInvocationPolicySnapshot,
    ConnectorBoundedInvocationReceipt,
    ConnectorBoundedInvocationRecord,
)
from atlas.modules.connectors.domain.invocation_authorization import (
    ConnectorInvocationAuthorizationRecord,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind

ACKNOWLEDGEMENT_FIELD = (
    "acknowledged_authorization_is_consumed_once_without_retry_on_uncertain_outcome"
)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
COMPLETION_API_FIELDS = {
    "invocation_id",
    "schema_version",
    "version",
    "source_authorization_id",
    "source_authorization_digest",
    "package_digest",
    "capability_id",
    "capability_class",
    "required_permission",
    "output_schema_digest",
    "result_policy_digest",
    "invocation_policy_id",
    "invocation_policy_digest",
    "invocation_policy_version",
    "normalized_redacted_result_digest",
    "observation_count",
    "output_bytes",
    "instance_state",
    "started_at",
    "completed_at",
    "canonical_digest",
    "authorization_consumed",
    "target_connection_opened",
    "capability_invoked",
    "result_received",
    "result_validated",
    "result_redacted",
    "target_session_closed",
    "delivery_channel_closed",
    "lease_revocation_confirmed",
    "target_connected",
    "reusable_session_available",
    "scheduled",
    "evidence_ingested",
    "execution_authorized",
    "deployment_approved",
    "infrastructure_mutation_performed",
    "reused",
}
OPTION_API_FIELDS = {
    "source_authorization_id",
    "source_authorization_digest",
    "package_digest",
    "capability_id",
    "capability_class",
    "required_permission",
    "invocation_policy_id",
    "invocation_policy_digest",
    "invocation_policy_version",
    "invocation_policy_expires_at",
    "required_assurance_level",
    "maximum_timeout_seconds",
    "maximum_output_bytes",
    "maximum_observations",
    "resulting_instance_state",
    "irreversible_consumption_required",
    "automatic_retry_allowed",
    "target_connected",
    "reusable_session_available",
    "scheduled",
    "evidence_ingested",
    "execution_authorized",
    "deployment_approved",
    "infrastructure_mutation_performed",
}


class RecordingPermissionAuthorizer:
    def __init__(self, *, deny: bool = False) -> None:
        self.deny = deny
        self.calls: list[tuple[str, str, str]] = []

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        permission_id: str,
        capability_id: str,
        capability_class: str,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None:
        del actor, organization_id, environment_id, correlation_id
        self.calls.append((permission_id, capability_id, capability_class))
        if self.deny:
            raise ConnectorBoundedInvocationError("bounded_invocation_capability_permission_denied")


class UncertainAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def invoke(
        self, instruction: ConnectorBoundedInvocationInstruction
    ) -> ConnectorBoundedInvocationReceipt:
        del instruction
        self.calls += 1
        raise ConnectorBoundedInvocationUncertainError(
            "bounded_invocation_transport_outcome_uncertain"
        )


class AlteredReceiptAdapter(SyntheticConnectorBoundedInvocationAdapter):
    async def invoke(
        self, instruction: ConnectorBoundedInvocationInstruction
    ) -> ConnectorBoundedInvocationReceipt:
        receipt = await super().invoke(instruction)
        altered = replace(receipt, result_schema_digest="f" * 64)
        return replace(altered, canonical_digest=self._receipt_digest(altered))


class BlockingAdapter(SyntheticConnectorBoundedInvocationAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def invoke(
        self, instruction: ConnectorBoundedInvocationInstruction
    ) -> ConnectorBoundedInvocationReceipt:
        self.started.set()
        await self.release.wait()
        return await super().invoke(instruction)


class FailThirdAuditSink:
    def __init__(self) -> None:
        self.calls = 0

    async def record(self, event: object) -> None:
        del event
        self.calls += 1
        if self.calls == 3:
            raise RuntimeError("audit unavailable")


class PublishUncertainRepository(InMemoryConnectorBoundedInvocationRepository):
    async def add(self, record: ConnectorBoundedInvocationRecord) -> bool:
        del record
        raise RuntimeError("completion persistence unavailable")


async def bounded_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | FailThirdAuditSink | None = None,
    repository: InMemoryConnectorBoundedInvocationRepository | None = None,
    permission_authorizer: RecordingPermissionAuthorizer | None = None,
    adapter: SyntheticConnectorBoundedInvocationAdapter
    | UncertainAdapter
    | AlteredReceiptAdapter
    | BlockingAdapter
    | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    ConnectorBoundedInvocationService,
    ConnectorInvocationAuthorizationService,
    ConnectorTargetSessionService,
    ConnectorRuntimeActivationService,
    ConnectorSecretBrokerageService,
    RuntimeFixture,
    ConnectorInvocationAuthorizationRecord,
    ConnectorBoundedInvocationPolicySnapshot,
    RecordingPermissionAuthorizer,
    SyntheticConnectorBoundedInvocationAdapter
    | UncertainAdapter
    | AlteredReceiptAdapter
    | BlockingAdapter,
]:
    (
        authorization_service,
        target_service,
        runtime_service,
        brokerage_service,
        runtime_fixture,
        target_session,
        profile,
        envelope,
        authorization_policy,
        _,
    ) = await invocation_fixture()
    authorization = await authorize_invocation(
        authorization_service,
        target_session,
        profile,
        envelope,
        authorization_policy,
    )
    policy = build_development_connector_bounded_invocation_policy(
        organization_id=authorization.organization_id,
        environment_id=authorization.environment_id,
        issued_at=authorization.authorized_at - timedelta(hours=1),
        expires_at=authorization.authorized_at + timedelta(days=1),
    )
    if policy.required_assurance_level is not required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_policy(policy))
    authorizer = permission_authorizer or RecordingPermissionAuthorizer()
    resolved_adapter = adapter or SyntheticConnectorBoundedInvocationAdapter(
        clock=lambda: authorization.authorized_at
    )
    service = ConnectorBoundedInvocationService(
        repository=repository or InMemoryConnectorBoundedInvocationRepository(),
        source=authorization_service,
        policy_source=InMemoryConnectorBoundedInvocationPolicySource((policy,)),
        permission_authorizer=authorizer,
        adapter=resolved_adapter,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=authorization.environment_id,
        clock=lambda: authorization.authorized_at,
    )
    return (
        service,
        authorization_service,
        target_service,
        runtime_service,
        brokerage_service,
        runtime_fixture,
        authorization,
        policy,
        authorizer,
        resolved_adapter,
    )


async def invoke_bounded(
    service: ConnectorBoundedInvocationService,
    authorization: ConnectorInvocationAuthorizationRecord,
    policy: ConnectorBoundedInvocationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "bounded-invocation-001",
) -> ConnectorBoundedInvocationRecord:
    return await service.create(
        actor=actor or target_session_operator("subject.connector-independent-bounded-invoker"),
        source_authorization_id=authorization.authorization_id,
        source_authorization_digest=authorization.canonical_digest,
        package_digest=authorization.package_digest,
        invocation_policy_id=policy.policy_id,
        invocation_policy_digest=policy.canonical_digest,
        purpose="Invoke one authorized read-only capability and close every ephemeral resource.",
        irreversible_consumption_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_bounded_invocation",
    )


@pytest.mark.asyncio
async def test_bounded_invocation_consumes_once_closes_resources_and_is_idempotent() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, _, _, authorization, policy, authorizer, adapter = await bounded_fixture(
        audit_sink=audit
    )
    record = await invoke_bounded(service, authorization, policy)
    repeated = await invoke_bounded(service, authorization, policy)

    assert record.instance_state == "enabled_bounded_capability_invocation_completed"
    assert record.authorization_consumed and record.capability_invoked
    assert record.result_received and record.result_validated and record.result_redacted
    assert record.target_session_closed and record.delivery_channel_closed
    assert record.lease_revocation_confirmed and not record.target_connected
    assert not record.scheduled and not record.evidence_ingested
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and repeated.invocation_id == record.invocation_id
    assert isinstance(adapter, SyntheticConnectorBoundedInvocationAdapter)
    assert len(adapter.calls) == 1
    assert authorizer.calls == [
        (
            authorization.required_permission,
            authorization.capability_id,
            authorization.capability_class,
        ),
        (
            authorization.required_permission,
            authorization.capability_id,
            authorization.capability_class,
        ),
    ]
    assert [item.result_code for item in audit.records] == [
        "connector_bounded_invocation_requested",
        "connector_bounded_invocation_authorization_consumed",
        "connector_bounded_invocation_completed",
    ]
    with pytest.raises(ConnectorBoundedInvocationError, match="idempotency_conflict"):
        await invoke_bounded(
            service,
            authorization,
            policy,
            key="bounded-invocation-key-different",
        )
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_bounded_invocation_accepts_development_identity_under_default_policy() -> None:
    service, _, _, _, _, _, authorization, policy, _, _ = await bounded_fixture()
    actor = development_target_session_operator("subject.connector-independent-bounded-invoker")

    record = await invoke_bounded(service, authorization, policy, actor=actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.invoked_by == actor.subject_id
    assert record.authorization_consumed and not record.reusable_session_available


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "required_assurance_level",
    (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED),
)
async def test_bounded_invocation_enforces_explicit_step_up_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, _, _, _, _, authorization, policy, authorizer, adapter = await bounded_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(ConnectorBoundedInvocationError, match="source_invalid"):
        await invoke_bounded(
            service,
            authorization,
            policy,
            actor=development_target_session_operator(
                "subject.connector-independent-bounded-invoker"
            ),
        )

    assert authorizer.calls == []
    assert getattr(adapter, "calls", []) in ([], 0)


@pytest.mark.asyncio
async def test_bounded_invocation_denies_non_human_identity() -> None:
    service, _, _, _, _, _, authorization, policy, authorizer, adapter = await bounded_fixture()
    actor = replace(
        development_target_session_operator("subject.connector-independent-bounded-invoker"),
        kind=SubjectKind.SERVICE,
    )

    with pytest.raises(ConnectorBoundedInvocationError, match="human_required"):
        await invoke_bounded(service, authorization, policy, actor=actor)

    assert authorizer.calls == []
    assert getattr(adapter, "calls", []) in ([], 0)


@pytest.mark.asyncio
async def test_bounded_invocation_atomically_rejects_a_concurrent_second_claim() -> None:
    adapter = BlockingAdapter()
    service, _, _, _, _, _, authorization, policy, _, _ = await bounded_fixture(adapter=adapter)
    first = asyncio.create_task(
        invoke_bounded(service, authorization, policy, key="bounded-concurrent-first")
    )
    await adapter.started.wait()

    with pytest.raises(ConnectorBoundedInvocationError, match="idempotency_conflict"):
        await invoke_bounded(
            service,
            authorization,
            policy,
            key="bounded-concurrent-second",
        )

    adapter.release.set()
    record = await first
    assert record.authorization_consumed
    assert record.capability_invoked
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_bounded_invocation_rejects_actor_reuse_and_permission_before_claim() -> None:
    service, _, _, _, _, _, authorization, policy, _, _ = await bounded_fixture()
    with pytest.raises(ConnectorBoundedInvocationError, match="separation_required"):
        await invoke_bounded(
            service,
            authorization,
            policy,
            actor=target_session_operator(authorization.authorized_by),
        )
    assert (
        await service.repository.get_claim_by_authorization_in_scope(
            source_authorization_id=authorization.authorization_id,
            organization_id=authorization.organization_id,
            environment_id=authorization.environment_id,
        )
        is None
    )

    denied_service, _, _, _, _, _, authorization, policy, _, _ = await bounded_fixture(
        permission_authorizer=RecordingPermissionAuthorizer(deny=True)
    )
    with pytest.raises(ConnectorBoundedInvocationError, match="permission_denied"):
        await invoke_bounded(denied_service, authorization, policy)
    assert (
        await denied_service.repository.get_claim_by_authorization_in_scope(
            source_authorization_id=authorization.authorization_id,
            organization_id=authorization.organization_id,
            environment_id=authorization.environment_id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_bounded_invocation_uncertain_or_invalid_receipt_consumes_without_retry() -> None:
    uncertain = UncertainAdapter()
    service, _, _, _, _, _, authorization, policy, _, _ = await bounded_fixture(adapter=uncertain)
    with pytest.raises(ConnectorBoundedInvocationUncertainError, match="outcome_uncertain"):
        await invoke_bounded(service, authorization, policy)
    with pytest.raises(ConnectorBoundedInvocationError, match="authorization_consumed"):
        await invoke_bounded(service, authorization, policy)
    assert uncertain.calls == 1

    altered = AlteredReceiptAdapter(clock=lambda: authorization.authorized_at)
    (
        altered_service,
        _,
        _,
        _,
        _,
        _,
        altered_authorization,
        altered_policy,
        _,
        _,
    ) = await bounded_fixture(adapter=altered)
    with pytest.raises(ConnectorBoundedInvocationUncertainError, match="receipt_invalid"):
        await invoke_bounded(altered_service, altered_authorization, altered_policy)
    assert (
        await altered_service.repository.get_by_authorization_in_scope(
            source_authorization_id=altered_authorization.authorization_id,
            organization_id=altered_authorization.organization_id,
            environment_id=altered_authorization.environment_id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_bounded_invocation_claim_audit_failure_consumes_without_adapter_call() -> None:
    service, _, _, _, _, _, authorization, policy, _, adapter = await bounded_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(ConnectorBoundedInvocationUncertainError, match="post_claim"):
        await invoke_bounded(service, authorization, policy)
    assert (
        await service.repository.get_claim_by_authorization_in_scope(
            source_authorization_id=authorization.authorization_id,
            organization_id=authorization.organization_id,
            environment_id=authorization.environment_id,
        )
        is not None
    )
    assert (
        await service.repository.get_by_authorization_in_scope(
            source_authorization_id=authorization.authorization_id,
            organization_id=authorization.organization_id,
            environment_id=authorization.environment_id,
        )
        is None
    )
    assert isinstance(adapter, SyntheticConnectorBoundedInvocationAdapter)
    assert len(adapter.calls) == 0
    assert (
        await service.list_options(
            actor=target_session_operator("subject.connector-independent-bounded-invoker"),
            source_authorization_id=authorization.authorization_id,
            correlation_id="cor_bounded_invocation_claim_audit_options",
        )
        == ()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("audit_sink", "repository"),
    (
        (FailThirdAuditSink(), None),
        (None, PublishUncertainRepository()),
    ),
)
async def test_bounded_invocation_completion_failures_are_uncertain_and_not_retryable(
    audit_sink: FailThirdAuditSink | None,
    repository: PublishUncertainRepository | None,
) -> None:
    service, _, _, _, _, _, authorization, policy, _, adapter = await bounded_fixture(
        audit_sink=audit_sink,
        repository=repository,
    )

    with pytest.raises(ConnectorBoundedInvocationUncertainError, match="post_claim"):
        await invoke_bounded(service, authorization, policy)
    with pytest.raises(ConnectorBoundedInvocationError, match="authorization_consumed"):
        await invoke_bounded(service, authorization, policy)

    assert isinstance(adapter, SyntheticConnectorBoundedInvocationAdapter)
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_bounded_invocation_options_are_exact_server_provided_and_consumed_once() -> None:
    service, _, _, _, _, _, authorization, policy, authorizer, adapter = await bounded_fixture()
    actor = target_session_operator("subject.connector-independent-bounded-invoker")

    options = await service.list_options(
        actor=actor,
        source_authorization_id=authorization.authorization_id,
        correlation_id="cor_bounded_invocation_options",
    )

    assert len(options) == 1
    option = options[0]
    assert option.source_authorization_id == authorization.authorization_id
    assert option.source_authorization_digest == authorization.canonical_digest
    assert option.package_digest == authorization.package_digest
    assert option.capability_id == authorization.capability_id
    assert option.capability_class == authorization.capability_class
    assert option.capability_class in {"C0", "C1"}
    assert option.required_permission == authorization.required_permission
    assert option.invocation_policy_id == policy.policy_id
    assert option.invocation_policy_digest == policy.canonical_digest
    assert option.invocation_policy_version == policy.policy_version
    assert option.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert option.maximum_timeout_seconds == min(
        authorization.maximum_timeout_seconds,
        policy.maximum_invocation_duration_seconds,
    )
    assert option.maximum_output_bytes == min(
        authorization.maximum_output_bytes,
        policy.maximum_output_bytes,
    )
    assert option.maximum_observations == policy.maximum_observations

    record = await invoke_bounded(service, authorization, policy, actor=actor)

    assert (
        await service.list_options(
            actor=actor,
            source_authorization_id=authorization.authorization_id,
            correlation_id="cor_bounded_invocation_options_consumed",
        )
        == ()
    )
    assert await service.list_invocations(
        actor=actor,
        source_authorization_id=authorization.authorization_id,
        correlation_id="cor_bounded_invocation_inventory",
    ) == (record,)
    assert isinstance(adapter, SyntheticConnectorBoundedInvocationAdapter)
    assert len(adapter.calls) == 1
    assert len(authorizer.calls) == 4


@pytest.mark.asyncio
async def test_bounded_invocation_uncertain_claim_removes_options_without_adapter_retry() -> None:
    adapter = UncertainAdapter()
    service, _, _, _, _, _, authorization, policy, _, _ = await bounded_fixture(adapter=adapter)
    actor = target_session_operator("subject.connector-independent-bounded-invoker")

    assert (
        len(
            await service.list_options(
                actor=actor,
                source_authorization_id=authorization.authorization_id,
                correlation_id="cor_bounded_invocation_uncertain_options_before",
            )
        )
        == 1
    )
    with pytest.raises(ConnectorBoundedInvocationUncertainError, match="outcome_uncertain"):
        await invoke_bounded(service, authorization, policy, actor=actor)

    assert (
        await service.list_options(
            actor=actor,
            source_authorization_id=authorization.authorization_id,
            correlation_id="cor_bounded_invocation_uncertain_options_after",
        )
        == ()
    )
    with pytest.raises(ConnectorBoundedInvocationError, match="authorization_consumed"):
        await invoke_bounded(service, authorization, policy, actor=actor)
    assert adapter.calls == 1


@pytest.mark.asyncio
async def test_bounded_invocation_inventory_is_tenant_scoped_and_revalidates_permission() -> None:
    service, _, _, _, _, _, authorization, policy, authorizer, adapter = await bounded_fixture()
    actor = target_session_operator("subject.connector-independent-bounded-invoker")
    record = await invoke_bounded(service, authorization, policy, actor=actor)
    foreign_actor = replace(actor, organization_id="organization.foreign")

    assert (
        await service.list_invocations(
            actor=foreign_actor,
            source_authorization_id=None,
            correlation_id="cor_bounded_invocation_foreign_list",
        )
        == ()
    )
    assert (
        await service.list_invocations(
            actor=foreign_actor,
            source_authorization_id=authorization.authorization_id,
            correlation_id="cor_bounded_invocation_foreign_filtered_list",
        )
        == ()
    )
    with pytest.raises(ConnectorBoundedInvocationError, match="record_not_found"):
        await service.get(
            actor=foreign_actor,
            invocation_id=record.invocation_id,
            correlation_id="cor_bounded_invocation_foreign_get",
        )

    authorizer.deny = True
    with pytest.raises(ConnectorBoundedInvocationError, match="permission_denied"):
        await service.get(
            actor=actor,
            invocation_id=record.invocation_id,
            correlation_id="cor_bounded_invocation_revoked_get",
        )
    with pytest.raises(ConnectorBoundedInvocationError, match="permission_denied"):
        await service.list_invocations(
            actor=actor,
            source_authorization_id=None,
            correlation_id="cor_bounded_invocation_revoked_list",
        )
    assert isinstance(adapter, SyntheticConnectorBoundedInvocationAdapter)
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_bounded_invocation_postgres_round_trip_excludes_sensitive_material() -> None:
    service, _, _, _, _, _, authorization, policy, _, _ = await bounded_fixture()
    record = await invoke_bounded(service, authorization, policy)
    claim = await service.repository.get_claim_by_authorization_in_scope(
        source_authorization_id=authorization.authorization_id,
        organization_id=authorization.organization_id,
        environment_id=authorization.environment_id,
    )
    assert claim is not None
    raw_claim = ConnectorBoundedInvocationService._normalize(asdict(claim))
    raw_record = ConnectorBoundedInvocationService._normalize(asdict(record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert PostgreSQLConnectorBoundedInvocationRepository._claim_to_domain(raw_claim) == claim
    assert PostgreSQLConnectorBoundedInvocationRepository._record_to_domain(raw_record) == record
    rendered = repr((raw_claim, raw_record)).lower()
    for hidden in (
        "raw_input",
        "input_values",
        "raw_output",
        "target_address",
        "target_endpoint",
        "target_port",
        "credential_profile_id",
        "secret_reference_id",
        "secret_store_profile_id",
        "broker_id",
        "lease_handle",
        "session_handle",
        "command",
        "password",
        "access_token",
        "idempotency_key",
    ):
        assert hidden not in rendered


@pytest.mark.asyncio
async def test_bounded_invocation_memory_allows_one_completion_per_scoped_claim() -> None:
    service, _, _, _, _, _, authorization, policy, _, _ = await bounded_fixture()
    record = await invoke_bounded(service, authorization, policy)
    duplicate = replace(
        record,
        invocation_id="connector-bounded-invocation.duplicate-claim",
        source_authorization_id="connector-invocation-authorization.duplicate-claim",
        canonical_digest="0" * 64,
    )
    duplicate = replace(
        duplicate,
        canonical_digest=service._digest(service._record_payload(duplicate)),
    )

    assert not await service.repository.add(duplicate)


@pytest.mark.asyncio
async def test_live_postgres_bounded_invocation_isolates_same_identifiers_by_tenant() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    service, _, _, _, _, _, authorization, policy, _, _ = await bounded_fixture()
    base_record = await invoke_bounded(service, authorization, policy)
    base_claim = await service.repository.get_claim_by_authorization_in_scope(
        source_authorization_id=authorization.authorization_id,
        organization_id=authorization.organization_id,
        environment_id=authorization.environment_id,
    )
    assert base_claim is not None
    suffix = uuid4().hex[:12]
    source_id = f"connector-invocation-authorization.scoped-{suffix}"

    first_claim = replace(
        base_claim,
        claim_id=f"connector-invocation-consumption-claim.first-{suffix}",
        source_authorization_id=source_id,
        invocation_id=f"connector-bounded-invocation.first-{suffix}",
        canonical_digest="0" * 64,
    )
    first_claim = replace(
        first_claim,
        canonical_digest=service._digest(service._claim_payload(first_claim)),
    )
    second_claim = replace(
        first_claim,
        organization_id="organization.foreign",
        canonical_digest="0" * 64,
    )
    second_claim = replace(
        second_claim,
        canonical_digest=service._digest(service._claim_payload(second_claim)),
    )
    first_record = replace(
        base_record,
        invocation_id=first_claim.invocation_id,
        consumption_claim_id=first_claim.claim_id,
        source_authorization_id=source_id,
        canonical_digest="0" * 64,
    )
    first_record = replace(
        first_record,
        canonical_digest=service._digest(service._record_payload(first_record)),
    )
    second_record = replace(
        first_record,
        organization_id=second_claim.organization_id,
        canonical_digest="0" * 64,
    )
    second_record = replace(
        second_record,
        canonical_digest=service._digest(service._record_payload(second_record)),
    )

    first_engine = create_async_engine(database_url)
    second_engine = create_async_engine(database_url)
    first_repository = PostgreSQLConnectorBoundedInvocationRepository(first_engine)
    second_repository = PostgreSQLConnectorBoundedInvocationRepository(second_engine)
    try:
        assert await first_repository.claim(first_claim)
        assert await second_repository.claim(second_claim)
        assert await first_repository.add(first_record)
        assert await second_repository.add(second_record)
        assert (
            await first_repository.get_by_authorization_in_scope(
                source_authorization_id=source_id,
                organization_id=first_record.organization_id,
                environment_id=first_record.environment_id,
            )
            == first_record
        )
        assert (
            await second_repository.get_by_authorization_in_scope(
                source_authorization_id=source_id,
                organization_id=second_record.organization_id,
                environment_id=second_record.environment_id,
            )
            == second_record
        )
        first_scope = await first_repository.list_scope(
            organization_id=first_record.organization_id,
            environment_id=first_record.environment_id,
        )
        assert first_record in first_scope
        assert second_record not in first_scope
        assert (
            await second_repository.get_in_scope(
                invocation_id=first_record.invocation_id,
                organization_id=second_record.organization_id,
                environment_id=second_record.environment_id,
            )
            == second_record
        )
        assert (
            await second_repository.get_in_scope(
                invocation_id=first_record.invocation_id,
                organization_id="organization.missing",
                environment_id=second_record.environment_id,
            )
            is None
        )
    finally:
        async with first_engine.begin() as connection:
            await connection.execute(
                delete(ConnectorBoundedInvocationModel).where(
                    ConnectorBoundedInvocationModel.source_authorization_id == source_id
                )
            )
            await connection.execute(
                delete(ConnectorInvocationConsumptionClaimModel).where(
                    ConnectorInvocationConsumptionClaimModel.source_authorization_id == source_id
                )
            )
        await first_repository.close()
        await second_repository.close()


def test_live_postgres_populated_legacy_invocation_migration_preserves_digests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    monkeypatch.setenv("ATLAS_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    suffix = uuid4().hex[:12]
    organization_id = f"organization.legacy-{suffix}"
    environment_id = "environment.development"
    claim_id = f"connector-invocation-consumption-claim.legacy-{suffix}"
    invocation_id = f"connector-bounded-invocation.legacy-{suffix}"
    evidence_claim_id = f"connector-invocation-evidence-claim.legacy-{suffix}"
    ingestion_id = f"connector-invocation-evidence-ingestion.legacy-{suffix}"
    expected_digests = {
        "connector_invocation_consumption_claims": "1" * 64,
        "connector_bounded_invocations": "2" * 64,
        "connector_invocation_evidence_claims": "3" * 64,
        "connector_invocation_evidence_ingestions": "4" * 64,
    }
    engine = create_engine(database_url)
    command.downgrade(config, "20260824_0161")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO connector_invocation_consumption_claims "
                    "(claim_id, source_authorization_id, invocation_id, claimed_by, "
                    "idempotency_digest, organization_id, environment_id, canonical_digest, "
                    "payload) VALUES (:claim_id, :source_id, :invocation_id, :actor, :idem, "
                    ":organization_id, :environment_id, :digest, CAST(:payload AS JSONB))"
                ),
                {
                    "claim_id": claim_id,
                    "source_id": f"connector-invocation-authorization.legacy-{suffix}",
                    "invocation_id": invocation_id,
                    "actor": f"subject.legacy-{suffix}",
                    "idem": "5" * 64,
                    "organization_id": organization_id,
                    "environment_id": environment_id,
                    "digest": expected_digests["connector_invocation_consumption_claims"],
                    "payload": json.dumps({"legacy": "bounded-claim"}),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO connector_bounded_invocations "
                    "(invocation_id, consumption_claim_id, source_authorization_id, instance_id, "
                    "capability_id, invoked_by, organization_id, environment_id, "
                    "canonical_digest, payload) VALUES (:invocation_id, :claim_id, :source_id, "
                    ":instance_id, :capability_id, :actor, :organization_id, :environment_id, "
                    ":digest, CAST(:payload AS JSONB))"
                ),
                {
                    "invocation_id": invocation_id,
                    "claim_id": claim_id,
                    "source_id": f"connector-invocation-authorization.legacy-{suffix}",
                    "instance_id": f"connector-instance.legacy-{suffix}",
                    "capability_id": "storage.health.read",
                    "actor": f"subject.legacy-{suffix}",
                    "organization_id": organization_id,
                    "environment_id": environment_id,
                    "digest": expected_digests["connector_bounded_invocations"],
                    "payload": json.dumps({"legacy": "bounded-completion"}),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO connector_invocation_evidence_claims "
                    "(claim_id, source_invocation_id, ingestion_id, claimed_by, "
                    "idempotency_digest, organization_id, environment_id, canonical_digest, "
                    "payload) VALUES (:claim_id, :invocation_id, :ingestion_id, :actor, :idem, "
                    ":organization_id, :environment_id, :digest, CAST(:payload AS JSONB))"
                ),
                {
                    "claim_id": evidence_claim_id,
                    "invocation_id": invocation_id,
                    "ingestion_id": ingestion_id,
                    "actor": f"subject.evidence-{suffix}",
                    "idem": "6" * 64,
                    "organization_id": organization_id,
                    "environment_id": environment_id,
                    "digest": expected_digests["connector_invocation_evidence_claims"],
                    "payload": json.dumps({"legacy": "evidence-claim"}),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO connector_invocation_evidence_ingestions "
                    "(ingestion_id, claim_id, source_invocation_id, instance_id, capability_id, "
                    "evidence_package_id, ingested_by, organization_id, environment_id, "
                    "canonical_digest, payload) VALUES (:ingestion_id, :claim_id, :invocation_id, "
                    ":instance_id, :capability_id, :package_id, :actor, :organization_id, "
                    ":environment_id, :digest, CAST(:payload AS JSONB))"
                ),
                {
                    "ingestion_id": ingestion_id,
                    "claim_id": evidence_claim_id,
                    "invocation_id": invocation_id,
                    "instance_id": f"connector-instance.legacy-{suffix}",
                    "capability_id": "storage.health.read",
                    "package_id": f"evidence-package.legacy-{suffix}",
                    "actor": f"subject.evidence-{suffix}",
                    "organization_id": organization_id,
                    "environment_id": environment_id,
                    "digest": expected_digests["connector_invocation_evidence_ingestions"],
                    "payload": json.dumps({"legacy": "evidence-ingestion"}),
                },
            )

        command.upgrade(config, "head")
        with engine.connect() as connection:
            for table, expected in expected_digests.items():
                actual = connection.execute(
                    text(
                        f"SELECT canonical_digest FROM {table} "
                        "WHERE organization_id = :organization_id "
                        "AND environment_id = :environment_id"
                    ),
                    {
                        "organization_id": organization_id,
                        "environment_id": environment_id,
                    },
                ).scalar_one()
                assert actual == expected
        inspector = inspect(engine)
        expected_primary_keys = {
            "connector_invocation_consumption_claims": "claim_id",
            "connector_bounded_invocations": "invocation_id",
            "connector_invocation_evidence_claims": "claim_id",
            "connector_invocation_evidence_ingestions": "ingestion_id",
        }
        for table, identifier in expected_primary_keys.items():
            assert inspector.get_pk_constraint(table)["constrained_columns"] == [
                identifier,
                "organization_id",
                "environment_id",
            ]
    finally:
        with engine.begin() as connection:
            for table in reversed(tuple(expected_digests)):
                connection.execute(
                    text(f"DELETE FROM {table} WHERE organization_id = :organization_id"),
                    {"organization_id": organization_id},
                )
        command.upgrade(config, "head")
        engine.dispose()


def test_bounded_invocation_api_is_csrf_protected_forbids_controls_and_is_minimized(
    tmp_path: Path,
) -> None:
    (
        service,
        authorization_service,
        target_service,
        runtime_service,
        brokerage_service,
        runtime_fixture,
        authorization,
        policy,
        _,
        _,
    ) = asyncio.run(bounded_fixture())
    (
        runtime_trust_service,
        enablement_service,
        validation_service,
        assignment_service,
        target_configuration_service,
        instance_service,
        installation_service,
        registration_service,
        *_rest,
    ) = runtime_fixture
    subject = development_target_session_operator("subject.connector-independent-bounded-invoker")
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.connector-bounded-invocation-input.v1",
        "source_authorization_id": authorization.authorization_id,
        "source_authorization_digest": authorization.canonical_digest,
        "package_digest": authorization.package_digest,
        "invocation_policy_id": policy.policy_id,
        "invocation_policy_digest": policy.canonical_digest,
        "purpose": "Invoke one authorized read-only capability and close every ephemeral resource.",
        ACKNOWLEDGEMENT_FIELD: True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_registration_service=registration_service,
            package_installation_service=installation_service,
            connector_instance_creation_service=instance_service,
            target_configuration_service=target_configuration_service,
            credential_assignment_service=assignment_service,
            configuration_validation_service=validation_service,
            capability_enablement_service=enablement_service,
            runtime_trust_service=runtime_trust_service,
            secret_brokerage_service=brokerage_service,
            runtime_activation_service=runtime_service,
            target_session_service=target_service,
            invocation_authorization_service=authorization_service,
            bounded_invocation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/bounded-invocations"
        options_before = client.get(
            f"{endpoint}/options",
            params={"source_authorization_id": authorization.authorization_id},
        )
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "bounded-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "command": "show storage health"},
            headers={
                "Idempotency-Key": "bounded-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "bounded-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        invocation_id = created.json()["data"]["invocation_id"]
        read = client.get(f"{endpoint}/{invocation_id}")
        inventory = client.get(endpoint)
        filtered_inventory = client.get(
            endpoint,
            params={"source_authorization_id": authorization.authorization_id},
        )
        options_after = client.get(
            f"{endpoint}/options",
            params={"source_authorization_id": authorization.authorization_id},
        )

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert options_before.status_code == 200, options_before.text
    assert read.status_code == inventory.status_code == filtered_inventory.status_code == 200
    assert options_after.status_code == 200
    assert {
        created.headers["Cache-Control"],
        read.headers["Cache-Control"],
        inventory.headers["Cache-Control"],
        filtered_inventory.headers["Cache-Control"],
        options_before.headers["Cache-Control"],
        options_after.headers["Cache-Control"],
    } == {"no-store"}
    option_data = options_before.json()["data"]
    assert len(option_data) == 1
    assert set(option_data[0]) == OPTION_API_FIELDS
    assert option_data[0]["capability_id"] == authorization.capability_id
    assert option_data[0]["capability_class"] == authorization.capability_class
    assert option_data[0]["capability_class"] in {"C0", "C1"}
    assert option_data[0]["required_assurance_level"] == "single_factor"
    assert option_data[0]["irreversible_consumption_required"] is True
    assert option_data[0]["automatic_retry_allowed"] is False
    assert option_data[0]["target_connected"] is False
    assert option_data[0]["reusable_session_available"] is False
    assert option_data[0]["scheduled"] is False
    assert option_data[0]["evidence_ingested"] is False
    assert option_data[0]["execution_authorized"] is False
    assert option_data[0]["deployment_approved"] is False
    assert option_data[0]["infrastructure_mutation_performed"] is False
    assert options_after.json()["data"] == []
    data = created.json()["data"]
    assert set(data) == COMPLETION_API_FIELDS
    assert set(read.json()["data"]) == COMPLETION_API_FIELDS
    assert inventory.json()["data"] == [data]
    assert filtered_inventory.json()["data"] == [data]
    assert data["authorization_consumed"] is True
    assert data["capability_invoked"] is True and data["result_validated"] is True
    assert data["target_connected"] is False and data["evidence_ingested"] is False
    rendered = " ".join(
        (
            created.text,
            read.text,
            inventory.text,
            filtered_inventory.text,
            options_before.text,
            options_after.text,
        )
    ).lower()
    for hidden in (
        "organization_id",
        "environment_id",
        "consumption_claim_id",
        "connector_id",
        "release_version",
        "manifest_digest",
        "instance_id",
        "instance_key",
        "display_name",
        "invocation_profile_id",
        "input_envelope_id",
        "input_schema_digest",
        "invocation_adapter_id",
        "invoked_by",
        "purpose",
        "raw_input",
        "input_values",
        "raw_output",
        "target_address",
        "target_endpoint",
        "target_port",
        "credential_profile_id",
        "secret_reference_id",
        "secret_store_profile_id",
        "broker_id",
        "lease_handle",
        "session_handle",
        "request_binding_digest",
        "idempotency_digest",
        "idempotency_key",
        "password",
        "access_token",
        "command",
        "handler",
        "target_selector",
    ):
        assert hidden not in rendered
