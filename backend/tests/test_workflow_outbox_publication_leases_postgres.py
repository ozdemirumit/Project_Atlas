from __future__ import annotations

from datetime import UTC, datetime, timedelta
from inspect import getsource
from pathlib import Path
from typing import cast

from sqlalchemy import Table

from atlas.core.persistence.models import (
    WorkflowOutboxPublicationLeaseAcquireClaimModel,
    WorkflowOutboxPublicationLeaseModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application import WorkflowOutboxPublicationLeaseAcquireRequest
from atlas.modules.workflows.domain import (
    WorkflowOutboxPublicationLease,
    WorkflowOutboxPublicationLeaseState,
    WorkflowPlanAuthority,
    WorkflowScope,
    canonical_digest,
)

NOW = datetime(2026, 8, 14, 18, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.atlas", "environment.development", "site.local")


def _lease() -> WorkflowOutboxPublicationLease:
    values: dict[str, object] = {
        "publication_lease_id": "workflow-publication-lease.postgres-01",
        "outbox_entry_id": "workflow-outbox.postgres-01",
        "outbox_entry_digest": "1" * 64,
        "dispatch_intent_id": "workflow-dispatch-intent.postgres-01",
        "dispatch_intent_digest": "2" * 64,
        "plan_id": "workflow-plan.postgres-01",
        "plan_digest": "3" * 64,
        "run_id": "workflow-run.postgres-01",
        "run_digest": "4" * 64,
        "step_run_id": "workflow-step-run.postgres-01",
        "step_run_digest": "5" * 64,
        "step_id": "step.postgres-01",
        "attempt_id": "workflow-attempt.postgres-01",
        "attempt_digest": "6" * 64,
        "attempt_number": 1,
        "scope": SCOPE,
        "target_id": "asset.storage.lab.primary",
        "target_type": "storage",
        "orchestration_lease_id": "workflow-lease.postgres-01",
        "orchestration_lease_digest": "7" * 64,
        "orchestration_fencing_token": 4,
        "publisher_subject_id": "workload.atlas.workflow-outbox-publisher-01",
        "acquired_at": NOW,
        "last_heartbeat_at": NOW,
        "expires_at": NOW + timedelta(seconds=90),
        "publication_fencing_token": 3,
        "state": WorkflowOutboxPublicationLeaseState.ACTIVE,
        "authority": WorkflowPlanAuthority(),
    }
    digest_payload = {
        key: value.canonical_value()
        if isinstance(value, (WorkflowScope, WorkflowPlanAuthority))
        else value.isoformat()
        if isinstance(value, datetime)
        else value.value
        if isinstance(value, WorkflowOutboxPublicationLeaseState)
        else value
        for key, value in values.items()
    }
    return WorkflowOutboxPublicationLease(
        publication_lease_id=cast(str, values["publication_lease_id"]),
        outbox_entry_id=cast(str, values["outbox_entry_id"]),
        outbox_entry_digest=cast(str, values["outbox_entry_digest"]),
        dispatch_intent_id=cast(str, values["dispatch_intent_id"]),
        dispatch_intent_digest=cast(str, values["dispatch_intent_digest"]),
        plan_id=cast(str, values["plan_id"]),
        plan_digest=cast(str, values["plan_digest"]),
        run_id=cast(str, values["run_id"]),
        run_digest=cast(str, values["run_digest"]),
        step_run_id=cast(str, values["step_run_id"]),
        step_run_digest=cast(str, values["step_run_digest"]),
        step_id=cast(str, values["step_id"]),
        attempt_id=cast(str, values["attempt_id"]),
        attempt_digest=cast(str, values["attempt_digest"]),
        attempt_number=1,
        scope=SCOPE,
        target_id=cast(str, values["target_id"]),
        target_type="storage",
        orchestration_lease_id=cast(str, values["orchestration_lease_id"]),
        orchestration_lease_digest=cast(str, values["orchestration_lease_digest"]),
        orchestration_fencing_token=4,
        publisher_subject_id=cast(str, values["publisher_subject_id"]),
        acquired_at=NOW,
        last_heartbeat_at=NOW,
        expires_at=NOW + timedelta(seconds=90),
        publication_fencing_token=3,
        state=WorkflowOutboxPublicationLeaseState.ACTIVE,
        authority=WorkflowPlanAuthority(),
        canonical_digest=canonical_digest(digest_payload),
    )


def _request() -> WorkflowOutboxPublicationLeaseAcquireRequest:
    lease = _lease()
    return WorkflowOutboxPublicationLeaseAcquireRequest(
        expected_outbox_entry_digest=lease.outbox_entry_digest,
        expected_orchestration_lease_id=lease.orchestration_lease_id,
        expected_orchestration_lease_digest=lease.orchestration_lease_digest,
        expected_orchestration_fencing_token=lease.orchestration_fencing_token,
        candidate=lease,
        requested_at=NOW,
        idempotency_key="publication-lease-postgres-acquire-0001",
        request_fingerprint="8" * 64,
        expected_current_lease_digest=None,
        expected_current_publication_fencing_token=None,
    )


def test_publication_lease_models_are_provider_neutral_and_uniquely_fenced() -> None:
    lease_table = cast(Table, WorkflowOutboxPublicationLeaseModel.__table__)
    claim_table = cast(Table, WorkflowOutboxPublicationLeaseAcquireClaimModel.__table__)
    lease_constraints = {constraint.name for constraint in lease_table.constraints}
    claim_constraints = {constraint.name for constraint in claim_table.constraints}

    assert "uq_workflow_dispatch_outbox_publication_lease_entry" in lease_constraints
    assert "ck_workflow_dispatch_outbox_publication_lease_fence" in lease_constraints
    assert "ck_workflow_dispatch_outbox_publication_orchestration_fence" in lease_constraints
    assert "ck_workflow_dispatch_outbox_publication_attempt_number" in lease_constraints
    assert "uq_workflow_dispatch_outbox_publication_lease_scope_idem" in claim_constraints
    assert "outbox_entry_id" in lease_table.columns
    assert "orchestration_lease_id" in lease_table.columns
    assert {
        "broker",
        "broker_address",
        "queue",
        "topic",
        "routing_key",
        "message_payload",
        "serialized_payload",
        "published_at",
        "delivered_at",
    }.isdisjoint(lease_table.columns.keys())


def test_publication_lease_and_claim_payloads_round_trip_exactly() -> None:
    request = _request()
    lease_row = PostgreSQLWorkflowPlanRepository._publication_lease_model(
        request.candidate,
        version=1,
    )
    claim_row = PostgreSQLWorkflowPlanRepository._publication_lease_claim_model(request)

    assert PostgreSQLWorkflowPlanRepository._publication_lease_from_row(lease_row) == (
        request.candidate
    )
    claim = PostgreSQLWorkflowPlanRepository._publication_lease_record_from_claim(claim_row)
    assert claim.request_fingerprint == request.request_fingerprint
    assert claim.lease == request.candidate
    assert lease_row.version == 1
    assert claim_row.publication_lease_id == request.candidate.publication_lease_id


def test_publication_lease_repository_locks_exact_evidence_and_commits_atomically() -> None:
    acquire_source = getsource(PostgreSQLWorkflowPlanRepository.acquire_publication_lease)
    mutation_source = getsource(PostgreSQLWorkflowPlanRepository._mutate_publication_lease)

    for model_name in (
        "WorkflowDispatchOutboxEntryModel",
        "WorkflowRunPlanModel",
        "WorkflowOrchestrationLeaseModel",
        "WorkflowOutboxPublicationLeaseModel",
    ):
        assert model_name in acquire_source
        assert model_name in mutation_source
    assert acquire_source.count(".with_for_update()") == 4
    assert mutation_source.count(".with_for_update()") == 4
    assert "session.add(self._publication_lease_claim_model(request))" in acquire_source
    assert "await session.commit()" in acquire_source
    assert "await session.commit()" in mutation_source
    assert "publication_fencing_token" in acquire_source
    assert "publication_fencing_token" in mutation_source


def test_publication_lease_migration_follows_outbox_head_without_broker_fields() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0114_workflow_outbox_publication_leases.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260814_0114"' in migration
    assert 'down_revision: str | None = "20260814_0113"' in migration
    assert "workflow_dispatch_outbox_publication_leases" in migration
    assert "workflow_dispatch_outbox_publication_lease_acquire_claims" in migration
    assert "fk_workflow_dispatch_outbox_publication_lease_entry" in migration
    assert "workflow_orchestration_leases.lease_id" not in migration
    for field in (
        '"broker"',
        '"queue"',
        '"topic"',
        '"routing_key"',
        '"serialized_payload"',
        '"published_at"',
        '"delivered_at"',
    ):
        assert field not in migration
