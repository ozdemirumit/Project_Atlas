from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from inspect import getsource, signature
from pathlib import Path
from typing import Any, cast

from sqlalchemy import LargeBinary, Table

from atlas.core.persistence.models import (
    WorkflowEventByteArtifactClaimModel,
    WorkflowEventByteArtifactModel,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application.byte_artifact_ports import (
    WorkflowEventByteArtifactRepository,
    WorkflowEventByteArtifactRequest,
)
from atlas.modules.workflows.domain import (
    WorkflowEventByteArtifact,
    WorkflowEventByteArtifactAuthority,
    WorkflowEventByteArtifactState,
    WorkflowScope,
    canonical_digest,
    canonical_json_bytes,
)

NOW = datetime(2026, 8, 14, 22, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.atlas", "environment.development", "site.local")


def _artifact() -> WorkflowEventByteArtifact:
    canonical_bytes = canonical_json_bytes(
        {"event_id": "workflow-dispatch-event.byte-postgres-01", "version": "1.0"}
    )
    values: dict[str, object] = {
        "artifact_id": "workflow-event-byte-artifact.postgres-01",
        "admission_id": "workflow-transport-admission.byte-postgres-01",
        "admission_digest": "0" * 64,
        "policy_id": "policy.workflow-event-transport-admission",
        "policy_version": "1.0",
        "policy_digest": "1" * 64,
        "event_id": "workflow-dispatch-event.byte-postgres-01",
        "event_digest": "2" * 64,
        "event_type": "WorkflowStepDispatchRequested",
        "event_version": "1.0",
        "schema_uri": "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
        "data_classification": "internal",
        "representation_name": "canonical-json",
        "encoding": "utf-8",
        "canonical_bytes": canonical_bytes,
        "canonical_byte_count": len(canonical_bytes),
        "content_sha256": sha256(canonical_bytes).hexdigest(),
        "maximum_canonical_byte_count": 65_536,
        "outbox_entry_id": "workflow-outbox.byte-postgres-01",
        "outbox_entry_digest": "3" * 64,
        "dispatch_intent_id": "workflow-dispatch-intent.byte-postgres-01",
        "dispatch_intent_digest": "4" * 64,
        "plan_id": "workflow-plan.byte-postgres-01",
        "plan_digest": "5" * 64,
        "run_id": "workflow-run.byte-postgres-01",
        "run_digest": "6" * 64,
        "step_run_id": "workflow-step-run.byte-postgres-01",
        "step_run_digest": "7" * 64,
        "step_id": "step.byte-postgres-01",
        "attempt_id": "workflow-attempt.byte-postgres-01",
        "attempt_digest": "8" * 64,
        "attempt_number": 1,
        "scope": SCOPE,
        "target_id": "asset.storage.lab.primary",
        "target_type": "storage",
        "orchestration_lease_id": "workflow-lease.byte-postgres-01",
        "orchestration_lease_digest": "9" * 64,
        "orchestration_fencing_token": 5,
        "publication_lease_id": "workflow-publication-lease.byte-postgres-01",
        "publication_lease_digest": "a" * 64,
        "publication_fencing_token": 4,
        "publisher_subject_id": "workload.atlas.workflow-outbox-publisher-01",
        "materialized_at": NOW,
        "state": WorkflowEventByteArtifactState.MATERIALIZED,
        "authority": WorkflowEventByteArtifactAuthority(),
    }
    digest_payload = {
        key: value.canonical_value()
        if isinstance(value, (WorkflowEventByteArtifactAuthority, WorkflowScope))
        else value.isoformat()
        if isinstance(value, datetime)
        else value.value
        if isinstance(value, WorkflowEventByteArtifactState)
        else value
        for key, value in values.items()
        if key != "canonical_bytes"
    }
    return WorkflowEventByteArtifact(
        **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
    )


def _request() -> WorkflowEventByteArtifactRequest:
    artifact = _artifact()
    return WorkflowEventByteArtifactRequest(
        expected_plan_digest=artifact.plan_digest,
        expected_outbox_entry_digest=artifact.outbox_entry_digest,
        expected_event_id=artifact.event_id,
        expected_event_digest=artifact.event_digest,
        expected_admission_id=artifact.admission_id,
        expected_admission_digest=artifact.admission_digest,
        expected_policy_digest=artifact.policy_digest,
        expected_orchestration_lease_id=artifact.orchestration_lease_id,
        expected_orchestration_lease_digest=artifact.orchestration_lease_digest,
        expected_orchestration_fencing_token=artifact.orchestration_fencing_token,
        expected_publication_lease_id=artifact.publication_lease_id,
        expected_publication_lease_digest=artifact.publication_lease_digest,
        expected_publication_fencing_token=artifact.publication_fencing_token,
        publisher_subject_id=artifact.publisher_subject_id,
        requested_at=NOW,
        candidate=artifact,
        idempotency_key="event-byte-artifact-postgres-0001",
        request_fingerprint="b" * 64,
    )


def test_byte_artifact_models_are_binary_immutable_and_provider_neutral() -> None:
    artifact_table = cast(Table, WorkflowEventByteArtifactModel.__table__)
    claim_table = cast(Table, WorkflowEventByteArtifactClaimModel.__table__)
    artifact_constraints = {constraint.name for constraint in artifact_table.constraints}
    claim_constraints = {constraint.name for constraint in claim_table.constraints}

    assert isinstance(artifact_table.c.canonical_bytes.type, LargeBinary)
    assert {
        "uq_workflow_event_byte_artifact_admission",
        "uq_workflow_event_byte_artifact_event",
        "uq_workflow_event_byte_artifact_outbox",
        "uq_workflow_event_byte_artifact_content",
        "ck_workflow_event_byte_artifact_binary_length",
        "ck_workflow_event_byte_artifact_state",
        "ck_workflow_event_byte_artifact_zero_authority",
    } <= artifact_constraints
    assert {
        "uq_workflow_event_byte_artifact_scope_idem",
        "uq_workflow_event_byte_artifact_claim_artifact",
        "uq_workflow_event_byte_artifact_claim_admission",
        "uq_workflow_event_byte_artifact_claim_event",
        "uq_workflow_event_byte_artifact_claim_outbox",
    } <= claim_constraints
    foreign_targets = {key.target_fullname for key in artifact_table.foreign_keys}
    assert not any("orchestration_leases" in target for target in foreign_targets)
    assert not any("publication_leases" in target for target in foreign_targets)
    assert {
        "provider",
        "broker",
        "endpoint",
        "route",
        "queue",
        "topic",
        "partition",
        "routing_key",
        "credential",
        "provider_message",
        "publication_attempt",
        "retry_schedule",
        "receipt",
        "delivery_acknowledgement",
        "worker_reservation",
        "execution_result",
    }.isdisjoint(artifact_table.columns.keys())


def test_byte_artifact_and_minimized_claim_round_trip_exactly() -> None:
    request = _request()
    artifact_row = PostgreSQLWorkflowPlanRepository._event_byte_artifact_model(request.candidate)
    claim_row = PostgreSQLWorkflowPlanRepository._event_byte_artifact_claim_model(request)

    assert artifact_row.canonical_bytes == request.candidate.canonical_bytes
    assert (
        PostgreSQLWorkflowPlanRepository._event_byte_artifact_from_row(artifact_row)
        == request.candidate
    )
    record = PostgreSQLWorkflowPlanRepository._event_byte_artifact_record_from_claim(
        claim_row, artifact_row
    )
    assert record.request_fingerprint == request.request_fingerprint
    assert record.artifact == request.candidate
    assert "canonical_bytes" not in claim_row.payload["result_artifact"]
    assert request.candidate.canonical_bytes.hex() not in str(claim_row.payload)


def test_byte_artifact_repository_locks_all_evidence_and_commits_atomically() -> None:
    source = getsource(PostgreSQLWorkflowPlanRepository.materialize_event_byte_artifact)
    for model_name in (
        "WorkflowRunPlanModel",
        "WorkflowDispatchOutboxEntryModel",
        "WorkflowOrchestrationLeaseModel",
        "WorkflowOutboxPublicationLeaseModel",
        "WorkflowDispatchEventEnvelopeModel",
        "WorkflowEventTransportAdmissionModel",
    ):
        assert model_name in source
    assert source.count(".with_for_update()") == 6
    assert "session.add(self._event_byte_artifact_model(candidate))" in source
    assert "session.add(self._event_byte_artifact_claim_model(request))" in source
    assert "await session.commit()" in source

    evidence_source = getsource(
        PostgreSQLWorkflowPlanRepository._event_byte_artifact_evidence_matches
    )
    for evidence in (
        "_event_transport_admission_evidence_matches",
        "expected_admission_digest",
        "expected_publication_fencing_token",
        "canonical_json_bytes",
        "WorkflowEventByteArtifactState.MATERIALIZED",
    ):
        assert evidence in evidence_source


def test_byte_artifact_adapters_match_repository_protocol_method_signatures() -> None:
    for adapter in (
        InMemoryWorkflowPlanRepository,
        PostgreSQLWorkflowPlanRepository,
        UnavailableWorkflowPlanRepository,
    ):
        for method_name in (
            "get_event_byte_artifact_by_admission_id",
            "get_event_byte_artifact_request",
            "materialize_event_byte_artifact",
        ):
            assert signature(getattr(adapter, method_name)) == signature(
                getattr(WorkflowEventByteArtifactRepository, method_name)
            )


def test_byte_artifact_migration_follows_admission_head_and_uses_bytea() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0117_workflow_event_byte_artifacts.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260814_0117"' in migration
    assert 'down_revision: str | None = "20260814_0116"' in migration
    assert "workflow_event_byte_artifacts" in migration
    assert "workflow_event_byte_artifact_claims" in migration
    assert 'sa.Column("canonical_bytes", sa.LargeBinary(), nullable=False)' in migration
    assert "fk_workflow_event_byte_artifact_admission" in migration
    assert "workflow_orchestration_leases.lease_id" not in migration
    assert "workflow_dispatch_outbox_publication_leases.publication_lease_id" not in migration
    for field in (
        '"provider"',
        '"broker"',
        '"endpoint"',
        '"route"',
        '"queue"',
        '"topic"',
        '"partition"',
        '"routing_key"',
        '"credential"',
        '"provider_message"',
        '"publication_attempt"',
        '"retry_schedule"',
        '"receipt"',
        '"delivery_acknowledgement"',
        '"worker_reservation"',
        '"execution_result"',
    ):
        assert field not in migration
