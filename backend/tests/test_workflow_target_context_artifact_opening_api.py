from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    _assert_no_step_up_language,
    _AuditSink,
    _issue_api_token,
    _login,
    _settings,
    _workload_headers,
)
from test_workflow_target_context_access_authorization_lease_api import (
    _workload_service_and_token,
)

from atlas.api.app import create_app
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT,
)
from atlas.modules.workflows.application.target_context_artifact_opening_ports import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy,
)

ENDPOINT = "/api/v1/workflows/physical-transport-target-context-artifact-openings"
NOW = datetime(2026, 8, 15, 20, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")


def _result() -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult:
    policy = code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy()
    authority = WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority()
    values: dict[str, Any] = {
        "opening_id": "workflow-target-context-artifact-opening.api01",
        "attempt_id": "workflow-target-context-artifact-opening-attempt.api01",
        "attempt_digest": "1" * 64,
        "consumption_claim_id": "workflow-target-context-access-consumption-claim.api01",
        "consumption_claim_digest": "2" * 64,
        "authorization_lease_id": "workflow-target-context-access-lease.api01",
        "authorization_lease_digest": "3" * 64,
        "target_context_binding_id": "workflow-target-context-binding.api01",
        "target_context_binding_digest": "4" * 64,
        "target_context_commitment": "5" * 64,
        "scope": SCOPE,
        "accessor_subject_id": WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "opener_id": "opener.workflow-protected-target-context.local",
        "opener_version": "1.0",
        "opening_receipt_digest": "6" * 64,
        "state": (
            WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState.OPENED_PROTECTED
        ),
        "failure_class": None,
        "sealed_capsule_id": "capsule.workflow-target-context.api01",
        "sealed_capsule_digest": "7" * 64,
        "capsule_is_bearer_capability": False,
        "capsule_schema_id": "schema.workflow-sealed-target-context-capsule-lineage",
        "capsule_schema_version": "1.0",
        "completed_at": NOW,
        "usable_until": NOW + timedelta(seconds=2),
        "protected_sources_closed": True,
        "cleanup_confirmed": True,
        "authority": authority,
    }
    payload = {
        key: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(
                value, WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState
            )
            else value.canonical_value()
            if isinstance(
                value,
                (
                    WorkflowScope,
                    WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthority,
                ),
            )
            else value
        )
        for key, value in values.items()
    }
    return WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult(
        **values,
        canonical_digest=canonical_digest(payload),
    )


class _Service:
    durable = True

    def __init__(
        self,
        results: tuple[WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult, ...] = (),
        *,
        failure: WorkflowEventPhysicalTransportTargetContextArtifactOpeningError | None = None,
        unavailable: bool = False,
        ignore_scope: bool = False,
    ) -> None:
        self.repository = self
        self.results = list(results)
        self.failure = failure
        self.unavailable = unavailable
        self.ignore_scope = ignore_scope
        self.open_calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        if self.unavailable:
            raise RuntimeError("repository unavailable")
        return NOW + timedelta(seconds=1)

    async def list_target_context_artifact_opening_results(
        self,
        *,
        scope: WorkflowScope,
        limit: int,
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult, ...]:
        if self.unavailable:
            raise RuntimeError("repository unavailable")
        if self.ignore_scope:
            return tuple(self.results)[:limit]
        return tuple(result for result in self.results if result.scope == scope)[:limit]

    async def list_results(
        self,
        *,
        scope: WorkflowScope,
        limit: int,
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult, ...]:
        return await self.list_target_context_artifact_opening_results(
            scope=scope,
            limit=limit,
        )

    async def get_results_for_opening_ids(
        self, *, scope: WorkflowScope, opening_ids: tuple[str, ...]
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult, ...]:
        if self.unavailable:
            raise RuntimeError("repository unavailable")
        return tuple(
            result
            for result in self.results
            if result.opening_id in opening_ids and (self.ignore_scope or result.scope == scope)
        )

    async def list_attempts(
        self,
        *,
        scope: WorkflowScope,
        limit: int,
    ) -> tuple[Any, ...]:
        results = (
            self.results
            if self.ignore_scope
            else [result for result in self.results if result.scope == scope]
        )
        return tuple(
            SimpleNamespace(
                opening_id=result.opening_id,
                attempt_id=result.attempt_id,
                scope=result.scope,
                started_at=result.completed_at - timedelta(seconds=1),
                policy_id=result.policy_id,
                policy_version=result.policy_version,
                authority=result.authority,
            )
            for result in results[:limit]
        )

    async def open_artifacts(
        self, **kwargs: Any
    ) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult:
        self.open_calls.append(kwargs)
        if self.failure is not None:
            raise self.failure
        result = _result()
        if not self.results:
            self.results.append(result)
        return self.results[0]


def _payload() -> dict[str, object]:
    policy = code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy()
    return {
        "authorization_lease_id": "workflow-target-context-access-lease.api01",
        "authorization_lease_digest": "3" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "target-context-artifact-opening-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def _assert_workload_minimized(item: dict[str, Any]) -> None:
    assert set(item) == {
        "opening_id",
        "result_digest",
        "state",
        "completed_at",
        "usable_until",
        "authority",
    }
    assert item["state"] == "opened_protected"
    assert len(item["result_digest"]) == 64
    assert len(item["authority"]) == 17
    assert all(value is False for value in item["authority"].values())
    forbidden = {
        "authorization_lease_id",
        "idempotency_key",
        "capsule",
        "artifact",
        "attestation",
        "endpoint",
        "credential",
        "route",
        "provider",
        "fence",
        "request_fingerprint",
        "policy_digest",
        "canonical_digest",
    }
    assert not forbidden.intersection(item)


def _assert_human_minimized(item: dict[str, Any]) -> None:
    assert set(item) == {
        "opening_id",
        "scope",
        "attempt_state",
        "result_state",
        "started_at",
        "completed_at",
        "policy",
        "authority",
        "integrity_reference",
    }
    assert item["attempt_state"] == "completed"
    assert item["result_state"] == "opened_protected"
    assert item["policy"] == {
        "policy_id": "policy.workflow-event-physical-transport-target-context-artifact-opening",
        "policy_version": "1.0",
    }
    assert len(item["authority"]) == 17
    assert all(value is False for value in item["authority"].values())
    for forbidden in (
        "result_digest",
        "usable_until",
        "sealed_capsule_id",
        "artifact_id",
        "attestation_id",
        "endpoint_value",
        "credential_value",
        "route_id",
        "provider_id",
        "fencing_token",
        "idempotency_key",
    ):
        assert forbidden not in item


def test_exact_workload_post_and_password_session_get_are_minimized() -> None:
    workload_service, token = _workload_service_and_token()
    service = _Service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        workflow_event_physical_transport_target_context_artifact_opening_service=cast(
            Any, service
        ),
    )

    with TestClient(app) as client:
        unauthenticated = client.get(ENDPOINT)
        csrf = _login(client)
        empty = client.get(ENDPOINT)
        browser_post = client.post(ENDPOINT, json=_payload(), headers={"X-CSRF-Token": csrf})
        created = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
            ),
        )
        inventory = client.get(ENDPOINT)

    assert unauthenticated.status_code == 403
    assert empty.status_code == 200
    assert empty.json()["data"]["physical_transport_target_context_artifact_openings"] == []
    assert browser_post.status_code == 401
    assert browser_post.json()["code"] == "workload_authentication_failed"
    assert created.status_code == 201
    item = dict(created.json()["data"])
    _assert_workload_minimized(item)
    assert inventory.status_code == 200
    human_item = dict(
        inventory.json()["data"]["physical_transport_target_context_artifact_openings"][0]
    )
    _assert_human_minimized(human_item)
    assert inventory.json()["data"]["durable"] is True
    for response in (unauthenticated, empty, browser_post, created, inventory):
        _assert_no_store(response)
    _assert_no_step_up_language(inventory.text + browser_post.text)
    assert "authorized browser session" not in inventory.text.casefold()
    context = service.open_calls[0]["context"]
    assert context.subject_id == WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT
    assert context.credential_audience == (
        WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE
    )


def test_post_rejects_pat_wrong_audience_and_extra_fields_without_leaking_values() -> None:
    workload_service, token = _workload_service_and_token()
    service = _Service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        workflow_event_physical_transport_target_context_artifact_opening_service=cast(
            Any, service
        ),
    )
    secret_value = "capsule.private.attacker-value"

    with TestClient(app) as client:
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        pat = client.post(
            ENDPOINT,
            json=_payload(),
            headers={"Authorization": f"Bearer {personal_token}"},
        )
        wrong_audience = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(token, "audience.workflow-worker"),
        )
        extra = client.post(
            ENDPOINT,
            json={**_payload(), "sealed_capsule_id": secret_value},
            headers=_workload_headers(
                token,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
            ),
        )
        missing_irreversible_ack = client.post(
            ENDPOINT,
            json={**_payload(), "irreversible_consumption_acknowledged": False},
            headers=_workload_headers(
                token,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
            ),
        )
        missing_uncertain_ack = client.post(
            ENDPOINT,
            json={
                **_payload(),
                "uncertain_outcome_requires_new_authorization_acknowledged": False,
            },
            headers=_workload_headers(
                token,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
            ),
        )

    for denied in (pat, wrong_audience):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_store(denied)
        _assert_no_step_up_language(denied.text)
    assert extra.status_code == 422
    assert secret_value not in extra.text
    _assert_no_store(extra)
    for missing_ack in (missing_irreversible_ack, missing_uncertain_ack):
        assert missing_ack.status_code == 422
        _assert_no_store(missing_ack)


def test_post_maps_internal_failures_to_one_non_oracle_error() -> None:
    workload_service, token = _workload_service_and_token()
    service = _Service(
        failure=WorkflowEventPhysicalTransportTargetContextArtifactOpeningError(
            "target_context_artifact_opening_lease_not_found"
        )
    )
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        workflow_event_physical_transport_target_context_artifact_opening_service=cast(
            Any, service
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
            ),
        )

    assert response.status_code == 409
    assert response.json()["code"] == "workflow_target_context_artifact_opening_unavailable"
    assert response.json()["retryable"] is False
    assert "not_found" not in response.text
    assert "authorization_lease_id" not in response.text
    _assert_no_store(response)


def test_get_fails_closed_for_repository_errors_and_scope_escape() -> None:
    cases = (
        _Service(unavailable=True),
        _Service(results=(_result(),), ignore_scope=True),
    )
    for service in cases:
        app = create_app(
            _settings().model_copy(update={"development_organization_id": "organization.other"}),
            audit_sink=_AuditSink(),
            workflow_event_physical_transport_target_context_artifact_opening_service=cast(
                Any, service
            ),
        )
        with TestClient(app) as client:
            _login(client)
            response = client.get(ENDPOINT)

        assert response.status_code == 503
        assert response.json()["code"] == (
            "workflow_target_context_artifact_opening_service_unavailable"
        )
        _assert_no_store(response)


def test_default_composition_has_no_memory_or_available_opener_fallback() -> None:
    workload_service, token = _workload_service_and_token()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )

    with TestClient(app) as client:
        _login(client)
        inventory = client.get(ENDPOINT)
        opening = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
            ),
        )

    assert inventory.status_code == 503
    assert inventory.json()["code"] == (
        "workflow_target_context_artifact_opening_service_unavailable"
    )
    assert opening.status_code == 409
    assert opening.json()["code"] == "workflow_target_context_artifact_opening_unavailable"
    for response in (inventory, opening):
        _assert_no_store(response)
        _assert_no_step_up_language(response.text)
