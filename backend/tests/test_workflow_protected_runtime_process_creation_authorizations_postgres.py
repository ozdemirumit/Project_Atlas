from __future__ import annotations

import ast
import asyncio
import inspect
import os
import subprocess
import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import Table, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from test_workflow_protected_runtime_readiness_authorizations_postgres import (
    _AcceptAllReceiptVerifier,
)
from test_workflow_protected_runtime_readiness_consumptions_postgres import (
    _cleanup as _cleanup_readiness,
)
from test_workflow_protected_runtime_readiness_consumptions_postgres import (
    _consumption_request,
    _receipt,
    _seed_authorization,
)
from test_workflow_protected_runtime_readiness_consumptions_postgres import (
    _service as _readiness_service,
)

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationClaimModel,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application.protected_runtime_process_creation_authorization_ports import (  # noqa: E501
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTATION_SIGNING_KEY_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_VERSION,
    WorkflowProtectedRuntimeProcessCreationAuthorizationError,
    WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeProcessCreationLifecycleAttestation,
    WorkflowProtectedRuntimeProcessCreationLifecycleAttestationRequest,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_authorizations import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationService,
)
from atlas.modules.workflows.application.protected_runtime_readiness_consumption_ports import (
    WorkflowProtectedRuntimeReadinessConsumptionClaimStatus,
    WorkflowProtectedRuntimeReadinessConsumptionResultRequest,
    WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import canonical_digest


def _method_source(name: str) -> str:
    return inspect.getsource(getattr(PostgreSQLWorkflowPlanRepository, name))


def test_repository_exposes_process_creation_authorization_persistence_contract() -> None:
    for name in (
        "preflight_protected_runtime_process_creation_authorization",
        "get_protected_runtime_process_creation_authorization_source",
        "authorize_protected_runtime_process_creation",
        "list_protected_runtime_process_creation_authorization_presentations",
        "_lock_protected_runtime_process_creation_authorization_rows",
        "_protected_runtime_process_creation_authorization_replay",
        "_protected_runtime_process_creation_authorization_source_is_eligible",
        "_protected_runtime_process_creation_authorization_lease_model",
        "_protected_runtime_process_creation_authorization_claim_model",
    ):
        assert callable(getattr(PostgreSQLWorkflowPlanRepository, name))


def test_lock_is_replay_first_and_uses_two_authoritative_database_times() -> None:
    source = _method_source("_lock_protected_runtime_process_creation_authorization_rows")

    assert source.index("existing_claims = tuple(") < source.index("source_statement = (")
    assert "select(func.clock_timestamp())" in source
    assert source.count("func.clock_timestamp()") >= 2
    assert ".with_for_update()" in source
    assert "WorkflowProtectedRuntimeProcessCreationAuthorizationClaimModel" in source
    assert "WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseModel" in source
    assert "WorkflowDispatchOutboxEntryModel" in source
    assert "WorkflowOutboxPublicationLeaseModel" in source
    assert "WorkflowOrchestrationLeaseModel" in source


def test_lock_binds_exact_ready_result_and_all_immediate_source_rows() -> None:
    source = _method_source("_lock_protected_runtime_process_creation_authorization_rows")

    for model in (
        "WorkflowProtectedRuntimeReadinessConsumptionResultModel",
        "WorkflowProtectedRuntimeReadinessConsumptionAttemptModel",
        "WorkflowProtectedRuntimeReadinessConsumptionClaimModel",
        "WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel",
        "WorkflowProtectedRuntimeReadinessAuthorizationClaimModel",
        "WorkflowProtectedRuntimeContextInjectionDestinationHeadModel",
        "WorkflowProtectedRuntimeContextInjectionSlotHeadModel",
        "WorkflowProtectedRuntimeStartCoordinationHeadModel",
    ):
        assert model in source
    assert 'result.state == "runtime_ready_in_protected_boundary"' in source
    assert "result.outcome_known.is_(True)" in source
    assert "result.assessment_performed.is_(True)" in source
    assert "result.runtime_ready.is_(True)" in source
    assert "destination.current.is_(True)" in source
    assert "slot.current.is_(True)" in source
    assert 'head.state == "start_attempt_terminal"' in source
    assert "head.process_created.is_(False)" in source
    assert "head.process_scheduled.is_(False)" in source
    assert 'dispatch_outbox.state == "pending_publication"' in source
    assert 'publication_lease.state == "active"' in source
    assert 'orchestration_lease.state == "active"' in source


def test_authorize_rechecks_final_window_and_fails_closed() -> None:
    source = _method_source("authorize_protected_runtime_process_creation")

    assert source.count("_lock_protected_runtime_process_creation_authorization_rows") == 2
    assert "commit_observed_at > locked.first_observed_at + timedelta(seconds=1)" in source
    assert "statuses.EVIDENCE_CONFLICT" in source
    assert "statuses.ALREADY_AUTHORIZED" in source
    assert "except (IntegrityError, TypeError, ValueError)" in source
    assert "session.add(" in source
    assert "await session.flush()" in source
    assert "await session.commit()" in source


def test_replay_requires_exact_idempotency_and_source_digest() -> None:
    source = _method_source("_protected_runtime_process_creation_authorization_replay")

    assert "claim_row.idempotency_digest != request.idempotency_digest" in source
    assert "claim_row.request_fingerprint != request.request_fingerprint" in source
    assert "claim_row.readiness_result_digest" in source
    assert "_protected_runtime_process_creation_authorization_lease_from_row" in source
    assert "_protected_runtime_process_creation_authorization_claim_from_row" in source
    assert "validate_workflow_protected_runtime_process_creation_authorization_request" in source
    assert "statuses.IDEMPOTENCY_CONFLICT" in source
    assert "statuses.REPLAY" in source


def test_adapter_has_no_memory_or_permissive_process_creation_fallback() -> None:
    tree = ast.parse(inspect.getsource(PostgreSQLWorkflowPlanRepository))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    source = _method_source("authorize_protected_runtime_process_creation")

    assert "InMemory" not in names
    assert "fallback" not in source.lower()
    assert "network" not in source.lower()
    assert "connector" not in source.lower()
    assert "subprocess" not in source.lower()


def test_process_creation_source_revalidates_exact_active_dispatch_fences() -> None:
    source = _method_source("_protected_runtime_process_creation_authorization_source_is_eligible")

    assert 'outbox.state == "pending_publication"' in source
    assert "publication.outbox_entry_digest == outbox.canonical_digest" in source
    assert "publication.orchestration_lease_id == outbox.lease_id" in source
    assert "publication.orchestration_fencing_token == outbox.lease_fencing_token" in source
    assert "publication.acquired_at <= locked.observed_at < publication.expires_at" in source
    assert "orchestration.canonical_digest == outbox.lease_digest" in source
    assert "orchestration.fencing_token == outbox.lease_fencing_token" in source
    assert "orchestration.acquired_at <= locked.observed_at < orchestration.expires_at" in source


class _AuditSink:
    async def record(self, record: object) -> None:
        del record


class _CaptureAuthorizationRepository:
    durable = True

    def __init__(self, repository: PostgreSQLWorkflowPlanRepository) -> None:
        self._repository = repository
        self.request: Any | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._repository, name)

    async def authorize_protected_runtime_process_creation(self, request: Any) -> Any:
        self.request = request
        raise RuntimeError("captured before persistence")


class _ReadinessReceiptVerifier:
    available = True

    def verify_receipt(self, receipt: object) -> bool:
        del receipt
        return True


class _ProcessLifecycleAttestor:
    available = True

    def __init__(self, *, before_return: Any | None = None) -> None:
        self._before_return = before_return

    async def attest_runtime_process_creation_lifecycle(
        self, request: WorkflowProtectedRuntimeProcessCreationLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeProcessCreationLifecycleAttestation:
        if self._before_return is not None:
            await self._before_return(request.readiness_result_id)
        request_values = {
            name: getattr(request, name) for name in request.__slots__ if name != "requested_at"
        }
        valid_until = request.requested_at + timedelta(seconds=1)
        values: dict[str, object] = {
            **request_values,
            "attestation_id": f"process-creation-attestation.{uuid4().hex}",
            "attestor_id": WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_ID,
            "attestor_version": WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTOR_VERSION,
            "signing_key_id": (
                WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_ATTESTATION_SIGNING_KEY_ID
            ),
            "signature_algorithm": "test-signature-v1",
            "observed_at": request.requested_at,
            "valid_until": valid_until,
            "runtime_envelope_eligible_until": valid_until,
            "exact_readiness_result_confirmed": True,
            "runtime_started_confirmed": True,
            "runtime_ready_confirmed": True,
            "readiness_assessment_confirmed": True,
            "metadata_only_confirmed": True,
            "runtime_envelope_current": True,
            "runtime_envelope_started": True,
            "destination_generation_current": True,
            "destination_fence_current": True,
            "protected_slot_generation_current": True,
            "readiness_profile_eligible": True,
            "prior_process_creation_claim_absent": True,
            "prior_process_creation_lease_absent": True,
            "runtime_resumed": False,
            "runtime_stopped": False,
            "runtime_restarted": False,
            "generic_process_created": False,
            "scheduling_performed": False,
            "readiness_probe_performed": False,
            "network_activity_performed": False,
            "connector_activity_performed": False,
            "publication_performed": False,
            "delivery_performed": False,
            "dispatch_performed": False,
            "execution_performed": False,
            "infrastructure_mutation_performed": False,
            "runtime_locator_included": False,
            "process_identifier_included": False,
            "context_included": False,
            "endpoint_included": False,
            "credential_included": False,
            "secret_included": False,
            "command_included": False,
            "integrity_signature": "f" * 64,
        }
        attestation = WorkflowProtectedRuntimeProcessCreationLifecycleAttestation(
            **cast(Any, values), canonical_digest="0" * 64
        )
        return replace(
            attestation,
            canonical_digest=canonical_digest(attestation.digest_payload()),
        )

    def verify_runtime_process_creation_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeProcessCreationLifecycleAttestation
    ) -> bool:
        del attestation
        return True


async def _seed_ready_result(
    engine: AsyncEngine,
    repository: PostgreSQLWorkflowPlanRepository,
    *,
    suffix: str,
) -> tuple[Any, Any]:
    start_request, authorization_source = await _seed_authorization(
        engine, repository, suffix=suffix
    )
    request = await _consumption_request(
        repository,
        authorization_lease_id=(authorization_source.authorization_lease.authorization_lease_id),
        idempotency_key=f"imp-227-readiness-{uuid4().hex}",
        source=authorization_source,
    )
    claimed = await repository.claim_protected_runtime_readiness_consumption(request)
    assert claimed.status is WorkflowProtectedRuntimeReadinessConsumptionClaimStatus.CLAIMED
    service = _readiness_service(repository)
    receipt = _receipt(request)
    result = service._build_receipted_result(
        claim=request.candidate_claim,
        attempt=request.candidate_attempt,
        receipt=receipt,
        recorded_at=await repository.get_authoritative_time(),
    )
    recorded = await repository.record_protected_runtime_readiness_consumption_result(
        WorkflowProtectedRuntimeReadinessConsumptionResultRequest(
            result=result,
            receipt=receipt,
            expected_claim_digest=request.candidate_claim.canonical_digest,
            expected_attempt_digest=request.candidate_attempt.canonical_digest,
        )
    )
    assert recorded.status is WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus.RECORDED
    return start_request, result


def _process_service(
    repository: PostgreSQLWorkflowPlanRepository,
    *,
    attestor: _ProcessLifecycleAttestor | None = None,
) -> WorkflowProtectedRuntimeProcessCreationAuthorizationService:
    attestor = attestor or _ProcessLifecycleAttestor()
    return WorkflowProtectedRuntimeProcessCreationAuthorizationService(
        authorization_repository=cast(Any, repository),
        lifecycle_attestor=attestor,
        lifecycle_signature_verifier=attestor,
        readiness_receipt_signature_verifier=_ReadinessReceiptVerifier(),
        audit_sink=cast(Any, _AuditSink()),
    )


async def _authorize_process_creation(
    service: WorkflowProtectedRuntimeProcessCreationAuthorizationService,
    result: Any,
    *,
    idempotency_key: str,
) -> Any:
    policy = service.policy
    return await service.authorize(
        readiness_result_id=result.result_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        single_use_nonrenewable_nontransferable_future_request_acknowledged=True,
        no_process_creation_or_scheduling_authority_acknowledged=True,
        idempotency_key=idempotency_key,
        context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
            subject_id=policy.consumer_subject_id,
            actor_type="service",
            authentication_method="workload_token",
            credential_audience=policy.consumer_audience,
            scope=result.scope,
            correlation_id=f"correlation.{uuid4().hex}",
            decision_id=f"decision.{uuid4().hex}",
            requested_at=await service.repository.get_authoritative_time(),
        ),
    )


async def _capture_process_creation_request(
    repository: PostgreSQLWorkflowPlanRepository,
    result: Any,
) -> Any:
    capturing = _CaptureAuthorizationRepository(repository)
    service = _process_service(cast(Any, capturing))
    with pytest.raises(WorkflowProtectedRuntimeProcessCreationAuthorizationError) as exc_info:
        await _authorize_process_creation(
            service,
            result,
            idempotency_key=f"imp-227-orphan-{uuid4().hex}",
        )
    assert exc_info.value.code.endswith("repository_unavailable")
    assert capturing.request is not None
    return capturing.request


async def _assert_circular_orphan_commit_rejected(
    repository: PostgreSQLWorkflowPlanRepository,
    request: Any,
    *,
    side: str,
) -> None:
    async with repository._sessions() as session:
        locked = await repository._lock_protected_runtime_process_creation_authorization_rows(
            session,
            readiness_result_id=request.source.result.result_id,
            scope=request.scope,
            consumer_subject_id=request.consumer_subject_id,
            consumer_audience=request.consumer_audience,
            idempotency_key=request.idempotency_key,
        )
        working = repository._protected_runtime_process_creation_authorization_retimed_request(
            request,
            claimed_at=locked.first_observed_at,
            issued_at=locked.first_observed_at,
        )
        audit_payload: dict[str, object] = {
            "readiness_result_id": working.candidate.readiness_result_id,
            "policy_digest": working.candidate.policy_digest,
            "request_fingerprint": working.request_fingerprint,
            "scope": working.scope.canonical_value(),
        }
        if side == "lease":
            session.add(
                repository._protected_runtime_process_creation_authorization_lease_model(
                    working.candidate,
                    working.lifecycle_attestation,
                    locked=locked,
                    source_observed_at=locked.first_observed_at,
                    authorized_at=locked.first_observed_at,
                )
            )
            constraint = "fk_wf_rtproc_auth_lease_claim"
        else:
            session.add(
                repository._protected_runtime_process_creation_authorization_claim_model(
                    working.candidate_claim,
                    authorization_lease_id=working.candidate.authorization_lease_id,
                    idempotency_key=working.idempotency_key,
                    audit_payload=audit_payload,
                    locked=locked,
                    source_observed_at=locked.first_observed_at,
                )
            )
            constraint = "fk_wf_rtproc_auth_claim_lease"
        await session.flush()
        with pytest.raises(DBAPIError, match=constraint):
            await session.commit()
        await session.rollback()


async def _cleanup_process_creation(engine: AsyncEngine, *, readiness_result_id: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        await connection.execute(
            text(
                "DELETE FROM workflow_event_runtime_process_creation_auth_claims "
                "WHERE readiness_result_id = :readiness_result_id"
            ),
            {"readiness_result_id": readiness_result_id},
        )
        await connection.execute(
            text(
                "DELETE FROM workflow_event_runtime_process_creation_auth_leases "
                "WHERE readiness_result_id = :readiness_result_id"
            ),
            {"readiness_result_id": readiness_result_id},
        )
        await connection.execute(text("SET LOCAL session_replication_role = origin"))


@pytest.mark.asyncio
async def test_live_postgres_exact_race_circular_fk_append_only_and_guarded_downgrade() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    repository = PostgreSQLWorkflowPlanRepository(engine=engine)
    repository.bind_protected_runtime_start_receipt_signature_verifier(
        cast(Any, _AcceptAllReceiptVerifier())
    )
    seeded: list[Any] = []
    readiness_results: list[Any] = []
    try:
        start_request, readiness_result = await _seed_ready_result(
            engine,
            repository,
            suffix=f"imp227-race-{uuid4().hex[:12]}",
        )
        seeded.append(start_request)
        readiness_results.append(readiness_result)
        idempotency_key = f"imp-227-process-{uuid4().hex}"
        first, second = await asyncio.wait_for(
            asyncio.gather(
                _authorize_process_creation(
                    _process_service(repository),
                    readiness_result,
                    idempotency_key=idempotency_key,
                ),
                _authorize_process_creation(
                    _process_service(repository),
                    readiness_result,
                    idempotency_key=idempotency_key,
                ),
            ),
            timeout=20,
        )
        assert first == second

        lease_table = cast(
            Table, WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseModel.__table__
        )
        claim_table = cast(
            Table, WorkflowProtectedRuntimeProcessCreationAuthorizationClaimModel.__table__
        )
        async with engine.connect() as connection:
            lease_row = (
                (
                    await connection.execute(
                        select(lease_table).where(
                            lease_table.c.authorization_lease_id == first.authorization_lease_id
                        )
                    )
                )
                .mappings()
                .one()
            )
            claim_row = (
                (
                    await connection.execute(
                        select(claim_table).where(claim_table.c.claim_id == first.claim_id)
                    )
                )
                .mappings()
                .one()
            )
            assert lease_row["claim_id"] == claim_row["claim_id"]
            assert lease_row["claim_digest"] == claim_row["canonical_digest"]
            assert claim_row["authorization_lease_id"] == lease_row["authorization_lease_id"]
            foreign_keys = {
                row["conname"]: row
                for row in (
                    (
                        await connection.execute(
                            text(
                                "SELECT conname, condeferrable, condeferred, "
                                "pg_get_constraintdef(oid) AS definition "
                                "FROM pg_constraint WHERE conname IN "
                                "('fk_wf_rtproc_auth_lease_claim', "
                                "'fk_wf_rtproc_auth_claim_lease')"
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
            }
            assert set(foreign_keys) == {
                "fk_wf_rtproc_auth_lease_claim",
                "fk_wf_rtproc_auth_claim_lease",
            }
            for foreign_key in foreign_keys.values():
                assert foreign_key["condeferrable"] is True
                assert foreign_key["condeferred"] is True
                assert "FOREIGN KEY" in foreign_key["definition"]

        policy = _process_service(repository).policy
        changed_replay = (
            await repository.preflight_protected_runtime_process_creation_authorization(
                WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightRequest(
                    readiness_result_id=readiness_result.result_id,
                    scope=readiness_result.scope,
                    consumer_subject_id=policy.consumer_subject_id,
                    consumer_audience=policy.consumer_audience,
                    policy_id=policy.policy_id,
                    policy_version=policy.policy_version,
                    policy_digest=policy.canonical_digest,
                    idempotency_key=idempotency_key,
                    idempotency_digest=cast(str, claim_row["idempotency_digest"]),
                    request_fingerprint="a" * 64,
                    offline_signature_verifier=_ProcessLifecycleAttestor(),
                    offline_readiness_receipt_signature_verifier=(_ReadinessReceiptVerifier()),
                )
            )
        )
        assert (
            changed_replay.status
            is (
                WorkflowProtectedRuntimeProcessCreationAuthorizationPreflightStatus
            ).IDEMPOTENCY_CONFLICT
        )
        assert changed_replay.lease is None

        orphan_start, orphan_result = await _seed_ready_result(
            engine,
            repository,
            suffix=f"imp227-orphan-{uuid4().hex[:12]}",
        )
        seeded.append(orphan_start)
        readiness_results.append(orphan_result)
        orphan_request = await _capture_process_creation_request(repository, orphan_result)
        await _assert_circular_orphan_commit_rejected(repository, orphan_request, side="lease")
        await _assert_circular_orphan_commit_rejected(repository, orphan_request, side="claim")

        competing_start, competing_result = await _seed_ready_result(
            engine,
            repository,
            suffix=f"imp227-competing-{uuid4().hex[:12]}",
        )
        seeded.append(competing_start)
        readiness_results.append(competing_result)
        competing = await asyncio.wait_for(
            asyncio.gather(
                _authorize_process_creation(
                    _process_service(repository),
                    competing_result,
                    idempotency_key=f"imp-227-competing-a-{uuid4().hex}",
                ),
                _authorize_process_creation(
                    _process_service(repository),
                    competing_result,
                    idempotency_key=f"imp-227-competing-b-{uuid4().hex}",
                ),
                return_exceptions=True,
            ),
            timeout=20,
        )
        competing_leases = [item for item in competing if not isinstance(item, Exception)]
        competing_errors = [item for item in competing if isinstance(item, Exception)]
        assert len(competing_leases) == 1
        assert len(competing_errors) == 1
        assert isinstance(
            competing_errors[0], WorkflowProtectedRuntimeProcessCreationAuthorizationError
        )
        assert competing_errors[0].code.endswith("already_authorized")

        for table, key, value in (
            (lease_table, "authorization_lease_id", first.authorization_lease_id),
            (claim_table, "claim_id", first.claim_id),
        ):
            async with engine.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError, match="append-only"):
                    await connection.execute(
                        table.update()
                        .where(table.c[key] == value)
                        .values(canonical_digest="a" * 64)
                    )
                await transaction.rollback()
            async with engine.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError, match="append-only"):
                    await connection.execute(table.delete().where(table.c[key] == value))
                await transaction.rollback()

        downgrade_environment = os.environ.copy()
        downgrade_environment["ATLAS_DATABASE_URL"] = database_url
        downgrade = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", "downgrade", "20260817_0149"],
            cwd=Path(__file__).parents[1],
            env=downgrade_environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert downgrade.returncode != 0
        assert "refusing guarded downgrade" in (downgrade.stdout + downgrade.stderr).lower()
    finally:
        for result in readiness_results:
            await _cleanup_process_creation(engine, readiness_result_id=result.result_id)
        if seeded:
            await _cleanup_readiness(engine, tuple(seeded))
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_publication_fence_change_fails_closed() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    repository = PostgreSQLWorkflowPlanRepository(engine=engine)
    repository.bind_protected_runtime_start_receipt_signature_verifier(
        cast(Any, _AcceptAllReceiptVerifier())
    )
    seeded: list[Any] = []
    publication_lease_id: str | None = None

    async def release_exact_publication_fence(readiness_result_id: str) -> None:
        nonlocal publication_lease_id
        async with engine.begin() as connection:
            publication_lease_id = cast(
                str,
                await connection.scalar(
                    text(
                        "SELECT publication.publication_lease_id "
                        "FROM workflow_event_runtime_readiness_consumption_results result "
                        "JOIN workflow_protected_runtime_context_use_results use_result "
                        "ON use_result.result_id = result.use_result_id "
                        "AND use_result.canonical_digest = result.use_result_digest "
                        "JOIN workflow_event_runtime_context_use_auth_consumption_results "
                        "consumption "
                        "ON consumption.result_id = use_result.authorization_consumption_result_id "
                        "AND consumption.canonical_digest = "
                        "use_result.authorization_consumption_result_digest "
                        "JOIN workflow_event_runtime_context_use_auth_leases use_lease "
                        "ON use_lease.authorization_lease_id = consumption.authorization_lease_id "
                        "AND use_lease.canonical_digest = consumption.authorization_lease_digest "
                        "JOIN workflow_event_runtime_context_injection_results injection_result "
                        "ON injection_result.result_id = use_lease.injection_result_id "
                        "AND injection_result.canonical_digest = use_lease.injection_result_digest "
                        "JOIN workflow_event_runtime_context_injection_auth_leases injection_lease "
                        "ON injection_lease.authorization_lease_id = "
                        "injection_result.authorization_lease_id "
                        "AND injection_lease.canonical_digest = "
                        "injection_result.authorization_lease_digest "
                        "JOIN workflow_event_resident_context_access_results access_result "
                        "ON access_result.access_id = injection_lease.access_result_id "
                        "AND access_result.canonical_digest = injection_lease.access_result_digest "
                        "JOIN workflow_event_resident_context_access_auth_leases access_lease "
                        "ON access_lease.access_authorization_lease_id = "
                        "access_result.authorization_lease_id "
                        "AND access_lease.canonical_digest = "
                        "access_result.authorization_lease_digest "
                        "JOIN workflow_event_tctx_capsule_opening_results opening_result "
                        "ON opening_result.opening_id = access_lease.opening_id "
                        "AND opening_result.canonical_digest = access_lease.opening_result_digest "
                        "JOIN workflow_event_tctx_capsule_consumer_bindings binding "
                        "ON binding.binding_id = opening_result.consumer_binding_id "
                        "AND binding.canonical_digest = opening_result.consumer_binding_digest "
                        "JOIN workflow_dispatch_outbox_publication_leases publication "
                        "ON publication.outbox_entry_id = binding.outbox_entry_id "
                        "AND publication.outbox_entry_digest = binding.outbox_entry_digest "
                        "WHERE result.result_id = :readiness_result_id"
                    ),
                    {"readiness_result_id": readiness_result_id},
                ),
            )
            assert publication_lease_id
            await connection.execute(
                text(
                    "UPDATE workflow_dispatch_outbox_publication_leases "
                    "SET state = 'released' WHERE publication_lease_id = :lease_id"
                ),
                {"lease_id": publication_lease_id},
            )

    try:
        start_request, readiness_result = await _seed_ready_result(
            engine,
            repository,
            suffix=f"imp227-fence-{uuid4().hex[:12]}",
        )
        seeded.append(start_request)
        service = _process_service(
            repository,
            attestor=_ProcessLifecycleAttestor(before_return=release_exact_publication_fence),
        )
        with pytest.raises(WorkflowProtectedRuntimeProcessCreationAuthorizationError) as exc_info:
            await _authorize_process_creation(
                service,
                readiness_result,
                idempotency_key=f"imp-227-fence-{uuid4().hex}",
            )
        assert (
            exc_info.value.code == "workflow_protected_runtime_process_creation_evidence_conflict"
        )
    finally:
        if publication_lease_id is not None:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE workflow_dispatch_outbox_publication_leases "
                        "SET state = 'active' WHERE publication_lease_id = :lease_id"
                    ),
                    {"lease_id": publication_lease_id},
                )
        if seeded:
            await _cleanup_readiness(engine, tuple(seeded))
        await engine.dispose()
