from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    _issue_api_token,
    _login,
    _settings,
    _workload_headers,
)
from test_workflow_target_context_access_authorization_lease_api import (
    _workload_service_and_token,
)

from atlas.api.app import create_app
from atlas.api.security import (
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULER_AUDIENCE,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULER_SUBJECT,
)
from atlas.modules.authorization.application.bootstrap import (
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_CONSUMPTION_READ,
    build_development_authorization_service,
    workflow_protected_runtime_process_scheduling_consumption_scope,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingConsumptionError,
)
from atlas.modules.workflows.domain.models import WorkflowScope
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_consumption_domain import (
    WorkflowProtectedRuntimeProcessSchedulingConsumptionAttemptState,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState,
    code_owned_workflow_protected_runtime_process_scheduling_consumption_policy,
)

ENDPOINT = "/api/v1/workflows/protected-runtime-process-scheduling-consumptions"
NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")


def _attempt(suffix: str) -> SimpleNamespace:
    policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
    return SimpleNamespace(
        attempt_id=f"prpsc-attempt-{suffix}",
        consumption_id=f"prpsc-consumption-{suffix}",
        canonical_digest=suffix[0] * 64,
        scope=SCOPE,
        state=(
            WorkflowProtectedRuntimeProcessSchedulingConsumptionAttemptState
        ).PROCESS_SCHEDULING_ATTEMPT_STARTED,
        started_at=NOW,
        invocation_deadline=NOW + timedelta(seconds=1),
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        scheduling_profile_digest=policy.scheduling_profile_digest,
        primitive_digest=policy.primitive_digest,
    )


def _result(
    attempt: SimpleNamespace,
    state: WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState,
) -> SimpleNamespace:
    scheduled: bool | None = (
        state
        is (
            WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
        ).PROCESS_SCHEDULED_SUSPENDED_IN_PROTECTED_BOUNDARY
    )
    if (
        state
        is (
            WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
        ).PROCESS_SCHEDULING_OUTCOME_UNCERTAIN
    ):
        scheduled = None
    known = scheduled is not None
    return SimpleNamespace(
        attempt_id=attempt.attempt_id,
        attempt_digest=attempt.canonical_digest,
        consumption_id=attempt.consumption_id,
        scope=attempt.scope,
        result_state=state,
        completed_at=NOW + timedelta(milliseconds=100),
        recorded_at=NOW + timedelta(milliseconds=200),
        process_scheduled=scheduled,
        process_suspended=True if known else None,
        process_runnable=False if known else None,
    )


def _presentations() -> tuple[SimpleNamespace, ...]:
    states = WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
    pending = _attempt("a" * 24)
    scheduled = _attempt("b" * 24)
    rejected = _attempt("c" * 24)
    failed = _attempt("d" * 24)
    uncertain = _attempt("e" * 24)
    return (
        SimpleNamespace(attempt=pending, result=None),
        SimpleNamespace(
            attempt=scheduled,
            result=_result(
                scheduled,
                states.PROCESS_SCHEDULED_SUSPENDED_IN_PROTECTED_BOUNDARY,
            ),
        ),
        SimpleNamespace(
            attempt=rejected,
            result=_result(rejected, states.PROCESS_SCHEDULING_REJECTED_WITHOUT_SCHEDULING),
        ),
        SimpleNamespace(
            attempt=failed,
            result=_result(failed, states.PROCESS_SCHEDULING_FAILED_WITHOUT_SCHEDULING),
        ),
        SimpleNamespace(
            attempt=uncertain,
            result=_result(uncertain, states.PROCESS_SCHEDULING_OUTCOME_UNCERTAIN),
        ),
    )


class _Service:
    durable = True

    def __init__(self) -> None:
        self.repository = self
        self.presentations = _presentations()
        self.calls: list[dict[str, Any]] = []

    async def consume(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self.presentations[1]

    async def list_protected_runtime_process_scheduling_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[SimpleNamespace, ...]:
        assert scope == SCOPE
        assert limit == 256
        return tuple(presentation.attempt for presentation in self.presentations)

    async def get_protected_runtime_process_scheduling_results(
        self, *, scope: WorkflowScope, consumption_ids: tuple[str, ...]
    ) -> tuple[SimpleNamespace, ...]:
        assert scope == SCOPE
        return tuple(
            presentation.result
            for presentation in self.presentations
            if presentation.result is not None
            and presentation.attempt.consumption_id in consumption_ids
        )

    async def get_authoritative_time(self) -> datetime:
        return NOW + timedelta(milliseconds=500)


class _ConflictService(_Service):
    async def consume(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        raise WorkflowProtectedRuntimeProcessSchedulingConsumptionError(
            "protected_runtime_process_scheduling_outcome_uncertain_no_retry"
        )


class _AuditSink:
    async def record(self, event: object) -> None:
        del event


def _payload() -> dict[str, object]:
    policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
    return {
        "authorization_lease_id": (
            "workflow-protected-runtime-process-scheduling-lease.0123456789abcdef01234567"
        ),
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertainty_no_retry_acknowledged": True,
        "idempotency_key": "process-scheduling-consumption-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def _exact_workload() -> tuple[Any, str]:
    return _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULER_SUBJECT,
        audience=WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULER_AUDIENCE,
    )


def test_process_scheduling_consumption_has_distinct_read_only_scope() -> None:
    settings = _settings()
    service = build_development_authorization_service(settings, _AuditSink())
    scope = workflow_protected_runtime_process_scheduling_consumption_scope(
        settings.development_organization_id,
        settings.environment,
    )

    assert WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_CONSUMPTION_READ == (
        "workflow.protected-runtime-process-scheduling-consumptions.read"
    )
    assert scope.resource_id == (
        "resource.workflow.protected-runtime-process-scheduling-consumptions"
    )
    assert scope.capability_class.value == "C1"
    assert any(
        assignment.assignment_id
        == "assignment.development.workflow-protected-runtime-process-scheduling-consumptions"
        and assignment.scope == scope
        for assignment in cast(Any, service)._assignments
    )


def test_password_get_is_minimized_no_store_and_has_all_terminal_states() -> None:
    service = _Service()
    app = create_app(
        _settings(),
        workflow_protected_runtime_process_scheduling_consumption_service=cast(Any, service),
    )
    with TestClient(app) as client:
        _login(client)
        response = client.get(ENDPOINT)

    assert response.status_code == 200, response.json()
    items = response.json()["data"]["process_schedulings"]
    assert [item["result_state"] for item in items] == [
        None,
        "process_scheduled_suspended_in_protected_boundary",
        "process_scheduling_rejected_without_scheduling",
        "process_scheduling_failed_without_scheduling",
        "process_scheduling_outcome_uncertain",
    ]
    assert set(items[0]) == {
        "process_scheduling_id",
        "attempt_state",
        "result_state",
        "started_at",
        "completed_at",
        "recorded_at",
        "process_scheduled",
        "process_sealed",
        "process_suspended",
        "process_runnable",
        "policy_reference",
        "scheduling_profile_reference",
        "primitive_reference",
        "integrity_reference",
        "effective_authority",
    }
    assert all(item["effective_authority"] is False for item in items)
    assert items[1]["process_sealed"] is True
    assert items[1]["process_runnable"] is False
    assert items[-1]["process_scheduled"] is None
    serialized = str(response.json()).lower()
    for forbidden in (
        "command",
        "executable",
        "argument",
        "environment_variable",
        "runtime_locator",
        "process_identifier",
        "queue",
        "priority",
        "affinity",
        "credential",
        "mfa",
        "authorized browser",
    ):
        assert forbidden not in serialized
    _assert_no_store(response)


def test_only_exact_workload_can_post_strict_acknowledged_request() -> None:
    workload_service, token = _exact_workload()
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_process_scheduling_consumption_service=cast(Any, service),
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULER_AUDIENCE)
    with TestClient(app) as client:
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        human = client.post(ENDPOINT, json=_payload(), headers={"X-CSRF-Token": csrf})
        client.cookies.clear()
        personal = client.post(
            ENDPOINT,
            json=_payload(),
            headers={"Authorization": f"Bearer {personal_token}"},
        )
        created = client.post(ENDPOINT, json=_payload(), headers=headers)

    assert human.status_code == 401
    assert personal.status_code == 401
    assert created.status_code == 201, created.json()
    assert len(service.calls) == 1
    assert set(service.calls[0]) == {
        "authorization_lease_id",
        "policy_id",
        "policy_version",
        "irreversible_consumption_acknowledged",
        "uncertainty_no_retry_acknowledged",
        "idempotency_key",
    }
    _assert_no_store(created)


def test_post_forbids_operational_material_and_uncertainty_is_not_retryable() -> None:
    workload_service, token = _exact_workload()
    service = _ConflictService()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_process_scheduling_consumption_service=cast(Any, service),
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULER_AUDIENCE)
    invalid = (
        {**_payload(), "irreversible_consumption_acknowledged": False},
        {**_payload(), "uncertainty_no_retry_acknowledged": False},
        {**_payload(), "command": "whoami"},
        {**_payload(), "arguments": ["--unsafe"]},
        {**_payload(), "environment": {"SECRET": "value"}},
        {**_payload(), "runtime_locator": "runtime.untrusted"},
        {**_payload(), "process_identifier": "pid.untrusted"},
        {**_payload(), "queue": "queue.untrusted"},
        {**_payload(), "priority": 99},
        {**_payload(), "affinity": [0]},
        {**_payload(), "connector_id": "connector.untrusted"},
        {**_payload(), "mcp_tool": "schedule"},
    )
    with TestClient(app) as client:
        invalid_responses = [
            client.post(ENDPOINT, json=payload, headers=headers) for payload in invalid
        ]
        uncertain = client.post(ENDPOINT, json=_payload(), headers=headers)

    assert all(response.status_code == 422 for response in invalid_responses)
    assert uncertain.status_code == 409
    assert uncertain.json()["retryable"] is False
    assert "lease" not in uncertain.json()["detail"].lower()
    assert len(service.calls) == 1
    for response in (*invalid_responses, uncertain):
        _assert_no_store(response)
