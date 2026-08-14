from __future__ import annotations

from datetime import UTC, datetime
from inspect import getsource
from pathlib import Path
from typing import cast

from sqlalchemy import Table

from atlas.core.persistence.models import (
    WorkflowDispatchEventEnvelopeModel,
    WorkflowDispatchEventEnvelopePreparationClaimModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application.event_envelope_ports import (
    WorkflowDispatchEventEnvelopePrepareRequest,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchEventAuthority,
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchEventEnvelopeState,
    WorkflowDispatchEventPayload,
    WorkflowScope,
    canonical_digest,
)

NOW = datetime(2026, 8, 14, 20, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.atlas", "environment.development", "site.local")


def _envelope() -> WorkflowDispatchEventEnvelope:
    event_payload = WorkflowDispatchEventPayload(
        outbox_entry_id="workflow-outbox.event-postgres-01",
        outbox_entry_digest="1" * 64,
        dispatch_intent_id="workflow-dispatch-intent.event-postgres-01",
        dispatch_intent_digest="2" * 64,
        plan_id="workflow-plan.event-postgres-01",
        plan_digest="3" * 64,
        run_id="workflow-run.event-postgres-01",
        run_digest="4" * 64,
        step_run_id="workflow-step-run.event-postgres-01",
        step_run_digest="5" * 64,
        step_id="step.event-postgres-01",
        attempt_id="workflow-attempt.event-postgres-01",
        attempt_digest="6" * 64,
        attempt_number=1,
        scope=SCOPE,
        target_id="asset.storage.lab.primary",
        target_type="storage",
    )
    authority = WorkflowDispatchEventAuthority()
    values: dict[str, object] = {
        "event_id": "workflow-dispatch-event.event-postgres-01",
        "event_type": "WorkflowStepDispatchRequested",
        "event_version": "1.0",
        "occurred_at": NOW,
        "recorded_at": NOW,
        "producer": "atlas.workflow-outbox-publisher",
        "producer_version": "1.0",
        "subject_type": "workflow-execution-attempt",
        "subject_id": event_payload.attempt_id,
        "organization_id": SCOPE.organization_id,
        "environment_id": SCOPE.environment_id,
        "correlation_id": event_payload.run_id,
        "causation_id": event_payload.dispatch_intent_id,
        "workflow_id": event_payload.run_id,
        "data_classification": "internal",
        "schema_uri": "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
        "payload": event_payload,
        "extensions": (),
        "orchestration_lease_id": "workflow-lease.event-postgres-01",
        "orchestration_lease_digest": "7" * 64,
        "orchestration_fencing_token": 4,
        "publication_lease_id": "workflow-publication-lease.event-postgres-01",
        "publication_lease_digest": "8" * 64,
        "publication_fencing_token": 3,
        "publisher_subject_id": "workload.atlas.workflow-outbox-publisher-01",
        "prepared_at": NOW,
        "state": WorkflowDispatchEventEnvelopeState.PREPARED,
        "authority": authority,
    }
    digest_payload = {
        key: value.canonical_value()
        if isinstance(value, (WorkflowDispatchEventPayload, WorkflowDispatchEventAuthority))
        else {}
        if key == "extensions"
        else value.isoformat()
        if isinstance(value, datetime)
        else value.value
        if isinstance(value, WorkflowDispatchEventEnvelopeState)
        else value
        for key, value in values.items()
    }
    return WorkflowDispatchEventEnvelope(
        **cast(dict[str, object], values),
        canonical_digest=canonical_digest(digest_payload),
    )


def _request() -> WorkflowDispatchEventEnvelopePrepareRequest:
    envelope = _envelope()
    return WorkflowDispatchEventEnvelopePrepareRequest(
        expected_outbox_entry_digest=envelope.payload.outbox_entry_digest,
        expected_plan_digest=envelope.payload.plan_digest,
        expected_orchestration_lease_id=envelope.orchestration_lease_id,
        expected_orchestration_lease_digest=envelope.orchestration_lease_digest,
        expected_orchestration_fencing_token=envelope.orchestration_fencing_token,
        expected_publication_lease_id=envelope.publication_lease_id,
        expected_publication_lease_digest=envelope.publication_lease_digest,
        expected_publication_fencing_token=envelope.publication_fencing_token,
        publisher_subject_id=envelope.publisher_subject_id,
        requested_at=NOW,
        candidate=envelope,
        idempotency_key="dispatch-event-envelope-prepare-postgres-0001",
        request_fingerprint="9" * 64,
    )


def test_dispatch_event_models_are_immutable_unique_and_zero_authority() -> None:
    envelope_table = cast(Table, WorkflowDispatchEventEnvelopeModel.__table__)
    claim_table = cast(Table, WorkflowDispatchEventEnvelopePreparationClaimModel.__table__)
    envelope_constraints = {constraint.name for constraint in envelope_table.constraints}
    claim_constraints = {constraint.name for constraint in claim_table.constraints}

    assert {
        "uq_workflow_dispatch_event_envelope_outbox",
        "uq_workflow_dispatch_event_envelope_event",
        "uq_workflow_dispatch_event_envelope_digest",
        "ck_workflow_dispatch_event_envelope_attempt_number",
        "ck_workflow_dispatch_event_envelope_state",
        "ck_workflow_dispatch_event_envelope_zero_authority",
    } <= envelope_constraints
    assert {
        "uq_workflow_dispatch_event_envelope_scope_idem",
        "uq_workflow_dispatch_event_envelope_claim_event",
        "uq_workflow_dispatch_event_envelope_claim_outbox",
    } <= claim_constraints
    foreign_targets = {
        str(foreign_key.target_fullname) for foreign_key in envelope_table.foreign_keys
    }
    assert not any("orchestration_leases" in target for target in foreign_targets)
    assert not any("publication_leases" in target for target in foreign_targets)
    assert {
        "broker",
        "endpoint",
        "queue",
        "topic",
        "routing_key",
        "partition",
        "credential",
        "serialized_payload",
        "publication_attempt",
        "receipt",
    }.isdisjoint(envelope_table.columns.keys())


def test_dispatch_event_envelope_and_claim_round_trip_exactly() -> None:
    request = _request()
    envelope_row = PostgreSQLWorkflowPlanRepository._dispatch_event_envelope_model(
        request.candidate
    )
    claim_row = PostgreSQLWorkflowPlanRepository._dispatch_event_envelope_claim_model(request)

    assert PostgreSQLWorkflowPlanRepository._dispatch_event_envelope_from_row(envelope_row) == (
        request.candidate
    )
    claim = PostgreSQLWorkflowPlanRepository._dispatch_event_envelope_record_from_claim(claim_row)
    assert claim.request_fingerprint == request.request_fingerprint
    assert claim.envelope == request.candidate
    assert claim_row.event_id == request.candidate.event_id
    assert claim_row.outbox_entry_id == request.candidate.payload.outbox_entry_id


def test_dispatch_event_repository_locks_sources_and_commits_atomically() -> None:
    source = getsource(PostgreSQLWorkflowPlanRepository.prepare_dispatch_event_envelope)

    for model_name in (
        "WorkflowRunPlanModel",
        "WorkflowDispatchOutboxEntryModel",
        "WorkflowOrchestrationLeaseModel",
        "WorkflowOutboxPublicationLeaseModel",
    ):
        assert model_name in source
    assert source.count(".with_for_update()") == 4
    assert "session.add(self._dispatch_event_envelope_model(candidate))" in source
    assert "session.add(self._dispatch_event_envelope_claim_model(request))" in source
    assert "await session.commit()" in source
    assert "publication_fencing_token" in getsource(
        PostgreSQLWorkflowPlanRepository._dispatch_event_envelope_evidence_matches
    )


def test_dispatch_event_migration_follows_publication_lease_head_without_transport_fields() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0115_workflow_dispatch_event_envelopes.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260814_0115"' in migration
    assert 'down_revision: str | None = "20260814_0114"' in migration
    assert "workflow_dispatch_event_envelopes" in migration
    assert "workflow_dispatch_event_envelope_preparation_claims" in migration
    assert "fk_workflow_dispatch_event_envelope_outbox" in migration
    assert "workflow_orchestration_leases.lease_id" not in migration
    assert "workflow_dispatch_outbox_publication_leases.publication_lease_id" not in migration
    for field in (
        '"broker"',
        '"endpoint"',
        '"queue"',
        '"topic"',
        '"routing_key"',
        '"partition"',
        '"credential"',
        '"serialized_payload"',
        '"publication_attempt"',
        '"receipt"',
    ):
        assert field not in migration
