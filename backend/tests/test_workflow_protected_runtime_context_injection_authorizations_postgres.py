from __future__ import annotations

import asyncio
import inspect
import os
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import Table, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    WorkflowProtectedResidentContextAccessResultModel,
    WorkflowProtectedRuntimeContextInjectionAuthorizationClaimModel,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseModel,
    WorkflowProtectedRuntimeContextInjectionDestinationHeadModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application.protected_runtime_context_injection_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseRequest,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseStatus,
    WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightRequest,
    WorkflowProtectedRuntimeHandleLifecycleAttestation,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessConsumptionResultState,
    WorkflowProtectedRuntimeContextInjectionAuthorizationClaim,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLease,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_runtime_context_injection_authorization_policy,
)

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260816_0141_workflow_protected_runtime_context_injection_authorization.py"
)
POLICY_DIGEST = "cf8b08ca5eef652623d69dd4521f8e25a7d537dc80a06de40fa7cc4cdc34fbcb"
HANDLE_PROFILE_DIGEST = "1a318541a6303a5caf48131a737b1e79f458c7442498fa8dcc83f7f137e63e8a"
SLOT_PROFILE_DIGEST = "7c429ec36bd39f5d02add24b7622e55e32eb0cfca9345ebf272fd231385e3e6b"


class _OfflineVerifier:
    def verify_runtime_handle_lifecycle_attestation(self, attestation: object) -> bool:
        del attestation
        return True

    def verify_receipt(self, receipt: object) -> bool:
        del receipt
        return True


def test_migration_is_append_only_guarded_exactly_lined_and_non_colliding() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260816_0141"' in source
    assert 'down_revision: str | None = "20260816_0140"' in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "refusing guarded downgrade" in source
    assert "uq_wf_rc_access_result_injection_auth_lineage" in source
    assert "fk_wf_rtctx_inj_auth_lease_result" in source
    assert "fk_wf_rtctx_inj_auth_claim_result" in source
    assert "fk_wf_rtctx_inj_auth_claim_lease" in source
    assert "fk_wf_rtctx_inj_auth_lease_claim" in source
    assert "trg_wf_rtctx_inj_dest_head_append_only" not in source
    assert "destination_generation >= 1" in source
    assert "jsonb_build_object" in source
    assert 'initially="DEFERRED"' in source
    assert "pre_attestation_observed_at" in source
    assert "lifecycle_attestation_observed_at" in source
    assert "uq_wf_rtctx_inj_auth_lease_result" in source
    assert "uq_wf_rtctx_inj_auth_lease_handle" in source
    assert "uq_wf_rtctx_inj_auth_scope_idem" in source
    assert "INTERVAL '1 second'" in source
    assert POLICY_DIGEST in source
    assert HANDLE_PROFILE_DIGEST in source
    assert SLOT_PROFILE_DIGEST in source
    assert "handle_established_in_protected_boundary" in source
    assert "protected_runtime_context_injection_authority_granted" in source
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_orm_matches_exact_source_policy_lifecycle_and_authority_contract() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeContextInjectionAuthorizationClaimModel.__table__)
    head = cast(Table, WorkflowProtectedRuntimeContextInjectionDestinationHeadModel.__table__)
    result = cast(Table, WorkflowProtectedResidentContextAccessResultModel.__table__)
    checks = " ".join(
        str(constraint.sqltext)
        for table in (lease, claim)
        for constraint in table.constraints
        if hasattr(constraint, "sqltext")
    )
    assert "handle_established_in_protected_boundary" in checks
    assert "protected_runtime_context_injection_authority_granted" in checks
    assert "NOT protected_resident_context_access_authority_granted" in checks
    assert "NOT target_context_capsule_handoff_authority_granted" in checks
    assert "NOT target_context_capsule_opening_authority_granted" in checks
    assert "NOT protected_artifact_access_authority_granted" in checks
    assert "NOT network_access_authority_granted" in checks
    assert "NOT readiness_probe_authority_granted" in checks
    assert "NOT execution_authority_granted" in checks
    assert "NOT infrastructure_mutation_authority_granted" in checks
    assert "INTERVAL '1 second'" in checks
    assert "runtime_handle_undestroyed" in checks
    assert "NOT runtime_handle_is_bearer_capability" in checks
    assert POLICY_DIGEST in checks
    assert HANDLE_PROFILE_DIGEST in checks
    assert SLOT_PROFILE_DIGEST in checks
    assert {
        "fk_wf_rtctx_inj_auth_lease_result",
        "fk_wf_rtctx_inj_auth_lease_claim",
        "uq_wf_rtctx_inj_auth_lease_result",
        "uq_wf_rtctx_inj_auth_lease_handle",
        "uq_wf_rtctx_inj_auth_lease_claim",
    } <= {constraint.name for constraint in lease.constraints}
    assert {
        "fk_wf_rtctx_inj_auth_claim_result",
        "fk_wf_rtctx_inj_auth_claim_lease",
        "uq_wf_rtctx_inj_auth_scope_idem",
    } <= {constraint.name for constraint in claim.constraints}
    circular = next(
        constraint
        for constraint in lease.constraints
        if constraint.name == "fk_wf_rtctx_inj_auth_lease_claim"
    )
    assert circular.deferrable is True
    assert circular.initially == "DEFERRED"
    head_checks = " ".join(
        str(constraint.sqltext) for constraint in head.constraints if hasattr(constraint, "sqltext")
    )
    assert "payload =" in head_checks
    assert "destination_generation >= 1" in head_checks
    assert "jsonb_build_object" in head_checks
    assert POLICY_DIGEST in head_checks
    assert "uq_wf_rc_access_result_injection_auth_lineage" in {
        constraint.name for constraint in result.constraints
    }


def test_repository_locks_oldest_to_newest_uses_two_db_times_and_has_no_external_io() -> None:
    lock = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_protected_runtime_context_injection_authorization_rows
    )
    opening_lock = lock.index("opening_authorization_lease = (")
    access_lock = lock.index("access_authorization_lease = (", opening_lock)
    result_revalidation = lock.index("populate_existing=True", access_lock)
    assert opening_lock < access_lock < result_revalidation
    assert "seed_access_result" in lock
    assert "seed_access_authorization_lease" in lock
    assert "WorkflowProtectedRuntimeContextInjectionDestinationHeadModel" in lock
    assert lock.count("clock_timestamp") == 2
    assert lock.count("with_for_update") >= 12
    authorize = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.authorize_protected_runtime_context_injection
    )
    assert "attest_runtime_handle_lifecycle" not in authorize
    assert "inject_runtime_context" not in authorize
    assert "connector" not in authorize
    assert "network" not in authorize
    assert "session.commit" in authorize
    assert "IntegrityError" in authorize
    assert "_protected_runtime_context_injection_replay" in authorize


def test_repository_requires_signed_known_success_and_projects_database_time() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_runtime_context_injection_source_from_rows
    )
    assert "accessor_receipt_payload is None" in source
    assert "HANDLE_ESTABLISHED_IN_PROTECTED_BOUNDARY" not in source
    assert "required_access_result_state" in source
    assert "verify_receipt" in source
    assert "completed_at >= result.access_deadline" in source
    assert "protected_runtime_handle_is_bearer_capability is not False" in source
    assert "runtime_handle_established_in_protected_boundary is not True" in source
    assert "outcome_known is not True" in source
    assert "access_authorization_claim.canonical_digest != access_lease.claim_digest" in source
    assert "shared_access_lineage_names" in source
    assert "expected_access_authorization_audit" in source
    preflight = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.preflight_protected_runtime_context_injection_authorization
    )
    assert "attest_runtime_handle_lifecycle" not in preflight
    assert "offline_signature_verifier" in preflight
    assert "offline_accessor_receipt_signature_verifier" in preflight
    assert "_protected_runtime_context_injection_locked_lineage_matches" in preflight
    presentation = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.list_protected_runtime_context_injection_authorization_presentations
    )
    assert "statement_timestamp" in presentation
    assert presentation.count("session.execute") == 1
    assert "consumed=False" in presentation
    assert "PresentationState.ACTIVE" in presentation
    assert "PresentationState.EXPIRED" in presentation


@pytest.mark.asyncio
async def test_live_postgres_repository_authorize_race_current_head_and_append_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    destination_head_table = cast(
        Table, WorkflowProtectedRuntimeContextInjectionDestinationHeadModel.__table__
    )
    policy = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
    rotated_head_payload = {
        "destination_boundary_id": policy.destination_boundary_id,
        "destination_deployment_id": policy.destination_deployment_id,
        "destination_generation": policy.destination_generation + 1,
        "destination_fencing_token_digest": "f" * 64,
        "policy_digest": policy.canonical_digest,
    }
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            updated = await connection.execute(
                destination_head_table.update()
                .where(
                    WorkflowProtectedRuntimeContextInjectionDestinationHeadModel.destination_deployment_id
                    == policy.destination_deployment_id
                )
                .values(
                    destination_generation=policy.destination_generation + 1,
                    destination_fencing_token_digest="f" * 64,
                    canonical_digest=canonical_digest(rotated_head_payload),
                    payload=rotated_head_payload,
                )
            )
            assert updated.rowcount == 1
        finally:
            await transaction.rollback()
    lease_table = cast(
        Table, WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseModel.__table__
    )
    claim_table = cast(
        Table, WorkflowProtectedRuntimeContextInjectionAuthorizationClaimModel.__table__
    )
    seed = uuid4().hex
    source_now = datetime.now(UTC)
    first = _authorization_evidence(
        source_seed=seed,
        idempotency_seed=f"{seed}a",
        now=source_now,
    )
    second = _authorization_evidence(
        source_seed=seed,
        idempotency_seed=f"{seed}b",
        now=source_now,
    )

    async def lock_repository_rows(
        repository: PostgreSQLWorkflowPlanRepository,
        session: Any,
        *,
        request: WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseRequest,
    ) -> Any:
        del repository
        policy = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
        destination_head = await session.get(
            WorkflowProtectedRuntimeContextInjectionDestinationHeadModel,
            policy.destination_deployment_id,
            with_for_update=True,
        )
        assert destination_head is not None
        assert destination_head.current is True
        assert destination_head.destination_generation == policy.destination_generation
        assert (
            destination_head.destination_fencing_token_digest
            == policy.destination_fencing_token_digest
        )
        existing = tuple(
            (
                await session.scalars(
                    select(WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseModel)
                    .where(
                        WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseModel.access_result_id
                        == request.candidate.access_result_id
                    )
                    .with_for_update()
                )
            ).all()
        )
        observed_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
        return SimpleNamespace(
            observed_at=observed_at,
            existing_leases=existing,
            idempotency_claim=None,
        )

    monkeypatch.setattr(
        PostgreSQLWorkflowPlanRepository,
        "_lock_protected_runtime_context_injection_authorization_sources",
        lock_repository_rows,
    )
    monkeypatch.setattr(
        PostgreSQLWorkflowPlanRepository,
        "_protected_runtime_context_injection_replay",
        classmethod(lambda cls, **kwargs: None),
    )
    monkeypatch.setattr(
        PostgreSQLWorkflowPlanRepository,
        "_protected_runtime_context_injection_evidence_matches",
        classmethod(lambda cls, **kwargs: True),
    )

    async def authorize(evidence: _AuthorizationEvidence) -> Any:
        repository = PostgreSQLWorkflowPlanRepository(engine=engine)
        return await repository.authorize_protected_runtime_context_injection(
            evidence.authorization_request
        )

    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role = replica"))
            await connection.execute(
                cast(Table, WorkflowProtectedResidentContextAccessResultModel.__table__).insert(),
                first.source_result_values,
            )
        outcomes = await asyncio.wait_for(
            asyncio.gather(authorize(first), authorize(second)), timeout=15
        )
        assert {outcome.status for outcome in outcomes} == {
            WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseStatus.AUTHORIZED,
            WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseStatus.ALREADY_AUTHORIZED,
        }
        winner_index = next(
            index
            for index, outcome in enumerate(outcomes)
            if outcome.status
            is WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseStatus.AUTHORIZED
        )
        winner = (first, second)[winner_index]

        for table, key, value in (
            (lease_table, "authorization_lease_id", winner.lease.authorization_lease_id),
            (claim_table, "claim_id", winner.claim.claim_id),
        ):
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(
                        table.update()
                        .where(table.c[key] == value)
                        .values(payload={"changed": True})
                    )
    finally:
        await engine.dispose()


class _AuthorizationEvidence:
    def __init__(
        self,
        *,
        claim: WorkflowProtectedRuntimeContextInjectionAuthorizationClaim,
        lease: WorkflowProtectedRuntimeContextInjectionAuthorizationLease,
        attestation: WorkflowProtectedRuntimeHandleLifecycleAttestation,
        audit_payload: dict[str, object],
        idempotency_key: str,
        preflight: WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightRequest,
        authorization_request: WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseRequest,
        source_result_values: dict[str, object],
    ) -> None:
        self.claim = claim
        self.lease = lease
        self.attestation = attestation
        self.audit_payload = audit_payload
        self.idempotency_key = idempotency_key
        self.preflight = preflight
        self.authorization_request = authorization_request
        self.source_result_values = source_result_values


def _authorization_evidence(
    *,
    source_seed: str,
    idempotency_seed: str,
    now: datetime | None = None,
) -> _AuthorizationEvidence:
    policy = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
    scope = WorkflowScope(
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
    )
    now = now or datetime.now(UTC)
    completed = now - timedelta(milliseconds=200)
    recorded = now - timedelta(milliseconds=100)
    access_deadline = now + timedelta(seconds=2)
    handle_usable_until = now + timedelta(seconds=30)
    resident_usable_until = now + timedelta(seconds=40)
    claim_id = (
        "workflow-protected-runtime-context-injection-claim."
        f"{_digest(idempotency_seed, 'claim-id')[:24]}"
    )
    lease_id = (
        "workflow-protected-runtime-context-injection-lease."
        f"{_digest(idempotency_seed, 'lease-id')[:24]}"
    )
    idempotency_key = f"idempotency-{idempotency_seed}"
    idempotency_digest = _digest(idempotency_seed, "idempotency")
    request_fingerprint = _digest(idempotency_seed, "fingerprint")
    source_values: dict[str, object] = {
        "access_result_id": f"access.{source_seed}",
        "access_result_digest": _digest(source_seed, "result"),
        "access_attempt_id": f"access-attempt.{source_seed}",
        "access_attempt_digest": _digest(source_seed, "attempt"),
        "access_consumption_claim_id": f"access-claim.{source_seed}",
        "access_consumption_claim_digest": _digest(source_seed, "access-claim"),
        "access_authorization_lease_id": f"access-lease.{source_seed}",
        "access_authorization_lease_digest": _digest(source_seed, "access-lease"),
        "accessor_receipt_digest": _digest(source_seed, "accessor-receipt"),
        "access_result_state": (
            WorkflowProtectedResidentContextAccessConsumptionResultState.HANDLE_ESTABLISHED_IN_PROTECTED_BOUNDARY
        ),
        "access_completed_at": completed,
        "access_result_recorded_at": recorded,
        "access_deadline": access_deadline,
        "protected_runtime_handle_id": f"protected-runtime-handle.{source_seed}",
        "protected_runtime_handle_digest": _digest(source_seed, "runtime-handle"),
        "protected_runtime_handle_created_at": completed,
        "protected_runtime_handle_usable_until": handle_usable_until,
        "protected_runtime_handle_is_bearer_capability": False,
        "protected_resident_context_usable_until": resident_usable_until,
        "protected_resident_context_consumed": True,
        "runtime_handle_established_in_protected_boundary": True,
        "access_outcome_known": True,
        "destination_boundary_id": policy.destination_boundary_id,
        "destination_deployment_id": policy.destination_deployment_id,
        "destination_generation": policy.destination_generation,
        "destination_fencing_token_digest": policy.destination_fencing_token_digest,
        "runtime_handle_profile_id": policy.runtime_handle_profile_id,
        "runtime_handle_profile_version": policy.runtime_handle_profile_version,
        "runtime_handle_profile_digest": policy.runtime_handle_profile_digest,
        "scope": scope,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
    }
    audit_payload: dict[str, object] = {
        "schema_id": "audit.workflow-protected-runtime-context-injection-authorization",
        "schema_version": "1.0",
        "authorization_lease_id": lease_id,
        "access_result_id": source_values["access_result_id"],
        "request_fingerprint": request_fingerprint,
        "scope": scope.canonical_value(),
        "consumer_subject_id": policy.consumer_subject_id,
        "protected_runtime_context_injection_authority_granted": True,
        "prior_authority_granted": False,
    }
    prior_authority = _prior_authority_values()
    claim_values = {
        "claim_id": claim_id,
        **source_values,
        "request_fingerprint": request_fingerprint,
        "idempotency_digest": idempotency_digest,
        "authorization_audit_digest": canonical_digest(audit_payload),
        "claimed_at": now,
        **prior_authority,
        "protected_runtime_context_injection_authority_granted": False,
    }
    claim = WorkflowProtectedRuntimeContextInjectionAuthorizationClaim(
        **cast(Any, claim_values),
        canonical_digest=canonical_digest(_canonical_payload(claim_values)),
    )
    attestation_values: dict[str, object] = {
        "attestation_id": f"runtime-handle-lifecycle-attestation.{idempotency_seed}",
        "attestor_id": policy.required_attestor_id,
        "attestor_version": policy.required_attestor_version,
        "signing_key_id": policy.verification_signing_key_id,
        "signature_algorithm": "test-signature-v1",
        "access_result_id": source_values["access_result_id"],
        "access_result_digest": source_values["access_result_digest"],
        "access_attempt_id": source_values["access_attempt_id"],
        "access_attempt_digest": source_values["access_attempt_digest"],
        "access_consumption_claim_id": source_values["access_consumption_claim_id"],
        "access_consumption_claim_digest": source_values["access_consumption_claim_digest"],
        "access_authorization_lease_id": source_values["access_authorization_lease_id"],
        "access_authorization_lease_digest": source_values["access_authorization_lease_digest"],
        "accessor_receipt_digest": source_values["accessor_receipt_digest"],
        "accessor_receipt_signing_key_id": (
            "key.workflow-protected-resident-context-access-receipt.v1"
        ),
        "protected_runtime_handle_id": source_values["protected_runtime_handle_id"],
        "protected_runtime_handle_digest": source_values["protected_runtime_handle_digest"],
        "protected_runtime_handle_created_at": completed,
        "protected_runtime_handle_usable_until": handle_usable_until,
        "destination_boundary_id": policy.destination_boundary_id,
        "destination_deployment_id": policy.destination_deployment_id,
        "destination_generation": policy.destination_generation,
        "destination_fencing_token_digest": policy.destination_fencing_token_digest,
        "runtime_handle_profile_id": policy.runtime_handle_profile_id,
        "runtime_handle_profile_version": policy.runtime_handle_profile_version,
        "runtime_handle_profile_digest": policy.runtime_handle_profile_digest,
        "injector_contract_id": policy.required_injector_contract_id,
        "injector_contract_version": policy.required_injector_contract_version,
        "injector_id": policy.approved_injector_id,
        "injector_version": policy.approved_injector_version,
        "runtime_slot_profile_id": policy.runtime_slot_profile_id,
        "runtime_slot_profile_version": policy.runtime_slot_profile_version,
        "runtime_slot_profile_digest": policy.runtime_slot_profile_digest,
        "scope": scope,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "request_nonce_digest": _digest(idempotency_seed, "nonce"),
        "observed_at": now,
        "valid_until": now + timedelta(seconds=20),
        "runtime_handle_present": True,
        "runtime_handle_is_bearer_capability": False,
        "runtime_handle_unexpired": True,
        "runtime_handle_unrevoked": True,
        "runtime_handle_undestroyed": True,
        "runtime_handle_uninjected": True,
        "runtime_handle_unused": True,
        "destination_generation_current": True,
        "destination_fence_current": True,
        "injector_profile_eligible": True,
        "runtime_slot_profile_eligible": True,
        **_unsafe_attestation_values(),
        "integrity_signature": f"signature-{idempotency_seed}",
    }
    attestation = WorkflowProtectedRuntimeHandleLifecycleAttestation(
        **cast(Any, attestation_values),
        canonical_digest=canonical_digest(_canonical_payload(attestation_values)),
    )
    lease_values = {
        "authorization_lease_id": lease_id,
        "claim_id": claim.claim_id,
        "claim_digest": claim.canonical_digest,
        **source_values,
        "lifecycle_attestation_id": attestation.attestation_id,
        "lifecycle_attestation_digest": attestation.canonical_digest,
        "lifecycle_attestation_valid_until": attestation.valid_until,
        "injector_contract_id": policy.required_injector_contract_id,
        "injector_contract_version": policy.required_injector_contract_version,
        "injector_id": policy.approved_injector_id,
        "injector_version": policy.approved_injector_version,
        "runtime_slot_profile_id": policy.runtime_slot_profile_id,
        "runtime_slot_profile_version": policy.runtime_slot_profile_version,
        "runtime_slot_profile_digest": policy.runtime_slot_profile_digest,
        "issued_at": now,
        "valid_until": now + timedelta(milliseconds=500),
        "effective_until": attestation.valid_until,
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        **prior_authority,
        "protected_runtime_context_injection_authority_granted": True,
    }
    lease = WorkflowProtectedRuntimeContextInjectionAuthorizationLease(
        **cast(Any, lease_values),
        canonical_digest=canonical_digest(_canonical_payload(lease_values)),
    )
    preflight = WorkflowProtectedRuntimeContextInjectionAuthorizationPreflightRequest(
        access_result_id=cast(str, source_values["access_result_id"]),
        access_result_digest=cast(str, source_values["access_result_digest"]),
        scope=scope,
        consumer_subject_id=policy.consumer_subject_id,
        consumer_audience=policy.consumer_audience,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        policy_digest=policy.canonical_digest,
        idempotency_key=idempotency_key,
        idempotency_digest=idempotency_digest,
        request_fingerprint=request_fingerprint,
        offline_signature_verifier=_OfflineVerifier(),
        offline_accessor_receipt_signature_verifier=_OfflineVerifier(),
    )
    source_result_values: dict[str, object] = {
        "access_id": source_values["access_result_id"],
        "attempt_id": source_values["access_attempt_id"],
        "attempt_digest": source_values["access_attempt_digest"],
        "consumption_claim_id": source_values["access_consumption_claim_id"],
        "consumption_claim_digest": source_values["access_consumption_claim_digest"],
        "authorization_lease_id": source_values["access_authorization_lease_id"],
        "authorization_lease_digest": source_values["access_authorization_lease_digest"],
        "protected_resident_context_id": f"resident-context.{source_seed}",
        "protected_resident_context_digest": _digest(source_seed, "resident-context"),
        "organization_id": scope.organization_id,
        "environment_id": scope.environment_id,
        "site_id": scope.site_id,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": "purpose.workflow-protected-resident-context-access-consumption",
        "policy_id": "policy.workflow-protected-resident-context-access-consumption",
        "policy_version": "1.0",
        "policy_digest": "9113356099474b5ed0239c16593bdec1ffd6212dfdeadefac9bb25cbcc20660d",
        "accessor_id": f"accessor.{source_seed}",
        "accessor_version": "1.0",
        "runtime_handle_profile_id": policy.runtime_handle_profile_id,
        "runtime_handle_profile_version": policy.runtime_handle_profile_version,
        "runtime_handle_profile_digest": policy.runtime_handle_profile_digest,
        "protected_runtime_handle_id": source_values["protected_runtime_handle_id"],
        "protected_runtime_handle_digest": source_values["protected_runtime_handle_digest"],
        "protected_runtime_handle_created_at": completed,
        "protected_runtime_handle_usable_until": handle_usable_until,
        "protected_runtime_handle_is_bearer_capability": False,
        "runtime_handle_established_in_protected_boundary": True,
        "protected_resident_context_consumed": True,
        "runtime_handle_absence_confirmed": False,
        "outcome_known": True,
        "accessor_receipt_digest": source_values["accessor_receipt_digest"],
        "access_deadline": access_deadline,
        "completed_at": completed,
        "recorded_at": recorded,
        "protected_resident_context_usable_until": resident_usable_until,
        "state": "handle_established_in_protected_boundary",
        "failure_class": None,
        **{
            name: False
            for name in (
                "protected_resident_context_access_authority_granted",
                "target_context_capsule_handoff_authority_granted",
                "target_context_capsule_opening_authority_granted",
                "endpoint_resolution_authority_granted",
                "route_selection_authority_granted",
                "route_binding_authority_granted",
                "credential_selection_authority_granted",
                "credential_assignment_binding_authority_granted",
                "credential_access_authority_granted",
                "credential_brokerage_authority_granted",
                "credential_resolution_authority_granted",
                "protected_artifact_access_authority_granted",
                "credential_delivery_authority_granted",
                "network_access_authority_granted",
                "readiness_probe_authority_granted",
                "publication_authority_granted",
                "delivery_authority_granted",
                "dispatch_authority_granted",
                "execution_authority_granted",
                "infrastructure_mutation_authority_granted",
            )
        },
        "canonical_digest": source_values["access_result_digest"],
        "payload": {"fixture": source_seed},
        "accessor_receipt_payload": {
            "canonical_digest": source_values["accessor_receipt_digest"],
            "fixture": source_seed,
        },
    }
    authorization_request = WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseRequest(
        source=cast(Any, None),
        lifecycle_attestation=attestation,
        expected_request_nonce_digest=attestation.request_nonce_digest,
        offline_signature_verifier=_OfflineVerifier(),
        offline_accessor_receipt_signature_verifier=_OfflineVerifier(),
        expected_policy_digest=policy.canonical_digest,
        expected_validity_window_seconds=1,
        scope=scope,
        consumer_subject_id=policy.consumer_subject_id,
        consumer_audience=policy.consumer_audience,
        pre_attestation_observed_at=attestation.observed_at,
        requested_at=now,
        candidate_claim=claim,
        candidate=lease,
        idempotency_key=idempotency_key,
        idempotency_digest=idempotency_digest,
        request_fingerprint=request_fingerprint,
    )
    return _AuthorizationEvidence(
        claim=claim,
        lease=lease,
        attestation=attestation,
        audit_payload=audit_payload,
        idempotency_key=idempotency_key,
        preflight=preflight,
        authorization_request=authorization_request,
        source_result_values=source_result_values,
    )


def _prior_authority_values() -> dict[str, bool]:
    return {
        "endpoint_resolution_authorized": False,
        "route_selection_authorized": False,
        "route_binding_authorized": False,
        "credential_selection_authorized": False,
        "credential_assignment_binding_authorized": False,
        "credential_access_authorized": False,
        "credential_brokerage_authorized": False,
        "credential_resolution_authorized": False,
        "protected_artifact_access_authorized": False,
        "credential_delivery_authorized": False,
        "network_access_authorized": False,
        "readiness_probe_authorized": False,
        "publication_authorized": False,
        "delivery_authorized": False,
        "dispatch_authorized": False,
        "execution_authorized": False,
        "infrastructure_mutation_authorized": False,
        "target_context_capsule_handoff_authorized": False,
        "target_context_capsule_opening_authorized": False,
        "protected_resident_context_access_authority_granted": False,
    }


def _unsafe_attestation_values() -> dict[str, bool]:
    return {
        "raw_context_included": False,
        "runtime_handle_material_included": False,
        "runtime_payload_included": False,
        "runtime_handle_locator_included": False,
        "endpoint_included": False,
        "credential_included": False,
        "secret_included": False,
        "bearer_token_included": False,
        "provider_payload_included": False,
        "handle_lookup_authorized": False,
        "handle_retrieval_authorized": False,
        "handle_use_authorized": False,
        "runtime_use_authorized": False,
        "runtime_context_injection_authorized": False,
        "injection_consumption_outstanding": False,
        "connector_activity_authorized": False,
        "network_activity_authorized": False,
        "readiness_probe_authorized": False,
        "publication_authorized": False,
        "delivery_authorized": False,
        "dispatch_authorized": False,
        "execution_authorized": False,
        "infrastructure_mutation_authorized": False,
    }


def _canonical_payload(values: dict[str, object]) -> dict[str, object]:
    return {name: _canonical_value(value) for name, value in values.items()}


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    canonical_value = getattr(value, "canonical_value", None)
    if callable(canonical_value):
        return cast(Any, canonical_value)()
    return value


def _model_values(model: Any) -> dict[str, object]:
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


def _digest(seed: str, name: str) -> str:
    return sha256(f"{seed}:{name}".encode()).hexdigest()
