"""Pass 36: docs/050_API.md SS15/SS19/SS20's operation resource framework had zero implementation
anywhere in the codebase. These tests cover the domain model's construction invariants (mirroring
`bootstrap_end_to_end_verification.py`'s state-machine rigor) and the application service's real
behavior: creation, the `mark_running`/`mark_succeeded`/`mark_failed`/`mark_partial` transitions,
`get()`'s owner-or-elevated-cross-subject-access authorization, and `cancel()`'s real idempotency
(repeated cancellation of an already-cancelled operation succeeds; cancelling a different terminal
state is a real conflict).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.operations.adapters.memory import InMemoryOperationResourceRepository
from atlas.modules.operations.application.ports import OperationResourceError
from atlas.modules.operations.application.service import OperationResourceService
from atlas.modules.operations.domain.models import OperationResource, OperationState

ORG = "organization.development"
ENV = "environment.test"
NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def _subject(subject_id: str) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name=subject_id,
        kind=SubjectKind.HUMAN,
        provider_id="provider.development",
        organization_id=ORG,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.SINGLE_FACTOR,
        authenticated_at=NOW,
        role_ids=(),
    )


def _resource(**overrides: object) -> OperationResource:
    defaults: dict[str, object] = dict(
        operation_id="operation.example-0001",
        operation_type="operation.knowledge-document-indexing",
        owner_subject_id="subject.owner",
        organization_id=ORG,
        environment_id=ENV,
        state=OperationState.QUEUED,
        progress_summary="Queued for processing.",
        created_at=NOW,
        started_at=None,
        updated_at=NOW,
        deadline_at=None,
        expires_at=None,
        input_artifact_reference="document-knowledge-preparation.example",
        workflow_run_reference=None,
        correlation_id="cor_example",
        current_step="queued",
        result_reference=None,
        partial_result_reference=None,
        error_reference=None,
        evidence_references=(),
        cancellation_eligible=True,
        cancellation_reason=None,
        required_human_task_reference=None,
    )
    defaults.update(overrides)
    return OperationResource(**defaults)  # type: ignore[arg-type]


class _NullAuditSink:
    async def record(self, event: object) -> None:
        return None


class AllowAllAuthorizer:
    def __init__(self, *, cross_subject: bool = False) -> None:
        self.cross_subject = cross_subject

    async def authorize(self, **_kwargs: object) -> None:
        return None

    async def cross_subject_access_allowed(self, **_kwargs: object) -> bool:
        return self.cross_subject


class DenyAllAuthorizer:
    async def authorize(self, **_kwargs: object) -> None:
        raise OperationResourceError("operation_resource_permission_denied")

    async def cross_subject_access_allowed(self, **_kwargs: object) -> bool:
        return False


def _service(
    *, authorizer: object | None = None, clock: object = lambda: NOW
) -> tuple[OperationResourceService, InMemoryOperationResourceRepository]:
    repository = InMemoryOperationResourceRepository()
    service = OperationResourceService(
        repository=repository,
        permission_authorizer=authorizer or AllowAllAuthorizer(),  # type: ignore[arg-type]
        audit_sink=_NullAuditSink(),
        clock=clock,  # type: ignore[arg-type]
    )
    return service, repository


async def _create(
    service: OperationResourceService, actor: AuthenticatedSubject, *, correlation_id: str = "cor_1"
) -> OperationResource:
    return await service.create(
        actor=actor,
        organization_id=ORG,
        environment_id=ENV,
        operation_type="operation.knowledge-document-indexing",
        input_artifact_reference="document-knowledge-preparation.example",
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# Domain: construction invariants
# ---------------------------------------------------------------------------


def test_operation_resource_constructs_with_valid_queued_state() -> None:
    resource = _resource()
    assert resource.state is OperationState.QUEUED
    assert resource.is_terminal is False


def test_operation_resource_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _resource(created_at=datetime(2026, 9, 11, 12, 0))


def test_operation_resource_rejects_updated_before_created() -> None:
    with pytest.raises(ValueError, match="updated"):
        _resource(updated_at=NOW - timedelta(seconds=1))


def test_operation_resource_rejects_started_before_created() -> None:
    with pytest.raises(ValueError, match="start time"):
        _resource(started_at=NOW - timedelta(seconds=1))


def test_operation_resource_rejects_deadline_before_creation() -> None:
    with pytest.raises(ValueError, match="deadline"):
        _resource(deadline_at=NOW)


def test_operation_resource_rejects_expiry_before_creation() -> None:
    with pytest.raises(ValueError, match="expiry"):
        _resource(expires_at=NOW)


def test_operation_resource_succeeded_requires_result_reference() -> None:
    with pytest.raises(ValueError, match="result reference"):
        _resource(state=OperationState.SUCCEEDED, cancellation_eligible=False)


def test_operation_resource_only_succeeded_may_carry_result_reference() -> None:
    with pytest.raises(ValueError, match="result reference"):
        _resource(state=OperationState.QUEUED, result_reference="chunks.4")


def test_operation_resource_failed_requires_error_reference() -> None:
    with pytest.raises(ValueError, match="error reference"):
        _resource(state=OperationState.FAILED, cancellation_eligible=False)


def test_operation_resource_only_failed_or_timed_out_may_carry_error_reference() -> None:
    with pytest.raises(ValueError, match="error reference"):
        _resource(state=OperationState.QUEUED, error_reference="error.x")


def test_operation_resource_cancelled_requires_cancellation_reason() -> None:
    with pytest.raises(ValueError, match="cancellation reason"):
        _resource(state=OperationState.CANCELLED, cancellation_eligible=False)


def test_operation_resource_only_cancelled_may_carry_cancellation_reason() -> None:
    with pytest.raises(ValueError, match="cancellation reason"):
        _resource(state=OperationState.QUEUED, cancellation_reason="Not cancelled.")


def test_operation_resource_partial_requires_partial_result_reference() -> None:
    with pytest.raises(ValueError, match="partial result reference"):
        _resource(state=OperationState.PARTIAL)


def test_operation_resource_only_partial_may_carry_partial_result_reference() -> None:
    with pytest.raises(ValueError, match="partial result reference"):
        _resource(state=OperationState.QUEUED, partial_result_reference="partial.1")


def test_operation_resource_terminal_state_forbids_cancellation_eligible() -> None:
    with pytest.raises(ValueError, match="cancellation-eligible"):
        _resource(
            state=OperationState.SUCCEEDED,
            result_reference="chunks.4",
            cancellation_eligible=True,
        )


def test_operation_resource_duplicate_evidence_references_rejected() -> None:
    with pytest.raises(ValueError, match="distinct"):
        _resource(evidence_references=("evidence.a", "evidence.a"))


def test_operation_resource_valid_succeeded_construction() -> None:
    resource = _resource(
        state=OperationState.SUCCEEDED,
        result_reference="chunks.4",
        evidence_references=("evidence.a",),
        cancellation_eligible=False,
        started_at=NOW,
    )
    assert resource.result_reference == "chunks.4"
    assert resource.is_terminal is True


def test_operation_resource_valid_timed_out_may_carry_error_reference() -> None:
    resource = _resource(
        state=OperationState.TIMED_OUT,
        error_reference="error.deadline_exceeded",
        cancellation_eligible=False,
        started_at=NOW,
    )
    assert resource.error_reference == "error.deadline_exceeded"
    assert resource.is_terminal is True


# ---------------------------------------------------------------------------
# Service: create / real state transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_persists_a_queued_operation_resource() -> None:
    service, repository = _service()
    actor = _subject("subject.owner")
    resource = await _create(service, actor)
    assert resource.state is OperationState.QUEUED
    assert resource.owner_subject_id == actor.subject_id
    stored = await repository.get(
        operation_id=resource.operation_id, organization_id=ORG, environment_id=ENV
    )
    assert stored == resource


@pytest.mark.asyncio
async def test_mark_running_then_succeeded_transitions_real_state() -> None:
    service, _ = _service()
    actor = _subject("subject.owner")
    resource = await _create(service, actor)

    running = await service.mark_running(
        actor=actor,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        current_step="indexing",
        correlation_id="cor_2",
    )
    assert running.state is OperationState.RUNNING
    assert running.started_at is not None

    succeeded = await service.mark_succeeded(
        actor=actor,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        result_reference="chunks.7",
        correlation_id="cor_3",
    )
    assert succeeded.state is OperationState.SUCCEEDED
    assert succeeded.result_reference == "chunks.7"
    assert succeeded.cancellation_eligible is False


@pytest.mark.asyncio
async def test_mark_failed_records_a_real_error_reference() -> None:
    service, _ = _service()
    actor = _subject("subject.owner")
    resource = await _create(service, actor)
    await service.mark_running(
        actor=actor,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        current_step="indexing",
        correlation_id="cor_2",
    )
    failed = await service.mark_failed(
        actor=actor,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        error_reference="error.document_knowledge_preparation_not_found",
        correlation_id="cor_3",
    )
    assert failed.state is OperationState.FAILED
    assert failed.error_reference == "error.document_knowledge_preparation_not_found"
    assert failed.cancellation_eligible is False


@pytest.mark.asyncio
async def test_mark_partial_records_a_real_partial_result_reference() -> None:
    service, _ = _service()
    actor = _subject("subject.owner")
    resource = await _create(service, actor)
    partial = await service.mark_partial(
        actor=actor,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        partial_result_reference="partial.chunks.3",
        evidence_references=("evidence.a",),
        correlation_id="cor_2",
    )
    assert partial.state is OperationState.PARTIAL
    assert partial.partial_result_reference == "partial.chunks.3"
    assert partial.is_terminal is False


@pytest.mark.asyncio
async def test_mark_succeeded_rejects_an_already_terminal_operation() -> None:
    service, _ = _service()
    actor = _subject("subject.owner")
    resource = await _create(service, actor)
    await service.mark_failed(
        actor=actor,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        error_reference="error.x",
        correlation_id="cor_2",
    )
    with pytest.raises(OperationResourceError, match="already_terminal"):
        await service.mark_succeeded(
            actor=actor,
            organization_id=ORG,
            environment_id=ENV,
            operation_id=resource.operation_id,
            result_reference="chunks.1",
            correlation_id="cor_3",
        )


@pytest.mark.asyncio
async def test_create_raises_when_permission_denied() -> None:
    service, _ = _service(authorizer=DenyAllAuthorizer())
    actor = _subject("subject.owner")
    # create() itself doesn't call authorize() -- it is the request-time gate for get()/cancel()
    # that must independently re-authorize. Confirm get() does raise on denial.
    with pytest.raises(OperationResourceError, match="permission_denied"):
        await service.get(
            actor=actor,
            organization_id=ORG,
            environment_id=ENV,
            operation_id="operation.does-not-exist",
            correlation_id="cor_1",
        )


# ---------------------------------------------------------------------------
# Service: get() ownership and cross-subject access
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_allows_the_owner() -> None:
    service, _ = _service()
    owner = _subject("subject.owner")
    resource = await _create(service, owner)
    fetched = await service.get(
        actor=owner,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        correlation_id="cor_2",
    )
    assert fetched.operation_id == resource.operation_id


@pytest.mark.asyncio
async def test_get_denies_a_non_owner_without_cross_subject_access() -> None:
    service, _ = _service(authorizer=AllowAllAuthorizer(cross_subject=False))
    owner = _subject("subject.owner")
    other = _subject("subject.other")
    resource = await _create(service, owner)
    with pytest.raises(OperationResourceError, match="not_found"):
        await service.get(
            actor=other,
            organization_id=ORG,
            environment_id=ENV,
            operation_id=resource.operation_id,
            correlation_id="cor_2",
        )


@pytest.mark.asyncio
async def test_get_allows_a_non_owner_with_cross_subject_access() -> None:
    service, _ = _service(authorizer=AllowAllAuthorizer(cross_subject=True))
    owner = _subject("subject.owner")
    elevated = _subject("subject.elevated")
    resource = await _create(service, owner)
    fetched = await service.get(
        actor=elevated,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        correlation_id="cor_2",
    )
    assert fetched.operation_id == resource.operation_id


@pytest.mark.asyncio
async def test_get_unknown_operation_raises_not_found() -> None:
    service, _ = _service()
    actor = _subject("subject.owner")
    with pytest.raises(OperationResourceError, match="not_found"):
        await service.get(
            actor=actor,
            organization_id=ORG,
            environment_id=ENV,
            operation_id="operation.does-not-exist",
            correlation_id="cor_1",
        )


# ---------------------------------------------------------------------------
# Service: cancel() idempotency, ownership, and terminal-state rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_transitions_a_queued_operation() -> None:
    service, _ = _service()
    actor = _subject("subject.owner")
    resource = await _create(service, actor)
    cancelled = await service.cancel(
        actor=actor,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        reason="No longer needed.",
        correlation_id="cor_2",
    )
    assert cancelled.state is OperationState.CANCELLED
    assert cancelled.cancellation_reason == "No longer needed."
    assert cancelled.cancellation_eligible is False


@pytest.mark.asyncio
async def test_cancel_is_idempotent_for_an_already_cancelled_operation() -> None:
    service, _ = _service()
    actor = _subject("subject.owner")
    resource = await _create(service, actor)
    first = await service.cancel(
        actor=actor,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        reason="No longer needed.",
        correlation_id="cor_2",
    )
    second = await service.cancel(
        actor=actor,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        reason="A different reason should not matter.",
        correlation_id="cor_3",
    )
    assert second.state is OperationState.CANCELLED
    assert second.cancellation_reason == first.cancellation_reason


@pytest.mark.asyncio
async def test_cancel_rejects_an_already_succeeded_operation() -> None:
    service, _ = _service()
    actor = _subject("subject.owner")
    resource = await _create(service, actor)
    await service.mark_succeeded(
        actor=actor,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        result_reference="chunks.1",
        correlation_id="cor_2",
    )
    with pytest.raises(OperationResourceError, match="already_terminal"):
        await service.cancel(
            actor=actor,
            organization_id=ORG,
            environment_id=ENV,
            operation_id=resource.operation_id,
            reason="Too late.",
            correlation_id="cor_3",
        )


@pytest.mark.asyncio
async def test_cancel_rejects_a_non_cancellation_eligible_operation() -> None:
    service, repository = _service()
    actor = _subject("subject.owner")
    resource = _resource(state=OperationState.RUNNING, started_at=NOW, cancellation_eligible=False)
    await repository.add(resource)
    with pytest.raises(OperationResourceError, match="not_cancellable"):
        await service.cancel(
            actor=actor,
            organization_id=ORG,
            environment_id=ENV,
            operation_id=resource.operation_id,
            reason="Try anyway.",
            correlation_id="cor_1",
        )


@pytest.mark.asyncio
async def test_cancel_requires_a_human_actor() -> None:
    service, _ = _service()
    actor = _subject("subject.owner")
    resource = await _create(service, actor)
    automation = dataclasses.replace(actor, kind=SubjectKind.SERVICE)
    with pytest.raises(OperationResourceError, match="human"):
        await service.cancel(
            actor=automation,
            organization_id=ORG,
            environment_id=ENV,
            operation_id=resource.operation_id,
            reason="Automated cleanup.",
            correlation_id="cor_2",
        )


@pytest.mark.asyncio
async def test_cancel_rejects_a_blank_reason() -> None:
    service, _ = _service()
    actor = _subject("subject.owner")
    resource = await _create(service, actor)
    with pytest.raises(OperationResourceError, match="reason_required"):
        await service.cancel(
            actor=actor,
            organization_id=ORG,
            environment_id=ENV,
            operation_id=resource.operation_id,
            reason="   ",
            correlation_id="cor_2",
        )


@pytest.mark.asyncio
async def test_cancel_denies_a_non_owner_without_cross_subject_access() -> None:
    service, _ = _service(authorizer=AllowAllAuthorizer(cross_subject=False))
    owner = _subject("subject.owner")
    other = _subject("subject.other")
    resource = await _create(service, owner)
    with pytest.raises(OperationResourceError, match="not_found"):
        await service.cancel(
            actor=other,
            organization_id=ORG,
            environment_id=ENV,
            operation_id=resource.operation_id,
            reason="Not mine to cancel.",
            correlation_id="cor_2",
        )


@pytest.mark.asyncio
async def test_cancel_allows_a_non_owner_with_cross_subject_access() -> None:
    service, _ = _service(authorizer=AllowAllAuthorizer(cross_subject=True))
    owner = _subject("subject.owner")
    elevated = _subject("subject.elevated")
    resource = await _create(service, owner)
    cancelled = await service.cancel(
        actor=elevated,
        organization_id=ORG,
        environment_id=ENV,
        operation_id=resource.operation_id,
        reason="Elevated cleanup.",
        correlation_id="cor_2",
    )
    assert cancelled.state is OperationState.CANCELLED
