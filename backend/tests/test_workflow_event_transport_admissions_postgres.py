from __future__ import annotations

from datetime import UTC, datetime
from inspect import getsource
from pathlib import Path
from typing import Any, cast

from sqlalchemy import Table

from atlas.core.persistence.models import (
    WorkflowEventTransportAdmissionClaimModel,
    WorkflowEventTransportAdmissionModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application.transport_admission_ports import (
    WorkflowEventTransportAdmissionRequest,
)
from atlas.modules.workflows.domain import (
    WorkflowEventTransportAdmission,
    WorkflowEventTransportAdmissionAuthority,
    WorkflowEventTransportAdmissionState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_transport_admission_policy,
)

NOW = datetime(2026, 8, 14, 21, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.atlas", "environment.development", "site.local")


def _admission() -> WorkflowEventTransportAdmission:
    policy = code_owned_workflow_event_transport_admission_policy()
    authority = WorkflowEventTransportAdmissionAuthority()
    values: dict[str, object] = {
        "admission_id": "workflow-transport-admission.postgres-01",
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "event_id": "workflow-dispatch-event.transport-postgres-01",
        "event_digest": "1" * 64,
        "event_type": "WorkflowStepDispatchRequested",
        "event_version": "1.0",
        "schema_uri": "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
        "data_classification": "internal",
        "representation_name": policy.representation_name,
        "encoding": policy.encoding,
        "canonical_byte_count": 4096,
        "maximum_canonical_byte_count": policy.maximum_canonical_byte_count,
        "outbox_entry_id": "workflow-outbox.transport-postgres-01",
        "outbox_entry_digest": "2" * 64,
        "dispatch_intent_id": "workflow-dispatch-intent.transport-postgres-01",
        "dispatch_intent_digest": "3" * 64,
        "plan_id": "workflow-plan.transport-postgres-01",
        "plan_digest": "4" * 64,
        "run_id": "workflow-run.transport-postgres-01",
        "run_digest": "5" * 64,
        "step_run_id": "workflow-step-run.transport-postgres-01",
        "step_run_digest": "6" * 64,
        "step_id": "step.transport-postgres-01",
        "attempt_id": "workflow-attempt.transport-postgres-01",
        "attempt_digest": "7" * 64,
        "attempt_number": 1,
        "scope": SCOPE,
        "target_id": "asset.storage.lab.primary",
        "target_type": "storage",
        "orchestration_lease_id": "workflow-lease.transport-postgres-01",
        "orchestration_lease_digest": "8" * 64,
        "orchestration_fencing_token": 4,
        "publication_lease_id": "workflow-publication-lease.transport-postgres-01",
        "publication_lease_digest": "9" * 64,
        "publication_fencing_token": 3,
        "publisher_subject_id": "workload.atlas.workflow-outbox-publisher-01",
        "admitted_at": NOW,
        "state": WorkflowEventTransportAdmissionState.ADMITTED,
        "authority": authority,
    }
    digest_payload = {
        key: value.canonical_value()
        if isinstance(value, (WorkflowScope, WorkflowEventTransportAdmissionAuthority))
        else value.isoformat()
        if isinstance(value, datetime)
        else value.value
        if isinstance(value, WorkflowEventTransportAdmissionState)
        else value
        for key, value in values.items()
    }
    return WorkflowEventTransportAdmission(
        **cast(Any, values),
        canonical_digest=canonical_digest(digest_payload),
    )


def _request() -> WorkflowEventTransportAdmissionRequest:
    admission = _admission()
    return WorkflowEventTransportAdmissionRequest(
        expected_plan_digest=admission.plan_digest,
        expected_outbox_entry_digest=admission.outbox_entry_digest,
        expected_event_id=admission.event_id,
        expected_event_digest=admission.event_digest,
        expected_policy_digest=admission.policy_digest,
        expected_orchestration_lease_id=admission.orchestration_lease_id,
        expected_orchestration_lease_digest=admission.orchestration_lease_digest,
        expected_orchestration_fencing_token=admission.orchestration_fencing_token,
        expected_publication_lease_id=admission.publication_lease_id,
        expected_publication_lease_digest=admission.publication_lease_digest,
        expected_publication_fencing_token=admission.publication_fencing_token,
        publisher_subject_id=admission.publisher_subject_id,
        requested_at=NOW,
        candidate=admission,
        idempotency_key="event-transport-admission-postgres-0001",
        request_fingerprint="a" * 64,
    )


def test_transport_admission_models_are_immutable_unique_and_zero_authority() -> None:
    admission_table = cast(Table, WorkflowEventTransportAdmissionModel.__table__)
    claim_table = cast(Table, WorkflowEventTransportAdmissionClaimModel.__table__)
    admission_constraints = {constraint.name for constraint in admission_table.constraints}
    claim_constraints = {constraint.name for constraint in claim_table.constraints}

    assert {
        "uq_workflow_event_transport_admission_event",
        "uq_workflow_event_transport_admission_outbox",
        "uq_workflow_event_transport_admission_digest",
        "ck_workflow_event_transport_admission_attempt_number",
        "ck_workflow_event_transport_admission_byte_count",
        "ck_workflow_event_transport_admission_state",
        "ck_workflow_event_transport_admission_zero_authority",
    } <= admission_constraints
    assert {
        "uq_workflow_event_transport_admission_scope_idem",
        "uq_workflow_event_transport_admission_claim_admission",
        "uq_workflow_event_transport_admission_claim_event",
        "uq_workflow_event_transport_admission_claim_outbox",
    } <= claim_constraints
    foreign_targets = {
        str(foreign_key.target_fullname) for foreign_key in admission_table.foreign_keys
    }
    assert not any("orchestration_leases" in target for target in foreign_targets)
    assert not any("publication_leases" in target for target in foreign_targets)
    assert {
        "provider",
        "broker",
        "endpoint",
        "queue",
        "topic",
        "routing_key",
        "partition",
        "credential",
        "wire_payload",
        "serialized_artifact",
        "serialization_format",
        "publication_attempt",
        "retry_schedule",
        "receipt",
        "delivery_acknowledgement",
        "worker_reservation",
        "execution_result",
    }.isdisjoint(admission_table.columns.keys())


def test_transport_admission_and_claim_round_trip_exactly() -> None:
    request = _request()
    admission_row = PostgreSQLWorkflowPlanRepository._event_transport_admission_model(
        request.candidate
    )
    claim_row = PostgreSQLWorkflowPlanRepository._event_transport_admission_claim_model(request)

    assert (
        PostgreSQLWorkflowPlanRepository._event_transport_admission_from_row(admission_row)
        == request.candidate
    )
    claim = PostgreSQLWorkflowPlanRepository._event_transport_admission_record_from_claim(claim_row)
    assert claim.request_fingerprint == request.request_fingerprint
    assert claim.admission == request.candidate
    assert claim_row.admission_id == request.candidate.admission_id
    assert claim_row.event_id == request.candidate.event_id
    assert claim_row.outbox_entry_id == request.candidate.outbox_entry_id


def test_transport_admission_repository_locks_all_sources_and_commits_atomically() -> None:
    source = getsource(PostgreSQLWorkflowPlanRepository.admit_event_transport)

    for model_name in (
        "WorkflowRunPlanModel",
        "WorkflowDispatchOutboxEntryModel",
        "WorkflowOrchestrationLeaseModel",
        "WorkflowOutboxPublicationLeaseModel",
        "WorkflowDispatchEventEnvelopeModel",
    ):
        assert model_name in source
    assert source.count(".with_for_update()") == 5
    assert "session.add(self._event_transport_admission_model(candidate))" in source
    assert "session.add(self._event_transport_admission_claim_model(request))" in source
    assert "await session.commit()" in source

    evidence_source = getsource(
        PostgreSQLWorkflowPlanRepository._event_transport_admission_evidence_matches
    )
    for evidence in (
        "expected_plan_digest",
        "expected_outbox_entry_digest",
        "expected_event_digest",
        "expected_policy_digest",
        "orchestration_fencing_token",
        "publication_fencing_token",
        "canonical_json_byte_count",
        "PENDING_PUBLICATION",
        "PREPARED",
    ):
        assert evidence in evidence_source


def test_transport_admission_migration_follows_envelope_head_without_transport_fields() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0116_workflow_event_transport_admissions.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260814_0116"' in migration
    assert 'down_revision: str | None = "20260814_0115"' in migration
    assert "workflow_event_transport_admissions" in migration
    assert "workflow_event_transport_admission_claims" in migration
    assert "fk_workflow_event_transport_admission_event" in migration
    assert "workflow_orchestration_leases.lease_id" not in migration
    assert "workflow_dispatch_outbox_publication_leases.publication_lease_id" not in migration
    for field in (
        '"provider"',
        '"broker"',
        '"endpoint"',
        '"queue"',
        '"topic"',
        '"routing_key"',
        '"partition"',
        '"credential"',
        '"wire_payload"',
        '"serialized_artifact"',
        '"serialization_format"',
        '"publication_attempt"',
        '"retry_schedule"',
        '"receipt"',
        '"delivery_acknowledgement"',
        '"worker_reservation"',
        '"execution_result"',
    ):
        assert field not in migration
