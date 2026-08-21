from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import Table, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from test_workflow_protected_runtime_process_creation_authorizations_postgres import (
    _cleanup_fixture_fences,
    _cleanup_process_creation,
    _FixtureProcessCreationRepository,
)
from test_workflow_protected_runtime_process_creation_consumptions_postgres import (
    _cleanup_consumption,
)
from test_workflow_protected_runtime_process_scheduling_authorizations_postgres import (
    _authorization_request as _scheduling_authorization_request,
)
from test_workflow_protected_runtime_process_scheduling_authorizations_postgres import (
    _cleanup_scheduling,
    _SchedulingStateAttestor,
    _seed_created_process,
)
from test_workflow_protected_runtime_readiness_authorizations_postgres import (
    _AcceptAllReceiptVerifier,
)
from test_workflow_protected_runtime_readiness_consumptions_postgres import (
    _cleanup as _cleanup_readiness,
)

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeProcessCreationResultModel,
    WorkflowProtectedRuntimeProcessResumeAuthorizationClaimModel,
    WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.protected_runtime_process_creators import (
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
)
from atlas.modules.workflows.adapters.protected_runtime_process_schedulers import (
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessScheduler,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier,
)
from atlas.modules.workflows.adapters.protected_runtime_process_schedulers import (
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier as _SchedulingInstructionSignatureVerifier,  # noqa: E501
)
from atlas.modules.workflows.application.protected_runtime_process_resume_authorization_ports import (  # noqa: E501
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTATION_SIGNING_KEY_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_ID,
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_VERSION,
    WorkflowProtectedRuntimeProcessResumeAuthorizationError,
    WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus,
    WorkflowProtectedRuntimeProcessResumeStateAttestation,
    WorkflowProtectedRuntimeProcessResumeStateAttestationRequest,
)
from atlas.modules.workflows.application.protected_runtime_process_resume_authorizations import (
    WorkflowProtectedRuntimeProcessResumeAuthorizationService,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumptions import (
    WorkflowProtectedRuntimeProcessSchedulingConsumptionService,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_resume_authorization_domain import (
    WorkflowProtectedRuntimeProcessResumeAuthorizationLease,
    code_owned_workflow_protected_runtime_process_resume_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_consumption_domain import (
    code_owned_workflow_protected_runtime_process_scheduling_consumption_policy,
)


class _AuditSink:
    async def record(self, record: object) -> None:
        del record


class _ResumeStateAttestor:
    available = True

    def __init__(
        self,
        *,
        after_attestation: (
            Callable[
                [WorkflowProtectedRuntimeProcessResumeStateAttestationRequest], Awaitable[None]
            ]
            | None
        ) = None,
    ) -> None:
        self.calls = 0
        self._after_attestation = after_attestation

    async def attest_runtime_process_resume_state(
        self, request: WorkflowProtectedRuntimeProcessResumeStateAttestationRequest
    ) -> WorkflowProtectedRuntimeProcessResumeStateAttestation:
        self.calls += 1
        values: dict[str, object] = {
            **{
                name: getattr(request, name) for name in request.__slots__ if name != "requested_at"
            },
            "attestation_id": f"process-resume-state-attestation.{uuid4().hex}",
            "attestor_id": WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_ID,
            "attestor_version": WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTOR_VERSION,
            "signing_key_id": WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_ATTESTATION_SIGNING_KEY_ID,
            "signature_algorithm": "test-signature-v1",
            "observed_at": request.requested_at,
            "valid_until": request.requested_at + timedelta(seconds=1),
            "process_state_eligible_until": request.requested_at + timedelta(seconds=1),
            "exact_process_scheduling_result_confirmed": True,
            "terminal_success_confirmed": True,
            "metadata_only_confirmed": True,
            "process_created_confirmed": True,
            "process_sealed_confirmed": True,
            "process_suspended_confirmed": True,
            "process_scheduled_confirmed": True,
            "process_not_runnable_confirmed": True,
            "process_not_resumed_confirmed": True,
            "process_not_dispatched_confirmed": True,
            "process_not_executed_confirmed": True,
            "runtime_envelope_current": True,
            "destination_generation_current": True,
            "destination_fence_current": True,
            "protected_slot_generation_current": True,
            "prior_process_resume_claim_absent": True,
            "prior_process_resume_lease_absent": True,
            "pending_or_conflicting_resume_absent": True,
            "pending_or_conflicting_dispatch_absent": True,
            "pending_or_conflicting_execution_absent": True,
            "pending_or_conflicting_supervision_absent": True,
            "pending_or_conflicting_stop_absent": True,
            "pending_or_conflicting_cleanup_absent": True,
            "pending_or_conflicting_replacement_absent": True,
            "pending_or_conflicting_rescheduling_absent": True,
            "scheduling_performed": False,
            "resume_performed": False,
            "dispatch_performed": False,
            "execution_performed": False,
            "network_activity_performed": False,
            "connector_activity_performed": False,
            "mcp_activity_performed": False,
            "provider_activity_performed": False,
            "infrastructure_mutation_performed": False,
            "process_locator_included": False,
            "process_identifier_included": False,
            "process_material_included": False,
            "runtime_material_included": False,
            "command_material_included": False,
            "argument_material_included": False,
            "environment_material_included": False,
            "prompt_material_included": False,
            "model_material_included": False,
            "endpoint_material_included": False,
            "credential_material_included": False,
            "secret_material_included": False,
            "integrity_signature": "a" * 64,
        }
        attestation = WorkflowProtectedRuntimeProcessResumeStateAttestation(
            **cast(Any, values), canonical_digest="0" * 64
        )
        attestation = replace(
            attestation,
            canonical_digest=canonical_digest(attestation.digest_payload()),
        )
        if self._after_attestation is not None:
            await self._after_attestation(request)
        return attestation

    def verify_runtime_process_resume_state_attestation(
        self,
        attestation: WorkflowProtectedRuntimeProcessResumeStateAttestation,
    ) -> bool:
        del attestation
        return True


def _resume_service(
    repository: _FixtureProcessCreationRepository,
    *,
    attestor: _ResumeStateAttestor,
    receipt_verifier: (
        DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier
    ),
) -> WorkflowProtectedRuntimeProcessResumeAuthorizationService:
    return WorkflowProtectedRuntimeProcessResumeAuthorizationService(
        authorization_repository=cast(Any, repository),
        process_state_attestor=attestor,
        process_state_signature_verifier=attestor,
        process_scheduling_receipt_signature_verifier=receipt_verifier,
        audit_sink=_AuditSink(),
    )


async def _authorize_resume(
    service: WorkflowProtectedRuntimeProcessResumeAuthorizationService,
    *,
    process_scheduling_result_id: str,
    scope: WorkflowScope,
    idempotency_key: str,
) -> WorkflowProtectedRuntimeProcessResumeAuthorizationLease:
    policy = service.policy
    return await service.authorize(
        process_scheduling_result_id=process_scheduling_result_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        single_use_nonrenewable_nontransferable_future_request_acknowledged=True,
        single_use_future_request_only_acknowledged=True,
        idempotency_key=idempotency_key,
        context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
            subject_id=policy.consumer_subject_id,
            actor_type="service",
            authentication_method="workload_token",
            credential_audience=policy.consumer_audience,
            scope=scope,
            correlation_id=f"correlation.{uuid4().hex}",
            decision_id=f"decision.{uuid4().hex}",
            requested_at=await service.repository.get_authoritative_time(),
        ),
    )


async def _seed_scheduled_process(
    engine: AsyncEngine,
    repository: _FixtureProcessCreationRepository,
    *,
    creation_receipt_verifier: (
        DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier
    ),
    scheduling_receipt_verifier: (
        DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier
    ),
) -> tuple[Any, Any, str, str, str]:
    start_request, readiness_result, creation_lease_id = await _seed_created_process(
        engine,
        repository,
        receipt_verifier=creation_receipt_verifier,
        suffix=f"imp231-resume-{uuid4().hex[:12]}",
    )
    async with repository._sessions() as session:
        process_creation_result_id = cast(
            str,
            await session.scalar(
                select(WorkflowProtectedRuntimeProcessCreationResultModel.result_id).where(
                    WorkflowProtectedRuntimeProcessCreationResultModel.authorization_lease_id
                    == creation_lease_id
                )
            ),
        )
    scheduling_request = await _scheduling_authorization_request(
        repository,
        process_creation_result_id=process_creation_result_id,
        scope=readiness_result.scope,
        idempotency_key=f"imp-231-scheduling-auth-{uuid4().hex}",
        attestor=_SchedulingStateAttestor(),
        receipt_verifier=creation_receipt_verifier,
    )
    scheduling_authorization = await repository.authorize_protected_runtime_process_scheduling(
        scheduling_request
    )
    assert scheduling_authorization.lease is not None
    scheduling_lease_id = scheduling_authorization.lease.authorization_lease_id
    signer = DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSigner(
        development_enabled=True
    )
    signature_verifier = _SchedulingInstructionSignatureVerifier(development_enabled=True)
    scheduling_service = WorkflowProtectedRuntimeProcessSchedulingConsumptionService(
        repository=cast(Any, repository),
        instruction_signer=signer,
        instruction_signature_verifier=signature_verifier,
        receipt_signature_verifier=scheduling_receipt_verifier,
        scheduler=DeterministicDevelopmentWorkflowProtectedRuntimeProcessScheduler(
            development_enabled=True,
            instruction_signature_verifier=signature_verifier,
        ),
    )
    scheduling_policy = (
        code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
    )
    scheduling = await scheduling_service.consume(
        authorization_lease_id=scheduling_lease_id,
        policy_id=scheduling_policy.policy_id,
        policy_version=scheduling_policy.policy_version,
        irreversible_consumption_acknowledged=True,
        uncertainty_no_retry_acknowledged=True,
        idempotency_key=f"imp-231-scheduling-{uuid4().hex}",
    )
    assert scheduling.result is not None
    return (
        start_request,
        readiness_result,
        creation_lease_id,
        process_creation_result_id,
        scheduling.result.result_id,
    )


async def _cleanup_resume_authorization(
    engine: AsyncEngine, *, process_scheduling_result_id: str
) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        for table in (
            "workflow_event_runtime_process_resume_auth_claims",
            "workflow_event_runtime_process_resume_auth_leases",
        ):
            await connection.execute(
                text(f"DELETE FROM {table} WHERE process_scheduling_result_id = :result_id"),
                {"result_id": process_scheduling_result_id},
            )
        await connection.execute(text("SET LOCAL session_replication_role = origin"))


async def _cleanup_scheduling_consumption(
    engine: AsyncEngine, *, process_creation_result_id: str
) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        for table in (
            "workflow_event_runtime_process_scheduling_results",
            "workflow_event_runtime_process_scheduling_attempts",
            "workflow_event_runtime_process_scheduling_consumption_claims",
        ):
            await connection.execute(
                text(f"DELETE FROM {table} WHERE process_creation_result_id = :result_id"),
                {"result_id": process_creation_result_id},
            )
        await connection.execute(text("SET LOCAL session_replication_role = origin"))


@pytest.mark.asyncio
async def test_live_postgres_resume_authorization_repository_contract() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url)
    repository = _FixtureProcessCreationRepository(engine=engine)
    repository.bind_protected_runtime_start_receipt_signature_verifier(
        cast(Any, _AcceptAllReceiptVerifier())
    )
    creation_receipt_verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier(
            development_enabled=True
        )
    )
    scheduling_receipt_verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier(
            development_enabled=True
        )
    )
    repository.bind_protected_runtime_process_creation_receipt_signature_verifier(
        creation_receipt_verifier
    )
    repository.bind_protected_runtime_process_scheduling_receipt_signature_verifier(
        scheduling_receipt_verifier
    )
    seeded: list[Any] = []
    readiness_result: Any | None = None
    creation_lease_id: str | None = None
    process_creation_result_id: str | None = None
    process_scheduling_result_id: str | None = None
    try:
        (
            start_request,
            readiness_result,
            creation_lease_id,
            process_creation_result_id,
            process_scheduling_result_id,
        ) = await _seed_scheduled_process(
            engine,
            repository,
            creation_receipt_verifier=creation_receipt_verifier,
            scheduling_receipt_verifier=scheduling_receipt_verifier,
        )
        seeded.append(start_request)
        scope = cast(WorkflowScope, readiness_result.scope)

        async with engine.connect() as connection:
            original_result_digest = cast(
                str,
                await connection.scalar(
                    text(
                        "SELECT canonical_digest "
                        "FROM workflow_event_runtime_process_scheduling_results "
                        "WHERE result_id = :result_id"
                    ),
                    {"result_id": process_scheduling_result_id},
                ),
            )

        async def drift_source(
            request: WorkflowProtectedRuntimeProcessResumeStateAttestationRequest,
        ) -> None:
            async with engine.begin() as connection:
                await connection.execute(text("SET LOCAL session_replication_role = replica"))
                await connection.execute(
                    text(
                        "UPDATE workflow_event_runtime_process_scheduling_results "
                        "SET canonical_digest = :digest WHERE result_id = :result_id"
                    ),
                    {"digest": "b" * 64, "result_id": request.process_scheduling_result_id},
                )
                await connection.execute(text("SET LOCAL session_replication_role = origin"))

        drift_attestor = _ResumeStateAttestor(after_attestation=drift_source)
        with pytest.raises(WorkflowProtectedRuntimeProcessResumeAuthorizationError):
            await _authorize_resume(
                _resume_service(
                    repository,
                    attestor=drift_attestor,
                    receipt_verifier=scheduling_receipt_verifier,
                ),
                process_scheduling_result_id=process_scheduling_result_id,
                scope=scope,
                idempotency_key=f"imp-231-stale-source-{uuid4().hex}",
            )
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role = replica"))
            await connection.execute(
                text(
                    "UPDATE workflow_event_runtime_process_scheduling_results "
                    "SET canonical_digest = :digest WHERE result_id = :result_id"
                ),
                {"digest": original_result_digest, "result_id": process_scheduling_result_id},
            )
            await connection.execute(text("SET LOCAL session_replication_role = origin"))

        attestor = _ResumeStateAttestor()
        service = _resume_service(
            repository,
            attestor=attestor,
            receipt_verifier=scheduling_receipt_verifier,
        )
        idempotency_key = f"imp-231-resume-auth-{uuid4().hex}"
        concurrent = await asyncio.wait_for(
            asyncio.gather(
                _authorize_resume(
                    service,
                    process_scheduling_result_id=process_scheduling_result_id,
                    scope=scope,
                    idempotency_key=idempotency_key,
                ),
                _authorize_resume(
                    service,
                    process_scheduling_result_id=process_scheduling_result_id,
                    scope=scope,
                    idempotency_key=idempotency_key,
                ),
                return_exceptions=True,
            ),
            timeout=20,
        )
        leases = tuple(
            result
            for result in concurrent
            if isinstance(result, WorkflowProtectedRuntimeProcessResumeAuthorizationLease)
        )
        rejections = tuple(
            result
            for result in concurrent
            if isinstance(result, WorkflowProtectedRuntimeProcessResumeAuthorizationError)
        )
        assert len(leases) == 1
        assert len(rejections) == 1
        assert rejections[0].code.endswith("already_authorized")
        first = leases[0]
        assert first.valid_until - first.issued_at <= timedelta(seconds=1)
        assert first.authority.protected_runtime_process_resume_authority_granted is True
        assert first.authority.runtime_resume_authorized is False

        calls_before_replay = attestor.calls
        replay = await _authorize_resume(
            service,
            process_scheduling_result_id=process_scheduling_result_id,
            scope=scope,
            idempotency_key=idempotency_key,
        )
        assert replay == first
        assert attestor.calls == calls_before_replay

        claim_table = cast(
            Table, WorkflowProtectedRuntimeProcessResumeAuthorizationClaimModel.__table__
        )
        lease_table = cast(
            Table, WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseModel.__table__
        )
        async with engine.connect() as connection:
            claim_row = (
                (
                    await connection.execute(
                        select(claim_table).where(
                            claim_table.c.process_scheduling_result_id
                            == process_scheduling_result_id
                        )
                    )
                )
                .mappings()
                .one()
            )
            lease_row = (
                (
                    await connection.execute(
                        select(lease_table).where(
                            lease_table.c.process_scheduling_result_id
                            == process_scheduling_result_id
                        )
                    )
                )
                .mappings()
                .one()
            )
        assert claim_row["authorization_lease_id"] == lease_row["authorization_lease_id"]
        assert lease_row["claim_id"] == claim_row["claim_id"]
        assert lease_row["claim_digest"] == claim_row["canonical_digest"]

        policy = code_owned_workflow_protected_runtime_process_resume_authorization_policy()
        changed = await repository.preflight_protected_runtime_process_resume_authorization(
            WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightRequest(
                process_scheduling_result_id=process_scheduling_result_id,
                scope=scope,
                consumer_subject_id=policy.consumer_subject_id,
                consumer_audience=policy.consumer_audience,
                policy_id=policy.policy_id,
                policy_version=policy.policy_version,
                policy_digest=policy.canonical_digest,
                idempotency_key=idempotency_key,
                idempotency_digest=cast(str, claim_row["idempotency_digest"]),
                request_fingerprint="a" * 64,
                offline_signature_verifier=attestor,
                offline_process_scheduling_receipt_signature_verifier=(scheduling_receipt_verifier),
            )
        )
        assert changed.status is (
            WorkflowProtectedRuntimeProcessResumeAuthorizationPreflightStatus.IDEMPOTENCY_CONFLICT
        )
        assert changed.lease is None

        with pytest.raises(WorkflowProtectedRuntimeProcessResumeAuthorizationError) as no_reissue:
            await _authorize_resume(
                service,
                process_scheduling_result_id=process_scheduling_result_id,
                scope=scope,
                idempotency_key=f"imp-231-no-reissue-{uuid4().hex}",
            )
        assert no_reissue.value.code.endswith("already_authorized")

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
            async with engine.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError, match="append-only"):
                    await connection.execute(text(f"TRUNCATE TABLE {table.name}"))
                await transaction.rollback()

        downgrade_environment = os.environ.copy()
        downgrade_environment["ATLAS_DATABASE_URL"] = database_url
        downgrade = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", "downgrade", "20260821_0153"],
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
        if process_scheduling_result_id is not None:
            await _cleanup_resume_authorization(
                engine,
                process_scheduling_result_id=process_scheduling_result_id,
            )
        if process_creation_result_id is not None:
            await _cleanup_scheduling_consumption(
                engine,
                process_creation_result_id=process_creation_result_id,
            )
            await _cleanup_scheduling(
                engine,
                process_creation_result_id=process_creation_result_id,
            )
        if creation_lease_id is not None:
            await _cleanup_consumption(engine, authorization_lease_id=creation_lease_id)
        if readiness_result is not None:
            await _cleanup_process_creation(engine, readiness_result_id=readiness_result.result_id)
            await _cleanup_fixture_fences(
                engine,
                repository,
                readiness_result_id=readiness_result.result_id,
            )
        if seeded:
            await _cleanup_readiness(engine, tuple(seeded))
        await engine.dispose()
