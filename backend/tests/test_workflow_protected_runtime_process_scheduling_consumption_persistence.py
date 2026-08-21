from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint
from test_workflow_protected_runtime_process_scheduling_consumptions import (
    _consume,
    _Repository,
    _service,
    _source,
)

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeProcessSchedulingAttemptModel,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimModel,
    WorkflowProtectedRuntimeProcessSchedulingResultModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingClaimRequest,
    WorkflowProtectedRuntimeProcessSchedulingClaimWrite,
    WorkflowProtectedRuntimeProcessSchedulingResultRequest,
    WorkflowProtectedRuntimeProcessSchedulingResultWrite,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "migrations"
    / "versions"
    / "20260821_0153_workflow_protected_runtime_process_scheduling_consumption.py"
)
POSTGRES_ADAPTER = ROOT / "src" / "atlas" / "modules" / "workflows" / "adapters" / "postgres.py"
MODELS = (
    WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimModel,
    WorkflowProtectedRuntimeProcessSchedulingAttemptModel,
    WorkflowProtectedRuntimeProcessSchedulingResultModel,
)


def _constraint_names(table: Table) -> set[str]:
    return {item.name for item in table.constraints if isinstance(item.name, str)}


def _checks(table: Table) -> str:
    return " ".join(
        str(item.sqltext) for item in table.constraints if isinstance(item, CheckConstraint)
    )


def test_migration_is_linear_append_only_and_guarded() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260821_0153"' in source
    assert 'down_revision: str | None = "20260820_0152"' in source
    assert source.count("op.create_table(") == 3
    assert "BEFORE UPDATE OR DELETE" in source
    assert "BEFORE TRUNCATE" in source
    assert "refusing guarded downgrade" in source
    assert "uq_wf_rtpsched_lease_cons_source" in source
    assert 'nullable=name == "process_creation_failure_class"' in source


def test_models_bind_exact_adr179_lineage_and_source_nullability() -> None:
    required = {
        "scheduling_authorization_lease_id",
        "scheduling_authorization_lease_digest",
        "scheduling_authorization_claim_id",
        "scheduling_authorization_claim_digest",
        "process_state_attestation_id",
        "process_state_attestation_digest",
        "scheduling_profile_id",
        "scheduling_profile_version",
        "scheduling_profile_digest",
        "process_creation_result_digest",
        "process_creation_attempt_digest",
        "process_creation_claim_digest",
        "process_creation_authorization_lease_digest",
        "process_creation_authorization_claim_digest",
        "process_creation_receipt_digest",
    }
    source_digests = {name for name in required if name.endswith("_digest")}
    for model in MODELS:
        table = cast(Table, model.__table__)
        assert required <= set(table.c.keys())
        assert table.c.process_creation_failure_class.nullable is True
        assert all(table.c[name].nullable is False for name in source_digests)
        foreign_keys = {
            item.name
            for item in table.foreign_key_constraints
            if isinstance(item, ForeignKeyConstraint)
        }
        stem = (
            "claim"
            if model is WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimModel
            else "attempt"
            if model is WorkflowProtectedRuntimeProcessSchedulingAttemptModel
            else "result"
        )
        assert f"fk_wf_rtpsched_cons_{stem}_lease" in foreign_keys
        assert f"fk_wf_rtpsched_cons_{stem}_claim" in foreign_keys


def test_one_claim_attempt_and_result_per_adr179_lease() -> None:
    claim = cast(Table, WorkflowProtectedRuntimeProcessSchedulingConsumptionClaimModel.__table__)
    attempt = cast(Table, WorkflowProtectedRuntimeProcessSchedulingAttemptModel.__table__)
    result = cast(Table, WorkflowProtectedRuntimeProcessSchedulingResultModel.__table__)

    assert "uq_wf_rtpsched_cons_claim_lease" in _constraint_names(claim)
    assert "uq_wf_rtpsched_cons_attempt_lease" in _constraint_names(attempt)
    assert "uq_wf_rtpsched_cons_result_lease" in _constraint_names(result)
    assert "fk_wf_rtpsched_cons_attempt_cons_claim" in _constraint_names(attempt)
    assert "fk_wf_rtpsched_cons_result_attempt" in _constraint_names(result)
    assert all(
        isinstance(item, UniqueConstraint)
        for table in (claim, attempt, result)
        for item in table.constraints
        if isinstance(item.name, str) and item.name.startswith("uq_wf_rtpsched_cons")
    )


def test_result_is_terminal_suspended_non_runnable_and_zero_authority() -> None:
    result = cast(Table, WorkflowProtectedRuntimeProcessSchedulingResultModel.__table__)
    checks = _checks(result)

    for state in (
        "process_scheduled_suspended_in_protected_boundary",
        "process_scheduling_rejected_without_scheduling",
        "process_scheduling_failed_without_scheduling",
        "process_scheduling_outcome_uncertain",
    ):
        assert state in checks
    assert "NOT result_process_runnable" in checks
    assert "NOT result_process_resumed" in checks
    assert "NOT result_process_dispatched" in checks
    assert "NOT result_process_executed" in checks
    assert "NOT protected_runtime_process_scheduling_authority_granted" in checks
    assert "NOT network_access_authorized" in checks
    assert "NOT infrastructure_mutation_authorized" in checks


def test_repository_is_replay_first_and_commits_claim_attempt_atomically() -> None:
    source = POSTGRES_ADAPTER.read_text(encoding="utf-8")
    method = source.index("async def claim_protected_runtime_process_scheduling")
    result_method = source.index(
        "async def record_protected_runtime_process_scheduling_result", method
    )
    body = source[method:result_method]

    assert body.index("_protected_runtime_process_scheduling_locked_replay") < body.index(
        "_protected_runtime_process_scheduling_request_is_valid"
    )
    assert "session.add_all(" in body
    assert body.count("await session.commit()") == 1
    assert body.index("session.add_all(") < body.index("await session.commit()")
    assert "func.clock_timestamp()" in source


class _CapturingRepository(_Repository):
    claim_request: WorkflowProtectedRuntimeProcessSchedulingClaimRequest | None = None
    result_request: WorkflowProtectedRuntimeProcessSchedulingResultRequest | None = None

    async def claim_protected_runtime_process_scheduling(
        self, request: WorkflowProtectedRuntimeProcessSchedulingClaimRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingClaimWrite:
        self.claim_request = request
        return await super().claim_protected_runtime_process_scheduling(request)

    async def record_protected_runtime_process_scheduling_result(
        self, request: WorkflowProtectedRuntimeProcessSchedulingResultRequest
    ) -> WorkflowProtectedRuntimeProcessSchedulingResultWrite:
        self.result_request = request
        return await super().record_protected_runtime_process_scheduling_result(request)


@pytest.mark.asyncio
async def test_postgres_models_accept_real_domain_claim_attempt_and_result() -> None:
    repository = _CapturingRepository(await _source())
    service, _ = _service(repository)
    await _consume(service)
    assert repository.claim_request is not None
    assert repository.result_request is not None

    lease = repository.source.authorization_lease
    source_values = {
        name: getattr(lease, name)
        for name in lease.__dataclass_fields__
        if name not in {"scope", "authority"}
    }
    source_values.update(
        organization_id=lease.scope.organization_id,
        environment_id=lease.scope.environment_id,
        site_id=lease.scope.site_id,
        state=lease.state.value,
        **lease.authority.canonical_value(),
    )
    source_row = SimpleNamespace(**source_values)
    claim_mapper = (
        PostgreSQLWorkflowPlanRepository
    )._protected_runtime_process_scheduling_consumption_claim_model
    attempt_mapper = (
        PostgreSQLWorkflowPlanRepository
    )._protected_runtime_process_scheduling_consumption_attempt_model
    result_mapper = (
        PostgreSQLWorkflowPlanRepository
    )._protected_runtime_process_scheduling_consumption_result_model
    claim_row = claim_mapper(repository.claim_request, authorization_lease_row=source_row)
    attempt_row = attempt_mapper(repository.claim_request, authorization_lease_row=source_row)
    result_row = result_mapper(repository.result_request, attempt_row=attempt_row)

    assert claim_row.scheduling_authorization_lease_id == lease.authorization_lease_id
    assert claim_row.process_creation_failure_class is None
    assert claim_row.process_creation_receipt_digest
    assert (
        attempt_row.scheduler_primitive_digest
        == repository.claim_request.candidate_attempt.primitive_digest
    )
    assert attempt_row.primitive_digest == lease.primitive_digest
    assert (
        result_row.scheduler_primitive_digest == repository.result_request.result.primitive_digest
    )
    assert result_row.failure_class is None
    assert (
        PostgreSQLWorkflowPlanRepository._protected_runtime_process_scheduling_attempt_from_row(
            attempt_row
        )
        == repository.claim_request.candidate_attempt
    )
    assert (
        PostgreSQLWorkflowPlanRepository._protected_runtime_process_scheduling_result_from_row(
            result_row
        )
        == repository.result_request.result
    )


def test_alembic_graph_has_single_0153_head_and_identifiers_fit_postgresql() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260821_0153"]
    revision = script.get_revision("20260821_0153")
    assert revision is not None
    assert revision.down_revision == "20260820_0152"
    names = {
        item.name
        for model in MODELS
        for item in cast(Table, model.__table__).constraints
        if isinstance(item.name, str)
    }
    assert names
    assert max(map(len, names)) <= 63
