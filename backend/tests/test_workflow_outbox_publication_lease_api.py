from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import STORAGE_OVERVIEW_READ
from atlas.modules.conversations.application.ports import ConversationTargetAccessRequest
from atlas.modules.conversations.domain.models import (
    AuthorizedConversationTarget,
    ConversationScope,
)
from atlas.modules.identity.adapters.workload_identities import (
    InMemoryWorkloadIdentityRepository,
)
from atlas.modules.identity.application.workload_identities import WorkloadIdentityService
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.workflows.application import (
    WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
    WORKFLOW_WORKER_AUDIENCE,
)

TARGET_ID = "asset.storage.lab.vsp-g400"
WORKER_ID = "workload.atlas.workflow-worker-01"
PUBLISHER_ID = "workload.atlas.workflow-outbox-publisher-01"
OTHER_PUBLISHER_ID = "workload.atlas.workflow-outbox-publisher-02"
SCOPE = ConversationScope(
    organization_id="organization.development",
    environment_id="environment.development",
    site_id="site.local",
)


class _AuditSink:
    async def record(self, event: AuditRecord) -> None:
        return None


class _ExplicitTargetAccessSource:
    def __init__(self) -> None:
        self.authorized_subject_ids = {
            "subject.development.operator",
            WORKER_ID,
            PUBLISHER_ID,
            OTHER_PUBLISHER_ID,
        }

    async def authorized_storage_targets(
        self, request: ConversationTargetAccessRequest
    ) -> tuple[AuthorizedConversationTarget, ...]:
        if request.scope != SCOPE or request.subject_id not in self.authorized_subject_ids:
            return ()
        return (
            AuthorizedConversationTarget(
                target_id=TARGET_ID,
                display_name="VSP G400 Lab",
                description="Explicitly authorized publication lease API test target.",
            ),
        )


def _settings() -> Settings:
    return Settings(environment="development", development_identity_enabled=True)


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def _issue_api_token(client: TestClient, csrf: str) -> str:
    response = client.post(
        "/api/v1/authentication/api-credentials",
        json={
            "display_name": "Publication lease boundary reader",
            "purpose": "Prove that a valid personal API token cannot mutate publisher leases.",
            "expires_in_minutes": 30,
            "permission_ids": [STORAGE_OVERVIEW_READ],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201
    return str(response.json()["data"]["token"])


def _workload_service() -> tuple[WorkloadIdentityService, dict[str, str]]:
    service = WorkloadIdentityService(
        repository=InMemoryWorkloadIdentityRepository(),
        audit_sink=_AuditSink(),
        environment_id="environment.development",
        signing_keys={3: b"workflow-publication-lease-api-test-key" * 2},
    )
    actor = AuthenticatedSubject(
        subject_id="subject.enterprise.security-admin",
        display_name="Security Administrator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.SINGLE_FACTOR,
        authenticated_at=datetime.now(UTC),
        organization_id="organization.development",
        role_ids=("role.security-administrator",),
    )
    identities = (
        (WORKER_ID, WORKFLOW_WORKER_AUDIENCE, "workflow-worker"),
        (PUBLISHER_ID, WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE, "outbox-publisher"),
        (OTHER_PUBLISHER_ID, WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE, "outbox-publisher"),
    )
    tokens: dict[str, str] = {}
    for ordinal, (identity_id, audience, service_name) in enumerate(identities, start=1):
        issued = asyncio.run(
            service.create(
                actor=actor,
                identity_id=identity_id,
                display_name=identity_id.rsplit("-", maxsplit=1)[-1],
                service_id=f"service.{service_name}",
                instance_id=f"instance.{service_name}.local-{ordinal:02d}",
                owner_subject_id="subject.enterprise.platform-owner",
                purpose="Exercise bounded workflow coordination without operational authority.",
                audiences=(audience,),
                secret_reference_ids=(f"secret.{service_name}.local-{ordinal:02d}",),
                lifetime=timedelta(minutes=10),
                reason="Create a bounded publication lease API integration identity.",
                idempotency_key=f"publication-lease-identity-{ordinal:04d}",
                correlation_id=f"correlation.publication-lease-identity-{ordinal}",
            )
        )
        tokens[identity_id] = issued.token
    return service, tokens


def _workload_headers(token: str, audience: str) -> dict[str, str]:
    return {
        "Authorization": f"Workload {token}",
        "X-Atlas-Audience": audience,
        "X-Atlas-Environment": "environment.development",
    }


def _plan_payload() -> dict[str, object]:
    return {
        "schema_version": "atlas.workflow-run-plan-create-input.v1",
        "definition_id": "workflow.evidence-grounded-query",
        "definition_version": 1,
        "target_id": TARGET_ID,
        "target_type": "storage",
        "inputs": {
            "purpose": "Review current storage evidence.",
            "input_summary": "Use only authorized read-only observations.",
        },
        "acknowledged_planning_only_no_execution_authority": True,
    }


def _seed_dispatch_outbox_chain(
    client: TestClient, *, csrf: str, worker_token: str
) -> dict[str, Any]:
    worker_headers = _workload_headers(worker_token, WORKFLOW_WORKER_AUDIENCE)
    created = client.post(
        "/api/v1/workflows/plans",
        json=_plan_payload(),
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "publication-api-plan-0001"},
    )
    assert created.status_code == 201
    plan = created.json()["data"]
    plan_id = plan["plan_id"]

    acquired = client.post(
        f"/api/v1/workflows/plans/{plan_id}/orchestration-lease/acquisition",
        json={
            "schema_version": "atlas.workflow-orchestration-lease-acquire-input.v1",
            "plan_digest": plan["canonical_digest"],
            "target_id": TARGET_ID,
            "target_type": "storage",
            "lease_duration_seconds": 180,
            "acknowledged_coordination_only_no_execution_authority": True,
        },
        headers={**worker_headers, "Idempotency-Key": "publication-api-orchestration"},
    )
    assert acquired.status_code == 201
    orchestration_lease = acquired.json()["data"]

    materialized = client.post(
        f"/api/v1/workflows/plans/{plan_id}/materialized-run",
        json={
            "schema_version": "atlas.workflow-run-materialization-input.v1",
            "plan_digest": plan["canonical_digest"],
            "target_id": TARGET_ID,
            "target_type": "storage",
            "lease_id": orchestration_lease["lease_id"],
            "lease_digest": orchestration_lease["canonical_digest"],
            "fencing_token": orchestration_lease["fencing_token"],
            "acknowledged_materialization_only_no_dispatch_authority": True,
        },
        headers={**worker_headers, "Idempotency-Key": "publication-api-run-0001"},
    )
    assert materialized.status_code == 201
    run = materialized.json()["data"]
    step_run = run["step_runs"][0]

    attempt_response = client.post(
        f"/api/v1/workflows/plans/{plan_id}/runs/{run['run_id']}"
        f"/steps/{step_run['step_run_id']}/attempts",
        json={
            "schema_version": "atlas.workflow-attempt-materialization-input.v1",
            "plan_digest": plan["canonical_digest"],
            "run_digest": run["canonical_digest"],
            "step_run_digest": step_run["canonical_digest"],
            "target_id": TARGET_ID,
            "target_type": "storage",
            "lease_id": orchestration_lease["lease_id"],
            "lease_digest": orchestration_lease["canonical_digest"],
            "fencing_token": orchestration_lease["fencing_token"],
            "acknowledged_attempt_only_no_queue_dispatch_or_execution_authority": True,
        },
        headers={**worker_headers, "Idempotency-Key": "publication-api-attempt-0001"},
    )
    assert attempt_response.status_code == 201
    attempt = attempt_response.json()["data"]

    intent_response = client.post(
        f"/api/v1/workflows/plans/{plan_id}/runs/{run['run_id']}"
        f"/attempts/{attempt['attempt_id']}/dispatch-intents",
        json={
            "schema_version": "atlas.workflow-dispatch-intent-staging-input.v1",
            "plan_digest": plan["canonical_digest"],
            "run_digest": run["canonical_digest"],
            "step_run_id": step_run["step_run_id"],
            "step_run_digest": step_run["canonical_digest"],
            "attempt_digest": attempt["canonical_digest"],
            "target_id": TARGET_ID,
            "target_type": "storage",
            "lease_id": orchestration_lease["lease_id"],
            "lease_digest": orchestration_lease["canonical_digest"],
            "fencing_token": orchestration_lease["fencing_token"],
            (
                "acknowledged_staging_only_no_publication_delivery_dispatch_or_execution_authority"
            ): True,
        },
        headers={**worker_headers, "Idempotency-Key": "publication-api-intent-0001"},
    )
    assert intent_response.status_code == 201
    intent = intent_response.json()["data"]
    outbox_url = (
        f"/api/v1/workflows/plans/{plan_id}/runs/{run['run_id']}"
        f"/attempts/{attempt['attempt_id']}/dispatch-intents/"
        f"{intent['dispatch_intent_id']}/outbox"
    )
    outbox_response = client.get(outbox_url)
    assert outbox_response.status_code == 200
    outbox = outbox_response.json()["data"]["outbox_entries"][0]
    return {
        "plan": plan,
        "orchestration_lease": orchestration_lease,
        "run": run,
        "step_run": step_run,
        "attempt": attempt,
        "intent": intent,
        "outbox": outbox,
        "outbox_url": outbox_url,
    }


def _publication_url(chain: dict[str, Any]) -> str:
    plan = chain["plan"]
    run = chain["run"]
    attempt = chain["attempt"]
    intent = chain["intent"]
    outbox = chain["outbox"]
    return (
        f"/api/v1/workflows/plans/{plan['plan_id']}/runs/{run['run_id']}"
        f"/attempts/{attempt['attempt_id']}/dispatch-intents/"
        f"{intent['dispatch_intent_id']}/outbox/{outbox['outbox_entry_id']}"
        "/publication-lease"
    )


def _acquire_payload(chain: dict[str, Any]) -> dict[str, object]:
    outbox = chain["outbox"]
    return {
        "schema_version": "atlas.workflow-outbox-publication-lease-acquire-input.v1",
        "outbox_entry_digest": outbox["canonical_digest"],
        "target_id": TARGET_ID,
        "target_type": "storage",
        "lease_duration_seconds": 120,
        (
            "acknowledged_coordination_only_no_publication_delivery_dispatch_or_execution_authority"
        ): True,
    }


def _mutation_payload(
    chain: dict[str, Any], lease: dict[str, Any], *, operation: str
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": f"atlas.workflow-outbox-publication-lease-{operation}-input.v1",
        "outbox_entry_digest": chain["outbox"]["canonical_digest"],
        "target_id": TARGET_ID,
        "target_type": "storage",
        "publication_lease_digest": lease["canonical_digest"],
        "publication_fencing_token": lease["publication_fencing_token"],
        (
            "acknowledged_coordination_only_no_publication_delivery_dispatch_or_execution_authority"
        ): True,
    }
    if operation == "heartbeat":
        payload["lease_duration_seconds"] = 180
    return payload


def _assert_no_step_up_language(response_text: str) -> None:
    normalized = response_text.casefold()
    assert "authorized browser session" not in normalized
    assert "mfa" not in normalized


def _assert_authority_false(lease: dict[str, Any]) -> None:
    assert not any(lease["authority"].values())
    assert lease["grants_publication_authority"] is False
    assert lease["grants_delivery_authority"] is False
    assert lease["grants_dispatch_authority"] is False
    assert lease["grants_execution_authority"] is False


def _workflow_snapshots(client: TestClient, chain: dict[str, Any]) -> dict[str, Any]:
    plan_id = chain["plan"]["plan_id"]
    run_id = chain["run"]["run_id"]
    attempt_id = chain["attempt"]["attempt_id"]
    intent_id = chain["intent"]["dispatch_intent_id"]
    urls = {
        "plan": f"/api/v1/workflows/plans/{plan_id}",
        "run": f"/api/v1/workflows/plans/{plan_id}/materialized-run",
        "attempts": f"/api/v1/workflows/plans/{plan_id}/runs/{run_id}/attempts",
        "intents": (
            f"/api/v1/workflows/plans/{plan_id}/runs/{run_id}/attempts/"
            f"{attempt_id}/dispatch-intents"
        ),
        "outbox": (
            f"/api/v1/workflows/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}"
            f"/dispatch-intents/{intent_id}/outbox"
        ),
    }
    responses = {name: client.get(url) for name, url in urls.items()}
    assert all(response.status_code == 200 for response in responses.values())
    return {
        "plan": responses["plan"].json()["data"],
        "run": responses["run"].json()["data"]["run"],
        "attempts": responses["attempts"].json()["data"]["attempts"],
        "intents": responses["intents"].json()["data"]["dispatch_intents"],
        "outbox": responses["outbox"].json()["data"]["outbox_entries"],
    }


def test_publisher_acquires_heartbeats_and_releases_one_secret_free_publication_lease() -> None:
    workload_service, tokens = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        chain = _seed_dispatch_outbox_chain(client, csrf=csrf, worker_token=tokens[WORKER_ID])
        endpoint = _publication_url(chain)
        before = _workflow_snapshots(client, chain)
        empty = client.get(endpoint)

        publisher_headers = _workload_headers(
            tokens[PUBLISHER_ID], WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE
        )
        acquired_response = client.post(
            f"{endpoint}/acquisition",
            json=_acquire_payload(chain),
            headers={
                **publisher_headers,
                "Idempotency-Key": "publication-lease-acquire-0001",
            },
        )
        assert acquired_response.status_code == 201
        acquired = acquired_response.json()["data"]
        active_inventory = client.get(endpoint)

        heartbeat_response = client.post(
            f"{endpoint}/{acquired['publication_lease_id']}/heartbeat",
            json=_mutation_payload(chain, acquired, operation="heartbeat"),
            headers=publisher_headers,
        )
        assert heartbeat_response.status_code == 200
        renewed = heartbeat_response.json()["data"]
        release_response = client.post(
            f"{endpoint}/{renewed['publication_lease_id']}/release",
            json=_mutation_payload(chain, renewed, operation="release"),
            headers=publisher_headers,
        )
        released = release_response.json()["data"]
        released_inventory = client.get(endpoint)
        after = _workflow_snapshots(client, chain)

    assert empty.status_code == 200
    assert empty.headers["Cache-Control"].startswith("no-store")
    assert empty.json()["data"]["outbox_entry_id"] == chain["outbox"]["outbox_entry_id"]
    assert empty.json()["data"]["publication_leases"] == []

    expected_fields = {
        "publication_lease_id",
        "outbox_entry_id",
        "outbox_entry_digest",
        "dispatch_intent_id",
        "dispatch_intent_digest",
        "plan_id",
        "plan_digest",
        "run_id",
        "run_digest",
        "step_run_id",
        "step_run_digest",
        "step_id",
        "attempt_id",
        "attempt_digest",
        "attempt_number",
        "scope",
        "target_id",
        "target_type",
        "orchestration_lease_id",
        "orchestration_lease_digest",
        "orchestration_fencing_token",
        "publisher_subject_id",
        "acquired_at",
        "last_heartbeat_at",
        "expires_at",
        "publication_fencing_token",
        "state",
        "effective_state",
        "authority",
        "grants_publication_authority",
        "grants_delivery_authority",
        "grants_dispatch_authority",
        "grants_execution_authority",
        "canonical_digest",
    }
    assert set(acquired) == expected_fields
    assert acquired["outbox_entry_id"] == chain["outbox"]["outbox_entry_id"]
    assert acquired["outbox_entry_digest"] == chain["outbox"]["canonical_digest"]
    assert acquired["dispatch_intent_id"] == chain["intent"]["dispatch_intent_id"]
    assert acquired["dispatch_intent_digest"] == chain["intent"]["canonical_digest"]
    assert acquired["plan_id"] == chain["plan"]["plan_id"]
    assert acquired["run_id"] == chain["run"]["run_id"]
    assert acquired["step_run_id"] == chain["step_run"]["step_run_id"]
    assert acquired["attempt_id"] == chain["attempt"]["attempt_id"]
    assert acquired["orchestration_lease_id"] == chain["orchestration_lease"]["lease_id"]
    assert acquired["publisher_subject_id"] == PUBLISHER_ID
    assert acquired["state"] == "active"
    assert acquired["effective_state"] == "active"
    _assert_authority_false(acquired)
    assert "secret." not in acquired_response.text.casefold()
    assert tokens[PUBLISHER_ID] not in acquired_response.text

    assert active_inventory.status_code == 200
    assert active_inventory.json()["data"]["publication_leases"] == [acquired]
    assert heartbeat_response.headers["Cache-Control"].startswith("no-store")
    assert renewed["last_heartbeat_at"] >= acquired["last_heartbeat_at"]
    assert renewed["expires_at"] >= acquired["expires_at"]
    assert renewed["publication_fencing_token"] == acquired["publication_fencing_token"]
    assert renewed["state"] == "active"
    assert renewed["effective_state"] == "active"
    _assert_authority_false(renewed)

    assert release_response.status_code == 200
    assert released["state"] == "released"
    assert released["effective_state"] == "released"
    _assert_authority_false(released)
    assert released_inventory.status_code == 200
    assert released_inventory.json()["data"]["publication_leases"] == [released]

    assert before == after
    assert after["plan"]["state"] == "planned"
    assert after["run"]["state"] == "created"
    assert [item["state"] for item in after["attempts"]] == ["created"]
    assert [item["state"] for item in after["intents"]] == ["staged"]
    assert [item["state"] for item in after["outbox"]] == ["pending_publication"]


def test_publication_lease_mutation_requires_the_exact_publisher_workload_identity() -> None:
    workload_service, tokens = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        chain = _seed_dispatch_outbox_chain(client, csrf=csrf, worker_token=tokens[WORKER_ID])
        api_token = _issue_api_token(client, csrf)
        endpoint = _publication_url(chain)
        payload = _acquire_payload(chain)

        browser_mutation = client.post(
            f"{endpoint}/acquisition",
            json=payload,
            headers={"Idempotency-Key": "publication-browser-denied-0001"},
        )
        client.cookies.clear()
        api_token_mutation = client.post(
            f"{endpoint}/acquisition",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Idempotency-Key": "publication-api-token-denied-0001",
            },
        )
        _login(client)
        worker_mutation = client.post(
            f"{endpoint}/acquisition",
            json=payload,
            headers={
                **_workload_headers(tokens[WORKER_ID], WORKFLOW_WORKER_AUDIENCE),
                "Idempotency-Key": "publication-worker-denied-0001",
            },
        )
        publisher_read = client.get(
            endpoint,
            headers=_workload_headers(tokens[PUBLISHER_ID], WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
        )

        publisher_headers = _workload_headers(
            tokens[PUBLISHER_ID], WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE
        )
        acquired_response = client.post(
            f"{endpoint}/acquisition",
            json=payload,
            headers={
                **publisher_headers,
                "Idempotency-Key": "publication-owner-acquire-0001",
            },
        )
        assert acquired_response.status_code == 201
        acquired = acquired_response.json()["data"]
        wrong_publisher_heartbeat = client.post(
            f"{endpoint}/{acquired['publication_lease_id']}/heartbeat",
            json=_mutation_payload(chain, acquired, operation="heartbeat"),
            headers=_workload_headers(
                tokens[OTHER_PUBLISHER_ID], WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE
            ),
        )
        browser_inventory = client.get(endpoint)

    for response in (browser_mutation, api_token_mutation, worker_mutation):
        assert response.status_code == 401
        assert response.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(response.text)
    assert api_token not in api_token_mutation.text

    assert publisher_read.status_code in {400, 401}
    _assert_no_step_up_language(publisher_read.text)
    assert wrong_publisher_heartbeat.status_code in {403, 409}
    _assert_no_step_up_language(wrong_publisher_heartbeat.text)

    assert browser_inventory.status_code == 200
    inventory = browser_inventory.json()["data"]
    assert inventory["outbox_entry_id"] == chain["outbox"]["outbox_entry_id"]
    assert inventory["publication_leases"] == [acquired]
    _assert_authority_false(inventory["publication_leases"][0])
    assert chain["outbox"]["state"] == "pending_publication"
