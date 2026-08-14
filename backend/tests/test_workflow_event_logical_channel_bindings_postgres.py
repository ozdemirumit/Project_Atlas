from __future__ import annotations

from datetime import UTC, datetime
from inspect import getsource, signature
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import Table
from test_workflow_event_byte_artifacts_postgres import _artifact

from atlas.core.persistence.models import (
    WorkflowEventLogicalChannelBindingClaimModel,
    WorkflowEventLogicalChannelBindingModel,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application.byte_artifact_ports import (
    WorkflowEventByteArtifactError,
)
from atlas.modules.workflows.application.logical_channel_binding_ports import (
    WorkflowEventLogicalChannelBindingError,
    WorkflowEventLogicalChannelBindingRepository,
    WorkflowEventLogicalChannelBindingRequest,
)
from atlas.modules.workflows.domain import (
    WorkflowEventLogicalChannelBinding,
    WorkflowEventLogicalChannelBindingAuthority,
    WorkflowEventLogicalChannelBindingState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_logical_channel_policy,
)

NOW = datetime(2026, 8, 14, 23, 0, tzinfo=UTC)


def _binding() -> WorkflowEventLogicalChannelBinding:
    artifact = _artifact()
    policy = code_owned_workflow_event_logical_channel_policy()
    authority = WorkflowEventLogicalChannelBindingAuthority()
    values: dict[str, object] = {
        "binding_id": "workflow-event-channel-binding.postgres-01",
        "artifact_id": artifact.artifact_id,
        "artifact_digest": artifact.canonical_digest,
        "content_sha256": artifact.content_sha256,
        "canonical_byte_count": artifact.canonical_byte_count,
        "admission_id": artifact.admission_id,
        "admission_digest": artifact.admission_digest,
        "event_id": artifact.event_id,
        "event_digest": artifact.event_digest,
        "event_type": artifact.event_type,
        "event_version": artifact.event_version,
        "schema_uri": artifact.schema_uri,
        "outbox_entry_id": artifact.outbox_entry_id,
        "outbox_entry_digest": artifact.outbox_entry_digest,
        "dispatch_intent_id": artifact.dispatch_intent_id,
        "dispatch_intent_digest": artifact.dispatch_intent_digest,
        "plan_id": artifact.plan_id,
        "plan_digest": artifact.plan_digest,
        "run_id": artifact.run_id,
        "run_digest": artifact.run_digest,
        "step_run_id": artifact.step_run_id,
        "step_run_digest": artifact.step_run_digest,
        "step_id": artifact.step_id,
        "attempt_id": artifact.attempt_id,
        "attempt_digest": artifact.attempt_digest,
        "attempt_number": artifact.attempt_number,
        "scope": artifact.scope,
        "target_id": artifact.target_id,
        "target_type": artifact.target_type,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "logical_channel_id": policy.logical_channel_id,
        "logical_channel_version": policy.logical_channel_version,
        "data_classification": artifact.data_classification,
        "representation_name": artifact.representation_name,
        "encoding": artifact.encoding,
        "delivery_semantics": policy.delivery_semantics,
        "durability_required": policy.durability_required,
        "ordering_key_kind": policy.ordering_key_kind,
        "ordering_key_value": artifact.run_id,
        "retention_class": policy.retention_class,
        "maximum_canonical_byte_count": policy.maximum_canonical_byte_count,
        "orchestration_lease_id": artifact.orchestration_lease_id,
        "orchestration_lease_digest": artifact.orchestration_lease_digest,
        "orchestration_fencing_token": artifact.orchestration_fencing_token,
        "publication_lease_id": artifact.publication_lease_id,
        "publication_lease_digest": artifact.publication_lease_digest,
        "publication_fencing_token": artifact.publication_fencing_token,
        "publisher_subject_id": artifact.publisher_subject_id,
        "bound_at": NOW,
        "state": WorkflowEventLogicalChannelBindingState.BOUND,
        "authority": authority,
    }
    digest_payload = {
        key: value.canonical_value()
        if isinstance(value, (WorkflowEventLogicalChannelBindingAuthority, WorkflowScope))
        else value.isoformat()
        if isinstance(value, datetime)
        else value.value
        if isinstance(value, WorkflowEventLogicalChannelBindingState)
        else value
        for key, value in values.items()
    }
    return WorkflowEventLogicalChannelBinding(
        **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
    )


def _request() -> WorkflowEventLogicalChannelBindingRequest:
    binding = _binding()
    return WorkflowEventLogicalChannelBindingRequest(
        expected_plan_digest=binding.plan_digest,
        expected_outbox_entry_digest=binding.outbox_entry_digest,
        expected_event_id=binding.event_id,
        expected_event_digest=binding.event_digest,
        expected_admission_id=binding.admission_id,
        expected_admission_digest=binding.admission_digest,
        expected_artifact_id=binding.artifact_id,
        expected_artifact_digest=binding.artifact_digest,
        expected_content_sha256=binding.content_sha256,
        expected_canonical_byte_count=binding.canonical_byte_count,
        expected_policy_digest=binding.policy_digest,
        expected_orchestration_lease_id=binding.orchestration_lease_id,
        expected_orchestration_lease_digest=binding.orchestration_lease_digest,
        expected_orchestration_fencing_token=binding.orchestration_fencing_token,
        expected_publication_lease_id=binding.publication_lease_id,
        expected_publication_lease_digest=binding.publication_lease_digest,
        expected_publication_fencing_token=binding.publication_fencing_token,
        publisher_subject_id=binding.publisher_subject_id,
        requested_at=NOW,
        candidate=binding,
        idempotency_key="event-logical-channel-binding-postgres-0001",
        request_fingerprint="b" * 64,
    )


def test_models_enforce_one_binding_per_artifact_and_zero_authority() -> None:
    binding_table = cast(Table, WorkflowEventLogicalChannelBindingModel.__table__)
    claim_table = cast(Table, WorkflowEventLogicalChannelBindingClaimModel.__table__)
    binding_constraints = {constraint.name for constraint in binding_table.constraints}
    claim_constraints = {constraint.name for constraint in claim_table.constraints}

    assert {
        "uq_wf_event_channel_binding_artifact",
        "uq_wf_event_channel_binding_digest",
        "ck_wf_event_channel_binding_attempt",
        "ck_wf_event_channel_binding_byte_count",
        "ck_wf_event_channel_binding_orch_fence",
        "ck_wf_event_channel_binding_pub_fence",
        "ck_wf_event_channel_binding_state",
        "ck_wf_event_channel_binding_zero_auth",
    } <= binding_constraints
    assert {
        "uq_wf_event_channel_claim_scope_idem",
        "uq_wf_event_channel_claim_binding",
        "uq_wf_event_channel_claim_artifact",
        "uq_wf_event_channel_claim_digest",
    } <= claim_constraints
    assert {
        "publication_authority_granted",
        "delivery_authority_granted",
        "dispatch_authority_granted",
        "execution_authority_granted",
    } <= set(binding_table.columns.keys())

    binding = _binding()
    row = PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_model(binding)
    assert row.publication_authority_granted is False
    assert row.delivery_authority_granted is False
    assert row.dispatch_authority_granted is False
    assert row.execution_authority_granted is False
    assert not any(binding.authority.canonical_value().values())


def test_binding_and_claim_round_trip_with_exact_column_payload_integrity() -> None:
    request = _request()
    binding_row = PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_model(
        request.candidate
    )
    claim_row = PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_claim_model(request)

    assert (
        PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_from_row(binding_row)
        == request.candidate
    )
    record = PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_record_from_claim(
        claim_row, binding_row
    )
    assert record.request_fingerprint == request.request_fingerprint
    assert record.binding == request.candidate
    assert claim_row.result_digest == request.candidate.canonical_digest
    assert claim_row.artifact_id == request.candidate.artifact_id
    assert "canonical_bytes" not in binding_row.payload
    assert "canonical_bytes" not in claim_row.payload["result_binding"]
    assert _artifact().canonical_bytes.hex() not in str(binding_row.payload)
    assert _artifact().canonical_bytes.hex() not in str(claim_row.payload)


def test_corrupted_artifact_binding_and_claim_fail_closed() -> None:
    artifact = _artifact()
    artifact_row = PostgreSQLWorkflowPlanRepository._event_byte_artifact_model(artifact)
    artifact_row.canonical_bytes = b"tampered"
    with pytest.raises(WorkflowEventByteArtifactError):
        PostgreSQLWorkflowPlanRepository._event_byte_artifact_from_row(artifact_row)

    request = _request()
    binding_row = PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_model(
        request.candidate
    )
    binding_row.content_sha256 = "f" * 64
    with pytest.raises(WorkflowEventLogicalChannelBindingError) as binding_error:
        PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_from_row(binding_row)
    assert binding_error.value.code == (
        "workflow_event_logical_channel_binding_repository_contract_violation"
    )

    binding_row = PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_model(
        request.candidate
    )
    claim_row = PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_claim_model(request)
    claim_row.result_digest = "e" * 64
    with pytest.raises(WorkflowEventLogicalChannelBindingError) as claim_error:
        PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_record_from_claim(
            claim_row, binding_row
        )
    assert claim_error.value.code == (
        "workflow_event_logical_channel_binding_repository_contract_violation"
    )


def test_repository_revalidates_locked_evidence_and_commits_atomically() -> None:
    source = getsource(PostgreSQLWorkflowPlanRepository.bind_event_logical_channel)
    locked_models = (
        "WorkflowRunPlanModel",
        "WorkflowDispatchOutboxEntryModel",
        "WorkflowOrchestrationLeaseModel",
        "WorkflowOutboxPublicationLeaseModel",
        "WorkflowDispatchEventEnvelopeModel",
        "WorkflowEventTransportAdmissionModel",
        "WorkflowEventByteArtifactModel",
    )

    assert source.count(".with_for_update()") == len(locked_models)
    positions = [source.index(model_name) for model_name in locked_models]
    assert positions == sorted(positions)
    assert "_event_logical_channel_binding_evidence_matches" in source
    assert "session.add(self._event_logical_channel_binding_model(candidate))" in source
    assert "session.add(self._event_logical_channel_binding_claim_model(request))" in source
    assert "await session.commit()" in source
    assert "except IntegrityError:" in source
    assert source.count("await session.rollback()") >= 3

    evidence_source = getsource(
        PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_evidence_matches
    )
    for evidence in (
        "_event_byte_artifact_evidence_matches",
        "_event_byte_artifact_from_row",
        "expected_artifact_digest",
        "expected_content_sha256",
        "expected_canonical_byte_count",
        "expected_admission_digest",
        "expected_orchestration_fencing_token",
        "expected_publication_fencing_token",
        "WorkflowEventLogicalChannelBindingState.BOUND",
    ):
        assert evidence in evidence_source


def test_integrity_error_race_replays_exact_request_and_conflicts_changed_request() -> None:
    bind_source = getsource(PostgreSQLWorkflowPlanRepository.bind_event_logical_channel)
    replay_source = getsource(
        PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_replay
    )

    integrity_position = bind_source.index("except IntegrityError:")
    post_race_session_position = bind_source.index(
        "async with self._sessions() as session:", integrity_position
    )
    post_race_replay_position = bind_source.index(
        "_event_logical_channel_binding_replay", post_race_session_position
    )
    assert integrity_position < post_race_session_position < post_race_replay_position
    assert "record.request_fingerprint == request.request_fingerprint" in replay_source
    assert "WorkflowEventLogicalChannelBindingStatus.REPLAY" in replay_source
    assert "WorkflowEventLogicalChannelBindingStatus.IDEMPOTENCY_CONFLICT" in replay_source
    assert "WorkflowEventLogicalChannelBindingStatus.EVIDENCE_CONFLICT" in bind_source
    assert "WorkflowEventLogicalChannelBindingStatus.ALREADY_BOUND" in bind_source


def test_adapters_match_logical_channel_repository_protocol() -> None:
    for adapter in (
        InMemoryWorkflowPlanRepository,
        PostgreSQLWorkflowPlanRepository,
        UnavailableWorkflowPlanRepository,
    ):
        for method_name in (
            "get_event_logical_channel_binding_by_artifact_id",
            "get_event_logical_channel_binding_request",
            "bind_event_logical_channel",
        ):
            assert signature(getattr(adapter, method_name)) == signature(
                getattr(WorkflowEventLogicalChannelBindingRepository, method_name)
            )


def test_migration_is_provider_neutral_and_has_no_replaceable_lease_foreign_keys() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0118_workflow_event_logical_channel_bindings.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260814_0118"' in migration
    assert 'down_revision: str | None = "20260814_0117"' in migration
    assert 'binding_table = "workflow_event_channel_bindings"' in migration
    assert 'claim_table = "workflow_event_channel_binding_claims"' in migration
    assert "uq_wf_event_channel_binding_artifact" in migration
    assert "uq_wf_event_channel_claim_scope_idem" in migration
    assert "uq_wf_event_channel_claim_artifact" in migration
    assert "ck_wf_event_channel_binding_zero_auth" in migration
    assert "workflow_orchestration_leases.lease_id" not in migration
    assert "workflow_dispatch_outbox_publication_leases.publication_lease_id" not in migration

    forbidden_columns = (
        "canonical_bytes",
        "raw_bytes",
        "provider",
        "broker",
        "endpoint",
        "topic",
        "queue",
        "route",
        "routing_key",
        "credential",
        "network",
        "publication_attempt",
        "provider_message",
        "receipt",
        "delivery_acknowledgement",
    )
    for field in forbidden_columns:
        assert f'sa.Column("{field}"' not in migration

    binding_table = cast(Table, WorkflowEventLogicalChannelBindingModel.__table__)
    claim_table = cast(Table, WorkflowEventLogicalChannelBindingClaimModel.__table__)
    for table in (binding_table, claim_table):
        foreign_targets = {key.target_fullname for key in table.foreign_keys}
        assert not any("orchestration_leases" in target for target in foreign_targets)
        assert not any("publication_leases" in target for target in foreign_targets)
        assert set(forbidden_columns).isdisjoint(table.columns.keys())
