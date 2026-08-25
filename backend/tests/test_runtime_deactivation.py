from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import TypedDict, cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import (
    activate_runtime,
    runtime_activation_fixture,
    runtime_activation_operator,
)

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.runtime_deactivation_memory import (
    InMemoryConnectorRuntimeDeactivationRepository,
)
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
)
from atlas.modules.connectors.application.runtime_activation_ports import (
    ConnectorRuntimeActivationError,
)
from atlas.modules.connectors.application.runtime_deactivation import (
    ConnectorRuntimeDeactivationService,
)
from atlas.modules.connectors.application.runtime_deactivation_ports import (
    ConnectorRuntimeDeactivationError,
)
from atlas.modules.connectors.domain.runtime_activation import ConnectorRuntimeActivationRecord
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind

ACKNOWLEDGEMENT_FIELD = "acknowledged_runtime_only_deactivation"


class DeactivationArguments(TypedDict):
    actor: AuthenticatedSubject
    activation_id: str
    expected_activation_version: int | None
    expected_activation_digest: str | None
    reason: str
    runtime_only_acknowledged: bool
    idempotency_key: str
    correlation_id: str


class FailingAuditSink:
    async def record(self, event: object) -> None:
        del event
        raise RuntimeError("audit unavailable")


async def deactivation_fixture(
    *, audit_sink: CollectingAuditSink | FailingAuditSink | None = None
) -> tuple[
    ConnectorRuntimeActivationService,
    ConnectorRuntimeDeactivationService,
    ConnectorRuntimeActivationRecord,
    ConnectorRuntimeTrustGrantRecord,
]:
    (
        activation_service,
        _,
        _,
        runtime_trust,
        brokerage,
        profile,
        policy,
        _,
    ) = await runtime_activation_fixture()
    activation = await activate_runtime(activation_service, brokerage, profile, policy)
    repository = InMemoryConnectorRuntimeDeactivationRepository()
    service = ConnectorRuntimeDeactivationService(
        repository=repository,
        activation_source=activation_service,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=runtime_trust.environment_id,
        clock=lambda: runtime_trust.granted_at,
    )
    activation_service.bind_deactivation_source(repository)
    return activation_service, service, activation, runtime_trust


@pytest.mark.asyncio
async def test_runtime_deactivation_is_immutable_idempotent_and_blocks_runtime_use() -> None:
    audit = CollectingAuditSink()
    activation_service, service, activation, _ = await deactivation_fixture(audit_sink=audit)
    actor = runtime_activation_operator()
    kwargs: DeactivationArguments = {
        "actor": actor,
        "activation_id": activation.activation_id,
        "expected_activation_version": activation.version,
        "expected_activation_digest": None,
        "reason": "Disable this Atlas connector runtime for scheduled operator maintenance.",
        "runtime_only_acknowledged": True,
        "idempotency_key": "runtime-deactivation-001",
        "correlation_id": "cor_runtime_deactivation",
    }

    first, repeated = await asyncio.gather(service.create(**kwargs), service.create(**kwargs))

    assert first.deactivation_id == repeated.deactivation_id
    assert first.reused is not repeated.reused
    assert first.activation_digest == activation.canonical_digest
    assert first.atlas_runtime_disabled is True
    assert first.target_authority_revoked is True
    assert first.managed_infrastructure_contacted is False
    assert first.infrastructure_mutation_performed is False
    assert (
        await activation_service.repository.get(activation_id=activation.activation_id)
        == activation
    )
    with pytest.raises(ConnectorRuntimeActivationError, match="runtime_activation_deactivated"):
        await activation_service.target_session_source(activation_id=activation.activation_id)
    assert await activation_service.list_activations(
        actor=actor,
        source_brokerage_authorization_id=None,
        correlation_id="cor_runtime_activation_history",
    ) == (activation,)
    with pytest.raises(ConnectorRuntimeDeactivationError, match="idempotency_conflict"):
        await service.create(
            **cast(
                DeactivationArguments,
                {
                    **kwargs,
                    "reason": (
                        "Disable this Atlas connector runtime for a different reviewed reason."
                    ),
                },
            )
        )
    assert {record.result_code for record in audit.records} >= {
        "connector_runtime_deactivation_requested",
        "connector_runtime_deactivated",
    }


@pytest.mark.asyncio
async def test_runtime_deactivation_enforces_preconditions_scope_human_and_acknowledgement() -> (
    None
):
    _, service, activation, _ = await deactivation_fixture()
    actor = runtime_activation_operator()
    base: DeactivationArguments = {
        "actor": actor,
        "activation_id": activation.activation_id,
        "expected_activation_version": activation.version,
        "expected_activation_digest": None,
        "reason": "Disable this Atlas connector runtime after an operator review.",
        "runtime_only_acknowledged": True,
        "idempotency_key": "runtime-deactivation-guard-001",
        "correlation_id": "cor_runtime_deactivation_guards",
    }
    cases = (
        ({"runtime_only_acknowledged": False}, "acknowledgement_required"),
        ({"expected_activation_version": 2}, "activation_conflict"),
        (
            {"expected_activation_version": None, "expected_activation_digest": "f" * 64},
            "activation_conflict",
        ),
        ({"actor": replace(actor, organization_id="org.foreign")}, "activation_not_found"),
        ({"actor": replace(actor, kind=SubjectKind.SERVICE)}, "human_required"),
    )
    for changes, expected in cases:
        with pytest.raises(ConnectorRuntimeDeactivationError, match=expected):
            await service.create(**cast(DeactivationArguments, {**base, **changes}))


@pytest.mark.asyncio
async def test_runtime_deactivation_fails_closed_when_audit_is_unavailable() -> None:
    _, service, activation, _ = await deactivation_fixture(audit_sink=FailingAuditSink())
    with pytest.raises(ConnectorRuntimeDeactivationError, match="audit_failed"):
        await service.create(
            actor=runtime_activation_operator(),
            activation_id=activation.activation_id,
            expected_activation_version=activation.version,
            expected_activation_digest=None,
            reason="Disable this Atlas connector runtime after an operator review.",
            runtime_only_acknowledged=True,
            idempotency_key="runtime-deactivation-audit-001",
            correlation_id="cor_runtime_deactivation_audit",
        )
    assert (
        await service.repository.get_by_activation_in_scope(
            activation_id=activation.activation_id,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
        )
        is None
    )


def test_runtime_deactivation_api_is_csrf_protected_scoped_and_minimized(
    tmp_path: Path,
) -> None:
    activation_service, service, activation, _ = asyncio.run(deactivation_fixture())
    subject = runtime_activation_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-runtime-deactivation-input.v1",
        "expected_activation_digest": activation.canonical_digest,
        "reason": "Disable this Atlas connector runtime after an operator review.",
        ACKNOWLEDGEMENT_FIELD: True,
    }
    endpoint = f"/api/v1/connectors/runtime-activations/{activation.activation_id}/deactivations"
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            runtime_activation_service=activation_service,
            runtime_deactivation_service=service,
        )
    ) as client:
        login_response = login(client)
        denied = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "runtime-deactivation-api-001"},
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "runtime-deactivation-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        repeated = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "runtime-deactivation-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        inventory = client.get("/api/v1/connectors/runtime-activations/deactivations")
        nested_inventory = client.get(endpoint)
        activation_inventory = client.get("/api/v1/connectors/runtime-activations")

    assert denied.status_code == 403
    assert created.status_code == repeated.status_code == 201
    assert created.json()["data"]["reused"] is False
    assert repeated.json()["data"]["reused"] is True
    assert inventory.status_code == nested_inventory.status_code == 200
    assert activation_inventory.status_code == 200
    assert activation_inventory.json()["data"][0]["activation_id"] == activation.activation_id
    assert inventory.json()["data"] == nested_inventory.json()["data"]
    assert inventory.json()["data"][0]["effective_runtime_state"] == "disabled_runtime"
    assert created.headers["Cache-Control"] == inventory.headers["Cache-Control"] == "no-store"
    rendered = created.text.lower()
    for hidden in (
        "activation_digest",
        "request_fingerprint",
        "idempotency_digest",
        "idempotency-key",
        "credential",
        "password",
        "access_token",
    ):
        assert hidden not in rendered
