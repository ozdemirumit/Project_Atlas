from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from test_workflow_physical_transport_route_bindings_postgres import (
    _integration_request as physical_route_binding_request,
)
from test_workflow_transport_credential_assignment_bindings_postgres import (
    _request as credential_binding_request,
)
from test_workflow_transport_credential_assignment_snapshots import assignment_fixture

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingService,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService,
    WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionError,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionRepository,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest,
    WorkflowTransportCredentialAssignmentSnapshotService,
)
from atlas.modules.workflows.domain import (
    DeploymentPhysicalTransportCredentialAssignment,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_assignment_freshness_policy,
)

NOW = datetime(2026, 8, 15, 12, 10, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self, *, fail_kind: str | None = None) -> None:
        self.records: list[AuditRecord] = []
        self.fail_kind = fail_kind

    async def record(self, event: AuditRecord) -> None:
        if self.fail_kind is not None and event.event_type.endswith(f".{self.fail_kind}"):
            raise RuntimeError("audit unavailable")
        self.records.append(event)


def _head_from_snapshot(
    *,
    route: Any,
    snapshot: Any,
    active: bool = True,
    revoked: bool = False,
    assignment_revision: str | None = None,
    credential_generation: int | None = None,
    rotation_epoch: int | None = None,
) -> DeploymentPhysicalTransportCredentialAssignment:
    return assignment_fixture(
        assignment_id=snapshot.assignment_id,
        assignment_revision=assignment_revision or snapshot.assignment_revision,
        route=route,
        scope=snapshot.scope,
        active=active,
        revoked=revoked,
        credential_generation=credential_generation or snapshot.credential_generation,
        rotation_epoch=rotation_epoch or snapshot.rotation_epoch,
        activated_at=snapshot.activated_at,
        expires_at=snapshot.expires_at,
    )


def _context(
    *,
    scope: WorkflowScope,
    requested_at: datetime = NOW,
    subject_id: str = (
        WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT
    ),
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = (WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE),
) -> WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext:
    return WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=scope,
        correlation_id="correlation.credential-assignment-freshness.0001",
        decision_id="decision.credential-assignment-freshness.0001",
        requested_at=requested_at,
    )


def _fixture(
    *,
    audit: CollectingAuditSink | None = None,
) -> tuple[
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService,
    InMemoryWorkflowPlanRepository,
    CollectingAuditSink,
    Any,
    Any,
    DeploymentPhysicalTransportCredentialAssignment,
]:
    request, route, snapshot = credential_binding_request()
    binding = request.candidate
    head = _head_from_snapshot(route=route, snapshot=snapshot)
    repository = InMemoryWorkflowPlanRepository()
    repository._credential_assignment_bindings[
        (binding.physical_transport_route_binding_id, snapshot.snapshot_id)
    ] = binding
    repository._credential_assignment_snapshots[
        (snapshot.assignment_id, snapshot.assignment_revision)
    ] = snapshot
    repository._credential_assignments[(head.assignment_id, head.assignment_revision)] = head
    sink = audit or CollectingAuditSink()
    service = WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService(
        admission_repository=repository,
        audit_sink=sink,
    )
    return service, repository, sink, binding, snapshot, head


async def _admit(
    service: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService,
    *,
    binding: Any,
    requested_at: datetime = NOW,
    idempotency_key: str = "credential-assignment-freshness-0001",
    context: WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext | None = None,
) -> Any:
    policy = service.policy
    return await service.admit(
        physical_transport_credential_assignment_binding_id=binding.binding_id,
        physical_transport_credential_assignment_binding_digest=binding.canonical_digest,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        idempotency_key=idempotency_key,
        context=context or _context(scope=binding.scope, requested_at=requested_at),
    )


@pytest.mark.asyncio
async def test_in_memory_admits_unique_current_max_rank_and_exact_replay() -> None:
    service, repository, audit, binding, snapshot, head = _fixture()

    admission = await _admit(service, binding=binding)
    replay = await _admit(service, binding=binding)

    assert replay == admission
    assert admission.assignment_revision == head.assignment_revision
    assert admission.credential_generation == head.credential_generation
    assert admission.rotation_epoch == head.rotation_epoch
    assert admission.valid_until - admission.evaluated_at == timedelta(seconds=60)
    assert len(admission.authority.canonical_value()) == 17
    assert not any(admission.authority.canonical_value().values())
    assert len(repository._credential_assignment_freshness_admissions) == 1
    assert [record.event_type.rsplit(".", 1)[-1] for record in audit.records] == [
        "intent",
        "authorization",
        "created",
        "intent",
        "replay",
    ]

    newer = _head_from_snapshot(
        route=credential_binding_request()[1],
        snapshot=snapshot,
        assignment_revision="14",
        credential_generation=head.credential_generation + 1,
        rotation_epoch=head.rotation_epoch,
    )
    repository._credential_assignments[(newer.assignment_id, newer.assignment_revision)] = newer
    assert (
        await repository.get_current_credential_assignment_head(assignment_id=head.assignment_id)
        == newer
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("active", "revoked"),
    ((False, False), (True, True)),
)
async def test_newer_inactive_or_revoked_head_blocks_older_bound_active_revision(
    active: bool,
    revoked: bool,
) -> None:
    service, repository, _, binding, snapshot, head = _fixture()
    newer = _head_from_snapshot(
        route=credential_binding_request()[1],
        snapshot=snapshot,
        active=active,
        revoked=revoked,
        assignment_revision="14",
        credential_generation=head.credential_generation + 1,
    )
    repository._credential_assignments[(newer.assignment_id, newer.assignment_revision)] = newer

    with pytest.raises(WorkflowTransportCredentialAssignmentFreshnessAdmissionError) as error:
        await _admit(service, binding=binding)

    assert error.value.code.endswith("_evidence_conflict")
    assert repository._credential_assignment_freshness_admissions == {}


@pytest.mark.asyncio
async def test_ambiguous_max_rank_and_tampered_source_fail_closed() -> None:
    service, repository, _, binding, snapshot, head = _fixture()
    ambiguous = _head_from_snapshot(
        route=credential_binding_request()[1],
        snapshot=snapshot,
        assignment_revision="14",
    )
    repository._credential_assignments[(ambiguous.assignment_id, ambiguous.assignment_revision)] = (
        ambiguous
    )
    assert (
        await repository.get_current_credential_assignment_head(assignment_id=head.assignment_id)
        is None
    )
    with pytest.raises(WorkflowTransportCredentialAssignmentFreshnessAdmissionError) as conflict:
        await _admit(service, binding=binding)
    assert conflict.value.code.endswith("_evidence_conflict")

    repository._credential_assignments.pop((ambiguous.assignment_id, ambiguous.assignment_revision))
    tampered_payload = head.digest_payload() | {"credential_profile_digest": "a" * 64}
    repository._credential_assignments[(head.assignment_id, head.assignment_revision)] = replace(
        head,
        credential_profile_digest="a" * 64,
        canonical_digest=canonical_digest(tampered_payload),
    )
    with pytest.raises(WorkflowTransportCredentialAssignmentFreshnessAdmissionError) as tampered:
        await _admit(service, binding=binding, idempotency_key="freshness-tampered-0001")
    assert tampered.value.code.endswith("_evidence_conflict")


@pytest.mark.asyncio
async def test_validity_is_capped_by_assignment_expiry_and_domain_rejects_over_60_seconds() -> None:
    service, repository, _, binding, snapshot, head = _fixture()
    near_expiry_at = NOW + timedelta(seconds=17)
    near_expiry_payload = head.digest_payload() | {"expires_at": near_expiry_at.isoformat()}
    near_expiry = replace(
        head,
        expires_at=near_expiry_at,
        canonical_digest=canonical_digest(near_expiry_payload),
    )
    route = credential_binding_request()[1]
    matching_snapshot = WorkflowTransportCredentialAssignmentSnapshotService._build_snapshot(
        assignment=near_expiry,
        route=route,
        snapshotter_subject_id=snapshot.snapshotter_subject_id,
        captured_at=snapshot.captured_at,
    )
    binding_service = WorkflowEventPhysicalTransportCredentialAssignmentBindingService(
        binding_repository=cast(Any, object()),
        audit_sink=cast(Any, object()),
    )
    matching_binding = binding_service._build_binding(
        route_binding=physical_route_binding_request().candidate,
        route=route,
        assignment=matching_snapshot,
        binder_subject_id=binding.binder_subject_id,
        bound_at=binding.bound_at,
    )
    repository._credential_assignment_bindings.clear()
    repository._credential_assignment_snapshots.clear()
    repository._credential_assignments.clear()
    repository._credential_assignment_bindings[
        (matching_binding.physical_transport_route_binding_id, matching_snapshot.snapshot_id)
    ] = matching_binding
    repository._credential_assignment_snapshots[
        (matching_snapshot.assignment_id, matching_snapshot.assignment_revision)
    ] = matching_snapshot
    repository._credential_assignments[
        (near_expiry.assignment_id, near_expiry.assignment_revision)
    ] = near_expiry

    admission = await _admit(service, binding=matching_binding)
    assert admission.valid_until == near_expiry.expires_at
    assert admission.valid_until - admission.evaluated_at == timedelta(seconds=17)
    with pytest.raises(ValueError, match="exceeds policy maximum"):
        replace(
            admission,
            valid_until=admission.evaluated_at + timedelta(seconds=61),
            canonical_digest="0" * 64,
        )


@pytest.mark.asyncio
async def test_same_binding_supports_multiple_append_only_admissions() -> None:
    service, repository, _, binding, _, _ = _fixture()
    first = await _admit(service, binding=binding, idempotency_key="freshness-multiple-0001")
    second = await _admit(
        service,
        binding=binding,
        requested_at=NOW + timedelta(seconds=1),
        idempotency_key="freshness-multiple-0002",
    )

    assert first.freshness_admission_id != second.freshness_admission_id
    assert first.physical_transport_credential_assignment_binding_id == (
        second.physical_transport_credential_assignment_binding_id
    )
    assert len(repository._credential_assignment_freshness_admissions) == 2


@pytest.mark.asyncio
async def test_required_precommit_audit_failure_persists_neither_admission_nor_claim() -> None:
    service, repository, _, binding, _, _ = _fixture(
        audit=CollectingAuditSink(fail_kind="authorization")
    )

    with pytest.raises(WorkflowTransportCredentialAssignmentFreshnessAdmissionError) as error:
        await _admit(service, binding=binding)

    assert error.value.code.endswith("_audit_unavailable")
    assert repository._credential_assignment_freshness_admissions == {}
    assert repository._credential_assignment_freshness_admission_requests == {}


@pytest.mark.asyncio
async def test_fixed_subject_audience_and_workload_method_are_mandatory() -> None:
    service, repository, _, binding, _, _ = _fixture()
    cases = (
        _context(scope=binding.scope, subject_id="service.other"),
        _context(scope=binding.scope, actor_type="human"),
        _context(scope=binding.scope, authentication_method="password"),
        _context(scope=binding.scope, audience="audience.other"),
    )
    for index, context in enumerate(cases):
        with pytest.raises(WorkflowTransportCredentialAssignmentFreshnessAdmissionError) as error:
            await _admit(
                service,
                binding=binding,
                context=context,
                idempotency_key=f"freshness-identity-{index:04d}",
            )
        assert error.value.code.endswith("_admitter_identity_required")
    assert repository._credential_assignment_freshness_admissions == {}


@pytest.mark.asyncio
async def test_exact_replay_survives_code_owned_policy_digest_rotation() -> None:
    service, repository, _, binding, _, _ = _fixture()
    admission = await _admit(service, binding=binding)
    current = service.policy

    class RotatedPolicy:
        policy_id = current.policy_id
        policy_version = current.policy_version
        validity_window_seconds = 60
        unique_current_head_required = True
        monotonic_rotation_rank_required = True
        active_assignment_required = True
        non_revoked_assignment_required = True
        assignment_expiry_bound_required = True

        def digest_payload(self) -> dict[str, object]:
            return {**current.digest_payload(), "code_owned_rotation": 2}

        canonical_digest = canonical_digest({**current.digest_payload(), "code_owned_rotation": 2})

    rotated = WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService(
        admission_repository=repository,
        audit_sink=CollectingAuditSink(),
        policy=cast(Any, RotatedPolicy()),
    )
    replay = await _admit(rotated, binding=binding)

    assert replay == admission
    assert replay.policy_digest == current.canonical_digest
    assert replay.policy_digest != rotated.policy.canonical_digest


def test_policy_domain_and_public_surface_are_minimized_and_zero_authority() -> None:
    policy = code_owned_workflow_event_physical_transport_credential_assignment_freshness_policy()
    assert policy.validity_window_seconds == 60
    assert policy.unique_current_head_required
    assert policy.monotonic_rotation_rank_required
    assert policy.active_assignment_required
    assert policy.non_revoked_assignment_required
    assert policy.assignment_expiry_bound_required
    assert policy.canonical_digest == canonical_digest(policy.digest_payload())
    assert (
        len(
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority().canonical_value()
        )
        == 17
    )
    with pytest.raises(ValueError, match="cannot grant authority"):
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority(
            credential_access_authorized=True
        )
    with pytest.raises(ValueError, match="cannot grant authority"):
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority(
            route_selection_authorized=0  # type: ignore[arg-type]
        )

    service, _, _, binding, snapshot, head = _fixture()
    admission = service._build_admission(
        binding=binding,
        snapshot=snapshot,
        head=head,
        admitter_subject_id=(
            WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT
        ),
        evaluated_at=NOW,
        idempotency_key="freshness-model-0001",
    )
    forbidden = {
        "credential_reference",
        "secret_reference",
        "endpoint",
        "hostname",
        "network_result",
        "readiness_result",
        "provider_message",
        "publication_attempt",
    }
    assert forbidden.isdisjoint({field.name for field in fields(type(admission))})
    assert forbidden.isdisjoint(
        {
            field.name
            for field in fields(WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest)
        }
    )
    assert set(inspect.signature(service.admit).parameters) == {
        "physical_transport_credential_assignment_binding_id",
        "physical_transport_credential_assignment_binding_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    assert "list_credential_assignment_freshness_admissions" in dir(
        WorkflowTransportCredentialAssignmentFreshnessAdmissionRepository
    )
