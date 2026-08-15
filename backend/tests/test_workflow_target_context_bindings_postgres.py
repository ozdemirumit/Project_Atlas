from __future__ import annotations

import asyncio
import inspect
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import CheckConstraint, Table, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from test_workflow_endpoint_resolution_authorization_leases_postgres import (
    _reset_endpoint_resolution_authorization_rows,
    _resolver_context,
)
from test_workflow_physical_transport_route_bindings_postgres import (
    _integration_request as physical_route_binding_request,
)
from test_workflow_physical_transport_route_bindings_postgres import (
    _integration_sources,
    _reset_integration_rows,
    _seed_integration_sources,
)
from test_workflow_route_freshness_admissions import CollectingAuditSink
from test_workflow_route_freshness_admissions_postgres import (
    _context as route_freshness_context,
)
from test_workflow_route_freshness_admissions_postgres import (
    _reset_freshness_rows,
    _selection_head,
)
from test_workflow_transport_credential_assignment_freshness_admissions_postgres import (
    _admission_request as credential_freshness_request,
)
from test_workflow_transport_credential_assignment_freshness_admissions_postgres import (
    _head as credential_head,
)
from test_workflow_transport_credential_assignment_snapshots import assignment_fixture

from atlas.core.persistence.models import (
    WorkflowEventPhysicalTransportTargetContextBindingClaimModel,
    WorkflowEventPhysicalTransportTargetContextBindingModel,
)
from atlas.modules.workflows.adapters import SyntheticWorkflowPhysicalTransportEndpointMaterializer
from atlas.modules.workflows.adapters.credential_materialization_synthetic import (
    SyntheticWorkflowPhysicalTransportCredentialMaterializer,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService,
    WorkflowEventPhysicalTransportCredentialMaterializationService,
    WorkflowEventPhysicalTransportEndpointMaterializationService,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionService,
    WorkflowEventPhysicalTransportTargetContextBindingRequest,
    WorkflowEventPhysicalTransportTargetContextBindingStatus,
)
from atlas.modules.workflows.application.credential_assignment_binding_ports import (
    WorkflowTransportCredentialAssignmentBindingRequest,
)
from atlas.modules.workflows.application.credential_assignment_bindings import (
    WorkflowEventPhysicalTransportCredentialAssignmentBindingService,
)
from atlas.modules.workflows.application.credential_assignment_snapshots import (
    WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT,
    WorkflowTransportCredentialAssignmentSnapshotService,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportRouteSnapshot,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialMaterializationResult,
    WorkflowEventPhysicalTransportEndpointMaterializationResult,
    WorkflowEventPhysicalTransportRouteBinding,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_access_authorization_policy,
    code_owned_workflow_event_physical_transport_credential_materialization_policy,
    code_owned_workflow_event_physical_transport_endpoint_materialization_policy,
    code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy,
    code_owned_workflow_event_physical_transport_route_freshness_policy,
    code_owned_workflow_event_physical_transport_target_context_binding_policy,
)

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260815_0131_workflow_target_context_binding.py"
)


async def _audit() -> None:
    return None


async def _failed_audit() -> None:
    raise RuntimeError("required precommit audit is unavailable")


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_schema_is_one_binding_per_source_append_only_and_zero_authority() -> None:
    binding = cast(Table, WorkflowEventPhysicalTransportTargetContextBindingModel.__table__)
    claim = cast(Table, WorkflowEventPhysicalTransportTargetContextBindingClaimModel.__table__)
    assert ("endpoint_materialization_id",) in _unique_columns(binding)
    assert ("credential_materialization_id",) in _unique_columns(binding)
    assert (
        "endpoint_materialization_id",
        "credential_materialization_id",
    ) in _unique_columns(binding)
    assert ("idempotency_scope_id", "idempotency_key") in _unique_columns(claim)
    checks = "\n".join(
        str(constraint.sqltext)
        for constraint in binding.constraints
        if isinstance(constraint, CheckConstraint)
    )
    authority_columns = {
        column.name for column in binding.columns if column.name.endswith("_authority_granted")
    }
    assert len(authority_columns) == 17
    assert all(f"NOT {name}" in checks for name in authority_columns)
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260815_0131"' in migration
    assert 'down_revision: str | None = "20260815_0130"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "trg_wf_tctx_bind_append_only" in migration
    assert "trg_wf_tctx_claim_append_only" in migration


def test_repository_locks_all_sources_before_two_database_clocks_and_atomic_pair() -> None:
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository.bind_target_context)
    lock = source.index("_lock_target_context_sources")
    first_clock = source.index("clock_timestamp", lock)
    evidence = source.index("_target_context_binding_evidence", first_clock)
    audit = source.index("required_precommit_audit", evidence)
    second_clock = source.index("clock_timestamp", audit)
    second_evidence = source.index("_target_context_binding_evidence", second_clock)
    binding_add = source.index("_target_context_binding_model", second_evidence)
    flush = source.index("await session.flush()", binding_add)
    claim_add = source.index("_target_context_binding_claim_model", flush)
    commit = source.index("await session.commit()", claim_add)
    assert (
        lock
        < first_clock
        < evidence
        < audit
        < second_clock
        < second_evidence
        < binding_add
        < flush
        < claim_add
        < commit
    )
    lock_source = inspect.getsource(PostgreSQLWorkflowPlanRepository._lock_target_context_sources)
    positions = [
        lock_source.index("route_binding ="),
        lock_source.index("route_snapshot ="),
        lock_source.index("endpoint_freshness ="),
        lock_source.index("endpoint_lease ="),
        lock_source.index("endpoint_claim ="),
        lock_source.index("endpoint_attempt ="),
        lock_source.index("endpoint_result ="),
        lock_source.index("credential_binding ="),
        lock_source.index("credential_snapshot ="),
        lock_source.index("credential_freshness ="),
        lock_source.index("credential_lease ="),
        lock_source.index("credential_claim ="),
        lock_source.index("credential_attempt ="),
        lock_source.index("credential_result ="),
        lock_source.index("existing_bindings ="),
        lock_source.index("idempotency_claim ="),
    ]
    assert positions == sorted(positions)
    assert lock_source.count(".with_for_update()") == 16
    assert "pg_advisory_xact_lock" not in lock_source
    assert "clock_timestamp" not in lock_source


def test_inventory_is_scope_bounded_and_strictly_rehydrates_payload() -> None:
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository.list_target_context_bindings)
    assert "organization_id" in source
    assert "environment_id" in source
    assert "site_id" in source
    assert ".limit(capped)" in source
    parser = inspect.getsource(PostgreSQLWorkflowPlanRepository._target_context_binding_from_row)
    assert "row.payload" in parser
    assert "canonical_digest" in parser
    assert "infrastructure_mutation_authority_granted" in parser


def test_memory_repository_is_not_a_production_fallback() -> None:
    assert InMemoryWorkflowPlanRepository().durable is False


def _credential_binding_request(
    *,
    route_binding: WorkflowEventPhysicalTransportRouteBinding,
    route: EventPhysicalTransportRouteSnapshot,
    assignment_id: str,
    revision: str,
    generation: int,
    rotation_epoch: int,
    suffix: str,
    now: datetime,
) -> tuple[
    WorkflowTransportCredentialAssignmentBindingRequest,
    EventPhysicalTransportCredentialAssignmentSnapshot,
]:
    assignment = assignment_fixture(
        assignment_id=assignment_id,
        assignment_revision=revision,
        route=route,
        scope=route.scope,
        credential_generation=generation,
        rotation_epoch=rotation_epoch,
        activated_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=1),
    )
    snapshot = WorkflowTransportCredentialAssignmentSnapshotService._build_snapshot(
        assignment=assignment,
        route=route,
        snapshotter_subject_id=WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT,
        captured_at=now - timedelta(seconds=3),
    )
    service = WorkflowEventPhysicalTransportCredentialAssignmentBindingService(
        binding_repository=cast(Any, object()), audit_sink=cast(Any, object())
    )
    candidate = service._build_binding(
        route_binding=route_binding,
        route=route,
        assignment=snapshot,
        binder_subject_id="service.workflow-physical-transport-credential-binder",
        bound_at=now - timedelta(seconds=2),
    )
    return (
        WorkflowTransportCredentialAssignmentBindingRequest(
            expected_physical_transport_route_binding_id=route_binding.binding_id,
            expected_physical_transport_route_binding_digest=route_binding.canonical_digest,
            expected_transport_route_snapshot_id=route.snapshot_id,
            expected_transport_route_snapshot_digest=route.canonical_digest,
            expected_credential_assignment_snapshot_id=snapshot.snapshot_id,
            expected_credential_assignment_snapshot_digest=snapshot.canonical_digest,
            expected_policy_digest=candidate.policy_digest,
            scope=candidate.scope,
            binder_subject_id=candidate.binder_subject_id,
            requested_at=candidate.bound_at,
            candidate=candidate,
            idempotency_key=f"credential-binding-target-context-{suffix}",
            request_fingerprint=canonical_digest({"credential-binding": suffix}),
            required_precommit_audit=_audit,
        ),
        snapshot,
    )


def _target_request(
    endpoint: WorkflowEventPhysicalTransportEndpointMaterializationResult,
    credential: WorkflowEventPhysicalTransportCredentialMaterializationResult,
    *,
    suffix: str,
    audit: Any = _audit,
) -> WorkflowEventPhysicalTransportTargetContextBindingRequest:
    policy = code_owned_workflow_event_physical_transport_target_context_binding_policy()
    fingerprint = canonical_digest(
        {
            "binder_subject_id": WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT,
            "credential_materialization_digest": credential.canonical_digest,
            "credential_materialization_id": credential.materialization_id,
            "endpoint_materialization_digest": endpoint.canonical_digest,
            "endpoint_materialization_id": endpoint.materialization_id,
            "policy_digest": policy.canonical_digest,
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "scope": endpoint.scope.canonical_value(),
        }
    )
    return WorkflowEventPhysicalTransportTargetContextBindingRequest(
        expected_endpoint_materialization_id=endpoint.materialization_id,
        expected_endpoint_materialization_digest=endpoint.canonical_digest,
        expected_credential_materialization_id=credential.materialization_id,
        expected_credential_materialization_digest=credential.canonical_digest,
        expected_policy_id=policy.policy_id,
        expected_policy_version=policy.policy_version,
        expected_policy_digest=policy.canonical_digest,
        scope=endpoint.scope,
        binder_subject_id=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT,
        requested_at=datetime.now(UTC),
        idempotency_key=f"target-context-postgres-{suffix}",
        request_fingerprint=fingerprint,
        required_precommit_audit=audit,
    )


async def _materialize_endpoint(
    repository: PostgreSQLWorkflowPlanRepository,
    *,
    route_binding: WorkflowEventPhysicalTransportRouteBinding,
    route: EventPhysicalTransportRouteSnapshot,
    now: datetime,
) -> tuple[WorkflowEventPhysicalTransportEndpointMaterializationResult, str, str]:
    head = _selection_head(route)
    await repository.synchronize_route_selection_heads((head,))
    freshness_service = WorkflowEventPhysicalTransportRouteFreshnessAdmissionService(
        admission_repository=repository, audit_sink=CollectingAuditSink()
    )
    freshness_policy = code_owned_workflow_event_physical_transport_route_freshness_policy()
    admission = await freshness_service.admit(
        physical_transport_route_binding_id=route_binding.binding_id,
        physical_transport_route_binding_digest=route_binding.canonical_digest,
        policy_id=freshness_policy.policy_id,
        policy_version=freshness_policy.policy_version,
        idempotency_key="target-context-endpoint-freshness-0001",
        context=route_freshness_context(route.scope, now),
    )
    authorization_service = (
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService(
            authorization_repository=repository, audit_sink=CollectingAuditSink()
        )
    )
    authorization_policy = (
        code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy()
    )
    lease = await authorization_service.authorize(
        freshness_admission_id=admission.freshness_admission_id,
        freshness_admission_digest=admission.canonical_digest,
        policy_id=authorization_policy.policy_id,
        policy_version=authorization_policy.policy_version,
        idempotency_key="target-context-endpoint-authorization-0001",
        context=_resolver_context(route.scope, datetime.now(UTC)),
    )
    materialization_service = WorkflowEventPhysicalTransportEndpointMaterializationService(
        repository=repository,
        materializer=SyntheticWorkflowPhysicalTransportEndpointMaterializer(),
        audit_sink=CollectingAuditSink(),
    )
    materialization_policy = (
        code_owned_workflow_event_physical_transport_endpoint_materialization_policy()
    )
    result = await materialization_service.materialize(
        authorization_lease_id=lease.authorization_lease_id,
        authorization_lease_digest=lease.canonical_digest,
        materialization_policy_id=materialization_policy.policy_id,
        materialization_policy_version=materialization_policy.policy_version,
        irreversible_consumption_acknowledged=True,
        uncertain_outcome_requires_new_authorization_acknowledged=True,
        idempotency_key="target-context-endpoint-materialization-0001",
        context=_resolver_context(route.scope, datetime.now(UTC)),
    )
    return result, admission.freshness_admission_id, head.head_id


async def _materialize_credential(
    repository: PostgreSQLWorkflowPlanRepository,
    *,
    binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
    route: EventPhysicalTransportRouteSnapshot,
    suffix: str,
) -> tuple[WorkflowEventPhysicalTransportCredentialMaterializationResult, str, str]:
    head = credential_head(route, snapshot)
    await repository.synchronize_credential_assignments((head,))
    freshness_request = credential_freshness_request(
        binding,
        snapshot,
        head,
        requested_at=datetime.now(UTC),
        idempotency_key=f"target-context-credential-freshness-{suffix}",
    )
    freshness_write = await repository.admit_credential_assignment_freshness(freshness_request)
    admission = freshness_write.admission
    assert admission is not None
    authorization_service = WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService(
        authorization_repository=repository, audit_sink=CollectingAuditSink()
    )
    authorization_policy = (
        code_owned_workflow_event_physical_transport_credential_access_authorization_policy()
    )
    from test_workflow_credential_access_authorization_leases_postgres import _context

    lease = await authorization_service.authorize(
        freshness_admission_id=admission.freshness_admission_id,
        freshness_admission_digest=admission.canonical_digest,
        policy_id=authorization_policy.policy_id,
        policy_version=authorization_policy.policy_version,
        idempotency_key=f"target-context-credential-authorization-{suffix}",
        context=_context(binding.scope, datetime.now(UTC)),
    )
    materialization_service = WorkflowEventPhysicalTransportCredentialMaterializationService(
        repository=repository,
        materializer=SyntheticWorkflowPhysicalTransportCredentialMaterializer(),
        audit_sink=CollectingAuditSink(),
    )
    materialization_policy = (
        code_owned_workflow_event_physical_transport_credential_materialization_policy()
    )
    result = await materialization_service.materialize(
        authorization_lease_id=lease.authorization_lease_id,
        authorization_lease_digest=lease.canonical_digest,
        materialization_policy_id=materialization_policy.policy_id,
        materialization_policy_version=materialization_policy.policy_version,
        irreversible_consumption_acknowledged=True,
        uncertain_outcome_requires_new_authorization_acknowledged=True,
        idempotency_key=f"target-context-credential-materialization-{suffix}",
        context=_context(binding.scope, datetime.now(UTC)),
    )
    return result, admission.freshness_admission_id, head.assignment_id


async def _delete_target_rows(engine: AsyncEngine, *, endpoint_materialization_id: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        await connection.execute(
            text(
                "DELETE FROM workflow_event_transport_target_context_binding_claims "
                "WHERE endpoint_materialization_id = :endpoint_id"
            ),
            {"endpoint_id": endpoint_materialization_id},
        )
        await connection.execute(
            text(
                "DELETE FROM workflow_event_transport_target_context_bindings "
                "WHERE endpoint_materialization_id = :endpoint_id"
            ),
            {"endpoint_id": endpoint_materialization_id},
        )


async def _cleanup_materialization_chain(
    engine: AsyncEngine,
    *,
    endpoint: WorkflowEventPhysicalTransportEndpointMaterializationResult | None,
    credentials: tuple[WorkflowEventPhysicalTransportCredentialMaterializationResult, ...],
    credential_binding_ids: tuple[str, ...],
    credential_snapshot_ids: tuple[str, ...],
    assignment_ids: tuple[str, ...],
) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        if endpoint is not None:
            params = {"lease": endpoint.authorization_lease_id}
            for table in (
                "workflow_event_endpoint_materialization_results",
                "workflow_event_endpoint_materialization_attempts",
                "workflow_event_endpoint_resolution_lease_consumption_claims",
            ):
                await connection.execute(
                    text(f"DELETE FROM {table} WHERE authorization_lease_id = :lease"), params
                )
        for credential in credentials:
            params = {"lease": credential.authorization_lease_id}
            for table in (
                "workflow_event_credential_materialization_results",
                "workflow_event_credential_materialization_attempts",
                "workflow_event_credential_access_lease_consumption_claims",
            ):
                await connection.execute(
                    text(f"DELETE FROM {table} WHERE authorization_lease_id = :lease"), params
                )
        for binding_id in credential_binding_ids:
            params = {"binding": binding_id}
            await connection.execute(
                text(
                    "DELETE FROM workflow_event_transport_credential_access_authorization_claims "
                    "WHERE authorization_lease_id IN ("
                    "SELECT authorization_lease_id "
                    "FROM workflow_event_transport_credential_access_authorization_leases "
                    "WHERE credential_assignment_binding_id = :binding)"
                ),
                params,
            )
            await connection.execute(
                text(
                    "DELETE FROM workflow_event_transport_credential_access_authorization_leases "
                    "WHERE credential_assignment_binding_id = :binding"
                ),
                params,
            )
            for table in (
                "workflow_event_transport_credential_freshness_claims",
                "workflow_event_transport_credential_freshness_admissions",
                "workflow_event_physical_transport_credential_binding_claims",
                "workflow_event_physical_transport_credential_bindings",
            ):
                column = (
                    "credential_assignment_binding_id"
                    if "freshness" in table
                    else "physical_transport_route_binding_id"
                    if "binding_claims" in table
                    else "binding_id"
                )
                if "binding_claims" in table:
                    continue
                await connection.execute(
                    text(f"DELETE FROM {table} WHERE {column} = :binding"), params
                )
            await connection.execute(
                text(
                    "DELETE FROM workflow_event_physical_transport_credential_binding_claims "
                    "WHERE binding_id = :binding"
                ),
                params,
            )
        await connection.execute(
            text(
                "DELETE FROM event_transport_credential_assignment_snapshots "
                "WHERE snapshot_id = ANY(:ids)"
            ),
            {"ids": list(credential_snapshot_ids)},
        )
        await connection.execute(
            text(
                "DELETE FROM deployment_event_transport_credential_assignments "
                "WHERE assignment_id = ANY(:ids)"
            ),
            {"ids": list(assignment_ids)},
        )


@pytest.mark.asyncio
async def test_live_postgres_binding_replay_race_audit_expiry_and_append_only() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    repository = PostgreSQLWorkflowPlanRepository(engine=engine)
    route_request = physical_route_binding_request()
    route = _integration_sources()[3]
    route_binding = route_request.candidate
    head = _selection_head(route)
    endpoint: WorkflowEventPhysicalTransportEndpointMaterializationResult | None = None
    endpoint_freshness_id = "freshness-admission.unseeded"
    credentials: tuple[WorkflowEventPhysicalTransportCredentialMaterializationResult, ...] = ()
    now = datetime.now(UTC)
    first_request, first_snapshot = _credential_binding_request(
        route_binding=route_binding,
        route=route,
        assignment_id="credential-assignment.target-context-primary",
        revision="31",
        generation=41,
        rotation_epoch=51,
        suffix="primary",
        now=now,
    )
    second_request, second_snapshot = _credential_binding_request(
        route_binding=route_binding,
        route=route,
        assignment_id="credential-assignment.target-context-alternate",
        revision="32",
        generation=42,
        rotation_epoch=52,
        suffix="alternate",
        now=now,
    )
    credential_requests = (first_request, second_request)
    try:
        await _delete_target_rows(
            engine,
            endpoint_materialization_id="workflow-endpoint-materialization.unseeded",
        )
        await _cleanup_materialization_chain(
            engine,
            endpoint=None,
            credentials=(),
            credential_binding_ids=tuple(item.candidate.binding_id for item in credential_requests),
            credential_snapshot_ids=(first_snapshot.snapshot_id, second_snapshot.snapshot_id),
            assignment_ids=(first_snapshot.assignment_id, second_snapshot.assignment_id),
        )
        await _reset_endpoint_resolution_authorization_rows(
            engine, freshness_admission_id="freshness-admission.unseeded"
        )
        await _reset_freshness_rows(
            engine, binding_id=route_binding.binding_id, head_id=head.head_id
        )
        await _reset_integration_rows(engine, route_request)
        await _seed_integration_sources(engine, route_request)
        bound_route = await repository.bind_physical_transport_route(route_request)
        assert bound_route.binding == route_binding

        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            session.add_all(
                (
                    repository._credential_assignment_snapshot_model(first_snapshot),
                    repository._credential_assignment_snapshot_model(second_snapshot),
                )
            )
            await session.commit()
        bound_credentials = []
        for credential_request in credential_requests:
            write = await repository.bind_credential_assignment(credential_request)
            assert write.binding is not None
            bound_credentials.append(write.binding)

        endpoint, endpoint_freshness_id, _ = await _materialize_endpoint(
            repository, route_binding=route_binding, route=route, now=datetime.now(UTC)
        )
        credential_results = []
        credential_freshness_ids = []
        for suffix, binding, snapshot in (
            ("primary", bound_credentials[0], first_snapshot),
            ("alternate", bound_credentials[1], second_snapshot),
        ):
            result, freshness_id, _ = await _materialize_credential(
                repository,
                binding=binding,
                snapshot=snapshot,
                route=route,
                suffix=suffix,
            )
            credential_results.append(result)
            credential_freshness_ids.append(freshness_id)
        credentials = tuple(credential_results)

        failed = await repository.bind_target_context(
            _target_request(endpoint, credentials[0], suffix="audit-failure", audit=_failed_audit)
        )
        assert (
            failed.status
            is WorkflowEventPhysicalTransportTargetContextBindingStatus.PRECOMMIT_AUDIT_FAILED
        )
        assert await repository.list_target_context_bindings(scope=route.scope) == ()

        primary = _target_request(endpoint, credentials[0], suffix="primary")
        alternate = _target_request(endpoint, credentials[1], suffix="alternate")
        outcomes = await asyncio.gather(
            repository.bind_target_context(primary),
            repository.bind_target_context(alternate),
        )
        assert {outcome.status for outcome in outcomes} == {
            WorkflowEventPhysicalTransportTargetContextBindingStatus.BOUND,
            WorkflowEventPhysicalTransportTargetContextBindingStatus.ALREADY_BOUND,
        }
        winner_index = next(
            index
            for index, outcome in enumerate(outcomes)
            if outcome.status is WorkflowEventPhysicalTransportTargetContextBindingStatus.BOUND
        )
        winner_request = (primary, alternate)[winner_index]
        winner = outcomes[winner_index].binding
        assert winner is not None
        assert not any(winner.authority.canonical_value().values())
        assert len(winner.authority.canonical_value()) == 17
        assert winner.target_context_commitment == repository._target_context_commitment(
            evidence={
                "route_binding": route_binding,
                "route_snapshot": route,
                "endpoint_result": endpoint,
                "credential_binding": bound_credentials[winner_index],
                "credential_snapshot": (first_snapshot, second_snapshot)[winner_index],
                "credential_result": credentials[winner_index],
            },
            policy=code_owned_workflow_event_physical_transport_target_context_binding_policy(),
        )

        changed = replace(
            winner_request,
            expected_credential_materialization_digest="f" * 64,
            request_fingerprint="e" * 64,
        )
        conflict = await repository.bind_target_context(changed)
        assert (
            conflict.status
            is WorkflowEventPhysicalTransportTargetContextBindingStatus.IDEMPOTENCY_CONFLICT
        )

        for statement in (
            "UPDATE workflow_event_transport_target_context_bindings "
            "SET state = state WHERE binding_id = :binding_id",
            "DELETE FROM workflow_event_transport_target_context_binding_claims "
            "WHERE binding_id = :binding_id",
        ):
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(text(statement), {"binding_id": winner.binding_id})

        delay = max(
            0.0,
            (winner.joint_usable_until - datetime.now(UTC)).total_seconds() + 0.15,
        )
        await asyncio.sleep(delay)
        replay = await repository.bind_target_context(winner_request)
        assert replay.status is WorkflowEventPhysicalTransportTargetContextBindingStatus.REPLAY
        assert replay.binding == winner

        await _delete_target_rows(engine, endpoint_materialization_id=endpoint.materialization_id)
        expired = await repository.bind_target_context(
            _target_request(endpoint, credentials[0], suffix="expired-first-create")
        )
        assert (
            expired.status
            is WorkflowEventPhysicalTransportTargetContextBindingStatus.EVIDENCE_CONFLICT
        )
        assert await repository.list_target_context_bindings(scope=route.scope) == ()
    finally:
        if endpoint is not None:
            await _delete_target_rows(
                engine, endpoint_materialization_id=endpoint.materialization_id
            )
        await _cleanup_materialization_chain(
            engine,
            endpoint=endpoint,
            credentials=credentials,
            credential_binding_ids=tuple(item.candidate.binding_id for item in credential_requests),
            credential_snapshot_ids=(first_snapshot.snapshot_id, second_snapshot.snapshot_id),
            assignment_ids=(first_snapshot.assignment_id, second_snapshot.assignment_id),
        )
        await _reset_endpoint_resolution_authorization_rows(
            engine, freshness_admission_id=endpoint_freshness_id
        )
        await _reset_freshness_rows(
            engine, binding_id=route_binding.binding_id, head_id=head.head_id
        )
        await _reset_integration_rows(engine, route_request)
        await engine.dispose()
