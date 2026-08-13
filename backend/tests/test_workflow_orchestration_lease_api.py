from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.conversations.application.ports import ConversationTargetAccessRequest
from atlas.modules.conversations.domain.models import (
    AuthorizedConversationTarget,
    ConversationScope,
)
from atlas.modules.identity.adapters.workload_identities import InMemoryWorkloadIdentityRepository
from atlas.modules.identity.application.workload_identities import WorkloadIdentityService
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.workflows.adapters import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_WORKER_AUDIENCE,
    WorkflowPlanningService,
    WorkflowPlanRepository,
)
from atlas.modules.workflows.domain import code_owned_workflow_registry

TARGET_ID = "asset.storage.lab.vsp-g400"
WORKER_ID = "workload.atlas.workflow-worker-01"
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
                description="Explicitly authorized workflow lease test target.",
            ),
        )


class _PlanOnlyRepository:
    @property
    def durable(self) -> bool:
        return False

    async def close(self) -> None:
        return None


def _settings() -> Settings:
    return Settings(environment="development", development_identity_enabled=True)


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


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


def _workload_service() -> tuple[WorkloadIdentityService, str]:
    service = WorkloadIdentityService(
        repository=InMemoryWorkloadIdentityRepository(),
        audit_sink=_AuditSink(),
        environment_id="environment.development",
        signing_keys={3: b"workflow-lease-test-signing-key" * 2},
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
    issued = asyncio.run(
        service.create(
            actor=actor,
            identity_id=WORKER_ID,
            display_name="Workflow worker 01",
            service_id="service.workflow-worker",
            instance_id="instance.workflow-worker.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Coordinate workflow plan ownership without execution authority.",
            audiences=(WORKFLOW_WORKER_AUDIENCE,),
            secret_reference_ids=("secret.workflow-worker.local-01",),
            lifetime=timedelta(minutes=10),
            reason="Create the bounded workflow orchestration test identity.",
            idempotency_key="workflow-worker-create-0001",
            correlation_id="correlation.workflow-worker-create",
        )
    )
    return service, issued.token


def _workload_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Workload {token}",
        "X-Atlas-Audience": WORKFLOW_WORKER_AUDIENCE,
        "X-Atlas-Environment": "environment.development",
    }


def test_injected_planning_service_and_default_lease_service_share_one_repository() -> None:
    repository = InMemoryWorkflowPlanRepository()
    planning_service = WorkflowPlanningService(
        registry=code_owned_workflow_registry(),
        repository=repository,
        audit_sink=_AuditSink(),
    )
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workflow_planning_service=planning_service,
    )

    with TestClient(app):
        assert app.state.workflow_planning_service.repository is repository
        assert app.state.workflow_orchestration_lease_service.repository is repository
        assert app.state.workflow_orchestration_lease_repository is repository
        assert app.state.workflow_run_materialization_service.repository is repository
        assert app.state.workflow_run_materialization_repository is repository


def test_plan_only_repository_requires_an_explicit_lease_service() -> None:
    planning_service = WorkflowPlanningService(
        registry=code_owned_workflow_registry(),
        repository=cast(WorkflowPlanRepository, _PlanOnlyRepository()),
        audit_sink=_AuditSink(),
    )

    with pytest.raises(ValueError, match="inject workflow_orchestration_lease_service"):
        create_app(
            _settings(),
            audit_sink=_AuditSink(),
            workflow_planning_service=planning_service,
        )


def test_workload_lease_api_requires_explicit_target_authority_and_never_grants_execution() -> None:
    target_source = _ExplicitTargetAccessSource()
    workload_service, token = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=target_source,
    )

    with TestClient(app) as client:
        csrf = _login(client)
        created = client.post(
            "/api/v1/workflows/plans",
            json=_plan_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workflow-lease-plan-0001"},
        )
        assert created.status_code == 201
        plan = created.json()["data"]
        plan_id = plan["plan_id"]
        acquire_payload = {
            "schema_version": "atlas.workflow-orchestration-lease-acquire-input.v1",
            "plan_digest": plan["canonical_digest"],
            "target_id": TARGET_ID,
            "target_type": "storage",
            "lease_duration_seconds": 90,
            "acknowledged_coordination_only_no_execution_authority": True,
        }

        target_source.authorized_subject_ids.remove(WORKER_ID)
        unauthorized_target = client.post(
            f"/api/v1/workflows/plans/{plan_id}/orchestration-lease/acquisition",
            json=acquire_payload,
            headers={
                **_workload_headers(token),
                "Idempotency-Key": "workflow-lease-acquire-denied-0001",
            },
        )
        target_source.authorized_subject_ids.add(WORKER_ID)

        browser_session_mutation = client.post(
            f"/api/v1/workflows/plans/{plan_id}/orchestration-lease/acquisition",
            json=acquire_payload,
            headers={"Idempotency-Key": "workflow-lease-browser-denied-0001"},
        )
        acquired = client.post(
            f"/api/v1/workflows/plans/{plan_id}/orchestration-lease/acquisition",
            json=acquire_payload,
            headers={
                **_workload_headers(token),
                "Idempotency-Key": "workflow-lease-acquire-0001",
            },
        )
        assert acquired.status_code == 201
        lease = acquired.json()["data"]

        status = client.get(f"/api/v1/workflows/plans/{plan_id}/orchestration-lease")
        heartbeat = client.post(
            f"/api/v1/workflows/plans/{plan_id}/orchestration-lease/{lease['lease_id']}/heartbeat",
            json={
                "schema_version": "atlas.workflow-orchestration-lease-heartbeat-input.v1",
                "plan_digest": plan["canonical_digest"],
                "target_id": TARGET_ID,
                "target_type": "storage",
                "lease_digest": lease["canonical_digest"],
                "fencing_token": lease["fencing_token"],
                "lease_duration_seconds": 120,
                "acknowledged_coordination_only_no_execution_authority": True,
            },
            headers=_workload_headers(token),
        )
        assert heartbeat.status_code == 200
        renewed = heartbeat.json()["data"]
        released = client.post(
            f"/api/v1/workflows/plans/{plan_id}/orchestration-lease/{lease['lease_id']}/release",
            json={
                "schema_version": "atlas.workflow-orchestration-lease-release-input.v1",
                "plan_digest": plan["canonical_digest"],
                "target_id": TARGET_ID,
                "target_type": "storage",
                "lease_digest": renewed["canonical_digest"],
                "fencing_token": renewed["fencing_token"],
                "acknowledged_coordination_only_no_execution_authority": True,
            },
            headers=_workload_headers(token),
        )
        unchanged_plan = client.get(f"/api/v1/workflows/plans/{plan_id}")

    assert unauthorized_target.status_code == 404
    assert unauthorized_target.json()["code"] == "workflow_resource_unavailable"
    assert browser_session_mutation.status_code == 401
    assert browser_session_mutation.json()["code"] == "workload_authentication_failed"
    assert "mfa" not in browser_session_mutation.text.casefold()
    assert "authorized browser session" not in browser_session_mutation.text.casefold()
    assert acquired.headers["Cache-Control"].startswith("no-store")
    assert lease["worker_subject_id"] == WORKER_ID
    assert lease["state"] == "active"
    assert lease["effective_state"] == "active"
    assert lease["grants_execution_authority"] is False
    assert "atlas_wlt_v1" not in acquired.text
    assert "secret.workflow-worker" not in acquired.text
    assert status.status_code == 200
    assert status.json()["data"]["lease"] == lease
    assert heartbeat.headers["Cache-Control"].startswith("no-store")
    assert renewed["last_heartbeat_at"] >= lease["last_heartbeat_at"]
    assert renewed["grants_execution_authority"] is False
    assert released.status_code == 200
    assert released.json()["data"]["state"] == "released"
    assert released.json()["data"]["effective_state"] == "released"
    assert released.json()["data"]["grants_execution_authority"] is False
    assert unchanged_plan.status_code == 200
    assert unchanged_plan.json()["data"] == plan


def test_workload_lease_api_rejects_wrong_audience_and_environment_without_step_up_language() -> (
    None
):
    target_source = _ExplicitTargetAccessSource()
    workload_service, token = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=target_source,
    )

    with TestClient(app) as client:
        csrf = _login(client)
        created = client.post(
            "/api/v1/workflows/plans",
            json=_plan_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workflow-lease-plan-0002"},
        )
        plan = created.json()["data"]
        endpoint = f"/api/v1/workflows/plans/{plan['plan_id']}/orchestration-lease/acquisition"
        payload = {
            "schema_version": "atlas.workflow-orchestration-lease-acquire-input.v1",
            "plan_digest": plan["canonical_digest"],
            "target_id": TARGET_ID,
            "target_type": "storage",
            "lease_duration_seconds": 60,
            "acknowledged_coordination_only_no_execution_authority": True,
        }
        wrong_audience = client.post(
            endpoint,
            json=payload,
            headers={
                **_workload_headers(token),
                "X-Atlas-Audience": "audience.untrusted-worker",
                "Idempotency-Key": "workflow-lease-wrong-audience-0001",
            },
        )
        wrong_environment = client.post(
            endpoint,
            json=payload,
            headers={
                **_workload_headers(token),
                "X-Atlas-Environment": "environment.production",
                "Idempotency-Key": "workflow-lease-wrong-environment-0001",
            },
        )

    assert wrong_audience.status_code == 401
    assert wrong_environment.status_code == 401
    for response in (wrong_audience, wrong_environment):
        assert response.json()["code"] == "workload_authentication_failed"
        assert "mfa" not in response.text.casefold()
        assert "authorized browser session" not in response.text.casefold()


def test_workload_materializes_one_no_dispatch_run_visible_to_existing_browser_session() -> None:
    target_source = _ExplicitTargetAccessSource()
    workload_service, token = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=target_source,
    )

    with TestClient(app) as client:
        csrf = _login(client)
        created = client.post(
            "/api/v1/workflows/plans",
            json=_plan_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workflow-run-plan-0001"},
        )
        assert created.status_code == 201
        plan = created.json()["data"]
        plan_id = plan["plan_id"]

        empty_status = client.get(f"/api/v1/workflows/plans/{plan_id}/materialized-run")
        browser_mutation = client.post(
            f"/api/v1/workflows/plans/{plan_id}/materialized-run",
            json={
                "schema_version": "atlas.workflow-run-materialization-input.v1",
                "plan_digest": plan["canonical_digest"],
                "target_id": TARGET_ID,
                "target_type": "storage",
                "lease_id": "workflow-lease.not-available",
                "lease_digest": "0" * 64,
                "fencing_token": 1,
                "acknowledged_materialization_only_no_dispatch_authority": True,
            },
            headers={"Idempotency-Key": "workflow-run-browser-denied-0001"},
        )
        acquired = client.post(
            f"/api/v1/workflows/plans/{plan_id}/orchestration-lease/acquisition",
            json={
                "schema_version": "atlas.workflow-orchestration-lease-acquire-input.v1",
                "plan_digest": plan["canonical_digest"],
                "target_id": TARGET_ID,
                "target_type": "storage",
                "lease_duration_seconds": 90,
                "acknowledged_coordination_only_no_execution_authority": True,
            },
            headers={
                **_workload_headers(token),
                "Idempotency-Key": "workflow-run-lease-0001",
            },
        )
        assert acquired.status_code == 201
        lease = acquired.json()["data"]
        materialization_payload = {
            "schema_version": "atlas.workflow-run-materialization-input.v1",
            "plan_digest": plan["canonical_digest"],
            "target_id": TARGET_ID,
            "target_type": "storage",
            "lease_id": lease["lease_id"],
            "lease_digest": lease["canonical_digest"],
            "fencing_token": lease["fencing_token"],
            "acknowledged_materialization_only_no_dispatch_authority": True,
        }
        headers = {
            **_workload_headers(token),
            "Idempotency-Key": "workflow-run-materialize-0001",
        }
        materialized = client.post(
            f"/api/v1/workflows/plans/{plan_id}/materialized-run",
            json=materialization_payload,
            headers=headers,
        )
        replayed = client.post(
            f"/api/v1/workflows/plans/{plan_id}/materialized-run",
            json=materialization_payload,
            headers=headers,
        )
        browser_status = client.get(f"/api/v1/workflows/plans/{plan_id}/materialized-run")
        unchanged_plan = client.get(f"/api/v1/workflows/plans/{plan_id}")

    assert empty_status.status_code == 200
    assert empty_status.json()["data"]["run"] is None
    assert browser_mutation.status_code == 401
    assert browser_mutation.json()["code"] == "workload_authentication_failed"
    assert "mfa" not in browser_mutation.text.casefold()
    assert "authorized browser session" not in browser_mutation.text.casefold()
    assert materialized.status_code == 201
    run = materialized.json()["data"]
    assert replayed.status_code == 201
    assert replayed.json()["data"] == run
    assert run["state"] == "created"
    assert run["plan_id"] == plan_id
    assert run["plan_digest"] == plan["canonical_digest"]
    assert run["lease_id"] == lease["lease_id"]
    assert run["lease_digest"] == lease["canonical_digest"]
    assert run["fencing_token"] == lease["fencing_token"]
    assert run["materialized_by_subject_id"] == WORKER_ID
    assert run["step_runs"]
    assert all(step["state"] == "not_started" for step in run["step_runs"])
    assert not any(run["authority"].values())
    assert run["grants_execution_authority"] is False
    assert browser_status.status_code == 200
    assert browser_status.headers["Cache-Control"].startswith("no-store")
    assert browser_status.json()["data"]["run"] == run
    assert unchanged_plan.status_code == 200
    assert unchanged_plan.json()["data"] == plan
