from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_invocation_authorization import (
    authorize_invocation,
    invocation_fixture,
)
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import FailSecondAuditSink
from test_secret_brokerage import RuntimeFixture
from test_target_session import target_session_operator

from atlas.api.app import create_app
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
from atlas.modules.identity.domain.models import AuthenticatedSubject

ACKNOWLEDGEMENT_FIELD = (
    "acknowledged_authorization_is_consumed_once_without_retry_on_uncertain_outcome"
)


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


async def bounded_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    permission_authorizer: RecordingPermissionAuthorizer | None = None,
    adapter: SyntheticConnectorBoundedInvocationAdapter
    | UncertainAdapter
    | AlteredReceiptAdapter
    | BlockingAdapter
    | None = None,
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
    authorizer = permission_authorizer or RecordingPermissionAuthorizer()
    resolved_adapter = adapter or SyntheticConnectorBoundedInvocationAdapter(
        clock=lambda: authorization.authorized_at
    )
    service = ConnectorBoundedInvocationService(
        repository=InMemoryConnectorBoundedInvocationRepository(),
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
        )
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
        await service.repository.get_claim_by_authorization(
            source_authorization_id=authorization.authorization_id
        )
        is None
    )

    denied_service, _, _, _, _, _, authorization, policy, _, _ = await bounded_fixture(
        permission_authorizer=RecordingPermissionAuthorizer(deny=True)
    )
    with pytest.raises(ConnectorBoundedInvocationError, match="permission_denied"):
        await invoke_bounded(denied_service, authorization, policy)
    assert (
        await denied_service.repository.get_claim_by_authorization(
            source_authorization_id=authorization.authorization_id
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
        await altered_service.repository.get_by_authorization(
            source_authorization_id=altered_authorization.authorization_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_bounded_invocation_claim_audit_failure_consumes_without_adapter_call() -> None:
    service, _, _, _, _, _, authorization, policy, _, adapter = await bounded_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await invoke_bounded(service, authorization, policy)
    assert (
        await service.repository.get_claim_by_authorization(
            source_authorization_id=authorization.authorization_id
        )
        is not None
    )
    assert (
        await service.repository.get_by_authorization(
            source_authorization_id=authorization.authorization_id
        )
        is None
    )
    assert isinstance(adapter, SyntheticConnectorBoundedInvocationAdapter)
    assert len(adapter.calls) == 0


@pytest.mark.asyncio
async def test_bounded_invocation_postgres_round_trip_excludes_sensitive_material() -> None:
    service, _, _, _, _, _, authorization, policy, _, _ = await bounded_fixture()
    record = await invoke_bounded(service, authorization, policy)
    claim = await service.repository.get_claim_by_authorization(
        source_authorization_id=authorization.authorization_id
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
    subject = target_session_operator("subject.connector-independent-bounded-invoker")
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

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["authorization_consumed"] is True
    assert data["capability_invoked"] is True and data["result_validated"] is True
    assert data["target_connected"] is False and data["evidence_ingested"] is False
    rendered = created.text.lower()
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
        "request_binding_digest",
        "idempotency_digest",
        "idempotency_key",
        "password",
        "access_token",
        "command",
    ):
        assert hidden not in rendered
