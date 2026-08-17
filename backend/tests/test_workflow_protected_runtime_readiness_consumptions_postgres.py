from __future__ import annotations

import ast
import asyncio
import os
import subprocess
import sys
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import Table, func, insert, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from test_workflow_protected_runtime_readiness_authorizations_postgres import (
    _AcceptAllReceiptVerifier,
    _authorization_request,
    _cleanup_runtime_start_sources,
    _ExactLifecycleVerifier,
    _seed_successful_runtime_start,
)

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel,
    WorkflowProtectedRuntimeReadinessConsumptionAttemptModel,
    WorkflowProtectedRuntimeReadinessConsumptionClaimModel,
    WorkflowProtectedRuntimeReadinessConsumptionResultModel,
    WorkflowProtectedRuntimeStartConsumptionResultModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application.protected_runtime_readiness_authorization_ports import (
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeReadinessAuthorizationSourceRequest,
)
from atlas.modules.workflows.application.protected_runtime_readiness_consumption_ports import (
    WorkflowProtectedRuntimeReadinessConsumptionClaimRequest,
    WorkflowProtectedRuntimeReadinessConsumptionClaimStatus,
    WorkflowProtectedRuntimeReadinessConsumptionReplayStatus,
    WorkflowProtectedRuntimeReadinessConsumptionResultRequest,
    WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus,
    build_workflow_protected_runtime_readiness_instruction,
    build_workflow_protected_runtime_readiness_signed_instruction_envelope,
)
from atlas.modules.workflows.application.protected_runtime_readiness_consumptions import (
    WorkflowProtectedRuntimeReadinessConsumptionService,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeReadinessConsumptionResultState,
    WorkflowProtectedRuntimeReadinessReceipt,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)

POSTGRES_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "atlas"
    / "modules"
    / "workflows"
    / "adapters"
    / "postgres.py"
)
SOURCE = POSTGRES_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
REPOSITORY = next(
    node
    for node in TREE.body
    if isinstance(node, ast.ClassDef) and node.name == "PostgreSQLWorkflowPlanRepository"
)


def _method_source(name: str) -> str:
    node = next(
        item
        for item in REPOSITORY.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    return ast.get_source_segment(SOURCE, node) or ""


def test_repository_implements_the_complete_readiness_consumption_port() -> None:
    for name in (
        "lookup_protected_runtime_readiness_consumption_replay",
        "get_protected_runtime_readiness_consumption_source",
        "claim_protected_runtime_readiness_consumption",
        "record_protected_runtime_readiness_consumption_result",
        "list_protected_runtime_readiness_attempts",
        "get_protected_runtime_readiness_results",
    ):
        assert _method_source(name)
    for symbol in (
        "WorkflowProtectedRuntimeReadinessConsumptionClaimModel",
        "WorkflowProtectedRuntimeReadinessConsumptionAttemptModel",
        "WorkflowProtectedRuntimeReadinessConsumptionResultModel",
        "_ProtectedRuntimeReadinessConsumptionLockedSources",
    ):
        assert symbol in SOURCE


def test_claim_path_is_atomic_database_timed_and_has_no_assessor_io() -> None:
    claim = _method_source("claim_protected_runtime_readiness_consumption")
    lock = _method_source("_lock_protected_runtime_readiness_consumption_rows")

    assert claim.index("_protected_runtime_readiness_consumption_locked_replay") < claim.index(
        "_protected_runtime_readiness_consumption_request_is_valid"
    )
    assert claim.count("session.add") == 2
    assert claim.count("session.flush") == 2
    assert claim.index("session.add") < claim.index("session.commit")
    assert lock.count("clock_timestamp") >= 2
    assert lock.index("first_observed_at") < lock.index("source_statement")
    assert lock.index("source_statement") < lock.index("claims =")
    assert lock.index("claims =") < lock.index("attempts =") < lock.index("results =")
    assert "with_for_update" in lock
    for model in (
        "WorkflowProtectedRuntimeReadinessAuthorizationClaimModel",
        "WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel",
        "WorkflowProtectedRuntimeStartConsumptionResultModel",
        "WorkflowProtectedRuntimeContextInjectionDestinationHeadModel",
        "WorkflowProtectedRuntimeContextInjectionSlotHeadModel",
        "WorkflowProtectedRuntimeStartCoordinationHeadModel",
    ):
        assert model in lock
    operational = (claim + lock).lower()
    for forbidden in (
        "assess_runtime_readiness",
        "httpx",
        "socket.",
        "subprocess",
        "connector_client",
        "mcp_client",
    ):
        assert forbidden not in operational


def test_repository_has_no_mutable_readiness_coordination_head() -> None:
    implementation = "\n".join(
        _method_source(name)
        for name in (
            "claim_protected_runtime_readiness_consumption",
            "record_protected_runtime_readiness_consumption_result",
            "_lock_protected_runtime_readiness_consumption_rows",
        )
    )
    assert "ReadinessCoordinationHead" not in implementation
    assert "runtime_readiness_coordination_heads" not in implementation
    assert "head.state =" not in implementation


def test_result_write_resolves_database_acknowledgement_errors_by_exact_read() -> None:
    implementation = _method_source("record_protected_runtime_readiness_consumption_result")
    assert "except SQLAlchemyError" in implementation
    assert implementation.index("await session.commit()") < implementation.index("existing = cast(")


def test_authorization_inventory_derives_consumption_without_mutating_the_lease() -> None:
    presentation = _method_source("list_protected_runtime_readiness_authorization_presentations")
    assert "WorkflowProtectedRuntimeReadinessConsumptionClaimModel" in presentation
    assert "consumed_expression" in presentation
    assert "consumed=bool(consumed)" in presentation
    assert "session.add" not in presentation
    assert "session.commit" not in presentation
    assert "update(" not in presentation


class _InstructionSigner:
    available = True
    signing_key_id = WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNING_KEY_ID
    signature_algorithm = WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str:
        assert len(payload_digest) == 64
        return "e" * 64


class _InstructionVerifier:
    available = True

    def verify_instruction_envelope(self, envelope: object) -> bool:
        del envelope
        return True


class _ReceiptVerifier:
    available = True

    def verify_receipt(self, receipt: object) -> bool:
        del receipt
        return True


class _AuditSink:
    async def record(self, event: object) -> None:
        del event


class _UnusedAssessor:
    available = True

    def __init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
        self.assessor_contract_id = policy.required_assessor_contract_id
        self.assessor_contract_version = policy.required_assessor_contract_version
        self.assessor_id = policy.approved_assessor_id
        self.assessor_version = policy.approved_assessor_version
        self.readiness_profile_id = policy.readiness_profile_id
        self.readiness_profile_version = policy.readiness_profile_version
        self.readiness_profile_digest = policy.readiness_profile_digest

    async def assess_runtime_readiness(self, invocation: object) -> None:
        del invocation
        raise AssertionError("repository tests must not invoke the assessor")


def _service(
    repository: PostgreSQLWorkflowPlanRepository,
) -> WorkflowProtectedRuntimeReadinessConsumptionService:
    return WorkflowProtectedRuntimeReadinessConsumptionService(
        repository=cast(Any, repository),
        assessor=cast(Any, _UnusedAssessor()),
        instruction_signer=_InstructionSigner(),
        instruction_signature_verifier=_InstructionVerifier(),
        receipt_signature_verifier=_ReceiptVerifier(),
        audit_sink=cast(Any, _AuditSink()),
    )


async def _consumption_request(
    repository: PostgreSQLWorkflowPlanRepository,
    *,
    authorization_lease_id: str,
    idempotency_key: str,
) -> WorkflowProtectedRuntimeReadinessConsumptionClaimRequest:
    source = await repository.get_protected_runtime_readiness_consumption_source(
        authorization_lease_id=authorization_lease_id
    )
    assert source is not None
    service = _service(repository)
    policy = service.policy
    now = await repository.get_authoritative_time()
    idempotency_digest = canonical_digest(
        {
            "scope": source.authorization_lease.scope.canonical_value(),
            "consumer_subject_id": policy.consumer_subject_id,
            "consumer_audience": policy.consumer_audience,
            "idempotency_key": idempotency_key,
        }
    )
    request_fingerprint = canonical_digest(
        {
            "authorization_lease_id": authorization_lease_id,
            "policy_digest": policy.canonical_digest,
            "idempotency_digest": idempotency_digest,
        }
    )
    seed = canonical_digest(
        {
            "authorization_lease_id": authorization_lease_id,
            "idempotency_digest": idempotency_digest,
            "request_fingerprint": request_fingerprint,
        }
    )
    claim = service._build_claim(
        source=source,
        claim_id=f"workflow-protected-runtime-readiness-consumption-claim.{seed[:24]}",
        attempt_id=f"workflow-protected-runtime-readiness-attempt.{seed[:24]}",
        consumption_id=f"workflow-protected-runtime-readiness-consumption.{seed[:24]}",
        scope=source.authorization_lease.scope,
        idempotency_digest=idempotency_digest,
        request_fingerprint=request_fingerprint,
        claimed_at=now,
    )
    attempt = service._build_attempt(source=source, claim=claim, started_at=now, seed=seed)
    envelope = build_workflow_protected_runtime_readiness_signed_instruction_envelope(
        build_workflow_protected_runtime_readiness_instruction(attempt), _InstructionSigner()
    )
    return WorkflowProtectedRuntimeReadinessConsumptionClaimRequest(
        source=source,
        candidate_claim=claim,
        candidate_attempt=attempt,
        signed_instruction_envelope=envelope,
        offline_instruction_signature_verifier=_InstructionVerifier(),
        expected_policy_id=policy.policy_id,
        expected_policy_version=policy.policy_version,
        expected_policy_digest=policy.canonical_digest,
        minimum_invocation_margin_milliseconds=policy.minimum_invocation_margin_milliseconds,
        idempotency_key=idempotency_key,
        idempotency_digest=idempotency_digest,
        request_fingerprint=request_fingerprint,
    )


def _receipt(request: WorkflowProtectedRuntimeReadinessConsumptionClaimRequest) -> Any:
    attempt = request.candidate_attempt
    instruction = request.signed_instruction_envelope.instruction
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    aliases: dict[str, object] = {
        "attempt_digest": attempt.canonical_digest,
        "instruction_digest": instruction.canonical_digest,
        "assessment_count_pre": 0,
        "assessment_count_post": 1,
        "result_state": (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READY_IN_PROTECTED_BOUNDARY,
        "runtime_ready": True,
        "readiness_assessment_performed": True,
        "runtime_locator_returned": False,
        "process_identifier_returned": False,
        "runtime_context_returned": False,
        "endpoint_material_returned": False,
        "credential_material_returned": False,
        "secret_material_returned": False,
        "command_constructed": False,
        "prompt_constructed": False,
        "model_inference_performed": False,
        "network_activity_performed": False,
        "connector_activity_performed": False,
        "mcp_activity_performed": False,
        "publication_performed": False,
        "delivery_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
        "completed_at": attempt.started_at,
        "signing_key_id": policy.receipt_verification_signing_key_id,
        "signature_algorithm": policy.receipt_signature_algorithm,
        "integrity_signature": "f" * 64,
    }
    values: dict[str, object] = {}
    for field in fields(WorkflowProtectedRuntimeReadinessReceipt):
        if field.name == "canonical_digest":
            continue
        values[field.name] = (
            aliases[field.name] if field.name in aliases else getattr(instruction, field.name)
        )
    receipt = WorkflowProtectedRuntimeReadinessReceipt(
        **cast(Any, values), canonical_digest="0" * 64
    )
    return replace(receipt, canonical_digest=canonical_digest(receipt.digest_payload()))


async def _seed_authorization(
    engine: Any,
    repository: PostgreSQLWorkflowPlanRepository,
    *,
    suffix: str,
) -> tuple[Any, Any]:
    async with engine.begin() as connection:
        start_request, _ = await _seed_successful_runtime_start(
            connection, repository, suffix=suffix
        )
    result_id = (
        "workflow-protected-runtime-start-result."
        f"{start_request.candidate_attempt.attempt_id.rsplit('.', 1)[-1]}"
    )
    async with engine.connect() as connection:
        result_digest = cast(
            str,
            await connection.scalar(
                select(WorkflowProtectedRuntimeStartConsumptionResultModel.canonical_digest).where(
                    WorkflowProtectedRuntimeStartConsumptionResultModel.result_id == result_id
                )
            ),
        )
    source = await repository.get_protected_runtime_readiness_authorization_source(
        WorkflowProtectedRuntimeReadinessAuthorizationSourceRequest(
            start_result_id=result_id,
            start_result_digest=result_digest,
            scope=start_request.candidate_attempt.scope,
            consumer_subject_id=start_request.candidate_attempt.consumer_subject_id,
            consumer_audience=start_request.candidate_attempt.consumer_audience,
            consumer_contract_id=start_request.candidate_attempt.consumer_contract_id,
            consumer_contract_version=start_request.candidate_attempt.consumer_contract_version,
        )
    )
    assert source is not None
    authorization_request = await _authorization_request(
        repository,
        source,
        idempotency_key=f"imp-226-auth-{uuid4().hex}",
        lifecycle_verifier=_ExactLifecycleVerifier(),
    )
    outcome = await repository.authorize_protected_runtime_readiness(authorization_request)
    assert outcome.status is WorkflowProtectedRuntimeReadinessAuthorizationLeaseStatus.AUTHORIZED
    assert outcome.lease is not None
    return start_request, outcome.lease


async def _cleanup(engine: Any, start_requests: tuple[Any, ...]) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        for request in start_requests:
            result_id = (
                "workflow-protected-runtime-start-result."
                f"{request.candidate_attempt.attempt_id.rsplit('.', 1)[-1]}"
            )
            for table in (
                "workflow_event_runtime_readiness_consumption_results",
                "workflow_event_runtime_readiness_consumption_attempts",
                "workflow_event_runtime_readiness_consumption_claims",
            ):
                await connection.execute(
                    text(f"DELETE FROM {table} WHERE start_result_id = :result_id"),
                    {"result_id": result_id},
                )
        await connection.execute(text("SET LOCAL session_replication_role = origin"))
    await _cleanup_runtime_start_sources(engine, start_requests)


@pytest.mark.asyncio
async def test_live_postgres_readiness_consumption_race_result_and_guards() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    repository = PostgreSQLWorkflowPlanRepository(engine=engine)
    repository.bind_protected_runtime_start_receipt_signature_verifier(
        cast(Any, _AcceptAllReceiptVerifier())
    )
    seeded: list[Any] = []
    try:
        start_request, lease = await _seed_authorization(
            engine, repository, suffix=f"imp226-race-{uuid4().hex[:12]}"
        )
        seeded.append(start_request)
        request = await _consumption_request(
            repository,
            authorization_lease_id=lease.authorization_lease_id,
            idempotency_key=f"imp-226-consume-{uuid4().hex}",
        )
        first, second = await asyncio.wait_for(
            asyncio.gather(
                repository.claim_protected_runtime_readiness_consumption(request),
                repository.claim_protected_runtime_readiness_consumption(request),
            ),
            timeout=15,
        )
        assert {first.status, second.status} == {
            WorkflowProtectedRuntimeReadinessConsumptionClaimStatus.CLAIMED,
            WorkflowProtectedRuntimeReadinessConsumptionClaimStatus.REPLAY_PENDING,
        }

        tampered_start_request, tampered_lease = await _seed_authorization(
            engine, repository, suffix=f"imp226-tampered-{uuid4().hex[:12]}"
        )
        seeded.append(tampered_start_request)
        tampered_request = await _consumption_request(
            repository,
            authorization_lease_id=tampered_lease.authorization_lease_id,
            idempotency_key=f"imp-226-tampered-{uuid4().hex}",
        )
        async with repository._sessions() as session:
            authorization_lease_row = await session.get(
                WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel,
                tampered_lease.authorization_lease_id,
            )
            assert authorization_lease_row is not None
            tampered_model = repository._protected_runtime_readiness_consumption_claim_model(
                tampered_request, authorization_lease_row=authorization_lease_row
            )
            tampered_values = {
                column.name: getattr(tampered_model, column.name)
                for column in tampered_model.__table__.columns
            }
            tampered_values["authorization_lease_digest"] = "0" * 64
        async with engine.connect() as connection:
            transaction = await connection.begin()
            with pytest.raises(DBAPIError, match="fk_wf_rtready_cons_claim_lease"):
                await connection.execute(
                    insert(
                        cast(
                            Table,
                            WorkflowProtectedRuntimeReadinessConsumptionClaimModel.__table__,
                        )
                    ),
                    tampered_values,
                )
                await transaction.commit()
            await transaction.rollback()
        replay = await repository.lookup_protected_runtime_readiness_consumption_replay(
            repository._protected_runtime_readiness_consumption_replay_request(request)
        )
        assert (
            replay.status
            is WorkflowProtectedRuntimeReadinessConsumptionReplayStatus.ATTEMPT_PENDING
        )
        changed_replay = await repository.lookup_protected_runtime_readiness_consumption_replay(
            replace(
                repository._protected_runtime_readiness_consumption_replay_request(request),
                request_fingerprint="9" * 64,
            )
        )
        assert (
            changed_replay.status
            is WorkflowProtectedRuntimeReadinessConsumptionReplayStatus.IDEMPOTENCY_CONFLICT
        )
        cross_tenant_replay = (
            await repository.lookup_protected_runtime_readiness_consumption_replay(
                replace(
                    repository._protected_runtime_readiness_consumption_replay_request(request),
                    scope=WorkflowScope(
                        "organization.cross-tenant",
                        request.candidate_claim.scope.environment_id,
                        request.candidate_claim.scope.site_id,
                    ),
                )
            )
        )
        assert (
            cross_tenant_replay.status
            is WorkflowProtectedRuntimeReadinessConsumptionReplayStatus.EVIDENCE_CONFLICT
        )

        service = _service(repository)
        receipt = _receipt(request)
        result = service._build_receipted_result(
            claim=request.candidate_claim,
            attempt=request.candidate_attempt,
            receipt=receipt,
            recorded_at=await repository.get_authoritative_time(),
        )
        result_request = WorkflowProtectedRuntimeReadinessConsumptionResultRequest(
            result=result,
            receipt=receipt,
            expected_claim_digest=request.candidate_claim.canonical_digest,
            expected_attempt_digest=request.candidate_attempt.canonical_digest,
        )
        recorded = await repository.record_protected_runtime_readiness_consumption_result(
            result_request
        )
        repeated = await repository.record_protected_runtime_readiness_consumption_result(
            result_request
        )
        assert (
            recorded.status
            is WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus.RECORDED
        )
        assert (
            repeated.status is WorkflowProtectedRuntimeReadinessConsumptionResultWriteStatus.REPLAY
        )
        assert repeated.result == result

        presentations = (
            await repository.list_protected_runtime_readiness_authorization_presentations(
                scope=lease.scope,
                authorization_lease_ids=(lease.authorization_lease_id,),
            )
        )
        assert len(presentations) == 1
        assert presentations[0].consumed is True
        assert presentations[0].protected_runtime_readiness_authority_granted is False

        async with engine.connect() as connection:
            assert (
                await connection.scalar(
                    text(
                        "SELECT to_regclass('workflow_event_runtime_readiness_coordination_heads')"
                    )
                )
                is None
            )

        for model, key, value in (
            (
                WorkflowProtectedRuntimeReadinessConsumptionClaimModel,
                "claim_id",
                request.candidate_claim.claim_id,
            ),
            (
                WorkflowProtectedRuntimeReadinessConsumptionAttemptModel,
                "attempt_id",
                request.candidate_attempt.attempt_id,
            ),
            (
                WorkflowProtectedRuntimeReadinessConsumptionResultModel,
                "result_id",
                result.result_id,
            ),
        ):
            table = cast(Table, model.__table__)
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
                    await connection.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
                await transaction.rollback()

        downgrade_environment = os.environ.copy()
        downgrade_environment["ATLAS_DATABASE_URL"] = database_url
        downgrade = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", "downgrade", "20260817_0148"],
            cwd=Path(__file__).parents[1],
            env=downgrade_environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert downgrade.returncode != 0
        assert "refusing downgrade" in (downgrade.stdout + downgrade.stderr).lower()
    finally:
        if seeded:
            await _cleanup(engine, tuple(seeded))
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_readiness_consumption_expires_while_waiting_for_lock() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    repository = PostgreSQLWorkflowPlanRepository(engine=engine)
    repository.bind_protected_runtime_start_receipt_signature_verifier(
        cast(Any, _AcceptAllReceiptVerifier())
    )
    seeded: list[Any] = []
    try:
        start_request, lease = await _seed_authorization(
            engine, repository, suffix=f"imp226-expiry-{uuid4().hex[:12]}"
        )
        seeded.append(start_request)
        request = await _consumption_request(
            repository,
            authorization_lease_id=lease.authorization_lease_id,
            idempotency_key=f"imp-226-expiry-{uuid4().hex}",
        )
        async with engine.connect() as blocker:
            transaction = await blocker.begin()
            await blocker.execute(
                text(
                    "SELECT authorization_lease_id "
                    "FROM workflow_event_runtime_readiness_auth_leases "
                    "WHERE authorization_lease_id = :lease_id FOR UPDATE"
                ),
                {"lease_id": lease.authorization_lease_id},
            )
            waiting = asyncio.create_task(
                repository.claim_protected_runtime_readiness_consumption(request)
            )
            await asyncio.sleep(1.05)
            await transaction.commit()
        outcome = await asyncio.wait_for(waiting, timeout=10)
        assert (
            outcome.status is WorkflowProtectedRuntimeReadinessConsumptionClaimStatus.LEASE_EXPIRED
        )
        async with engine.connect() as connection:
            counts = [
                await connection.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.authorization_lease_id == lease.authorization_lease_id)
                )
                for model in (
                    WorkflowProtectedRuntimeReadinessConsumptionClaimModel,
                    WorkflowProtectedRuntimeReadinessConsumptionAttemptModel,
                    WorkflowProtectedRuntimeReadinessConsumptionResultModel,
                )
            ]
        assert counts == [0, 0, 0]
    finally:
        if seeded:
            await _cleanup(engine, tuple(seeded))
        await engine.dispose()
