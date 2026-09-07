from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.platform.adapters.bootstrap_rollback_memory import (
    InMemoryBootstrapRollbackRepository,
)
from atlas.modules.platform.application.bootstrap_rollback import (
    BootstrapRollbackError,
    BootstrapRollbackService,
)
from atlas.modules.platform.domain.bootstrap_rollback import (
    ComponentVersionCompatibility,
    RollbackOutcome,
    RollbackSupportDeclaration,
    SchemaCompatibilityCheck,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service() -> tuple[
    BootstrapRollbackService, CollectingAuditSink, InMemoryBootstrapRollbackRepository
]:
    audit_sink = CollectingAuditSink()
    repository = InMemoryBootstrapRollbackRepository()
    service = BootstrapRollbackService(
        repository=repository,
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )
    return service, audit_sink, repository


async def _plan(service: BootstrapRollbackService, *, permitted: bool = True) -> str:
    await service.plan_rollback(
        plan_id="plan.rollback.primary",
        release_id="release.atlas.2026.9.0",
        target_release_id="release.atlas.2026.8.0",
        support=RollbackSupportDeclaration(
            release_id="release.atlas.2026.9.0",
            application_rollback_supported=permitted,
            data_rollback_supported=permitted,
            unsupported_rationale=None if permitted else "No compatible downgrade path.",
        ),
        schema_check=SchemaCompatibilityCheck(
            current_schema_revision="20260907_0170",
            target_schema_revision="20260827_0169",
            irreversible_migrations_applied=(),
            compatible=True,
        ),
        component_compatibility=(
            ComponentVersionCompatibility(
                component="workflows",
                current_version="1.2.0",
                target_version="1.1.0",
                compatible=True,
            ),
        ),
        configuration_rollback_independent=True,
        secret_rollback_independent=True,
        artifacts_available_until=NOW + timedelta(days=7),
        correlation_id="correlation.test",
    )
    return "plan.rollback.primary"


@pytest.mark.asyncio
async def test_plan_rollback_persists_and_audits() -> None:
    service, audit_sink, _repository = _service()
    plan_id = await _plan(service)
    assert plan_id == "plan.rollback.primary"
    assert any(item.result_code == "bootstrap_rollback_planned" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_plan_rollback_rejects_an_invalid_plan() -> None:
    service, _audit, _repository = _service()
    with pytest.raises(BootstrapRollbackError, match="bootstrap_rollback_plan_invalid"):
        await service.plan_rollback(
            plan_id="plan.rollback.primary",
            release_id="release.atlas.2026.9.0",
            target_release_id="release.atlas.2026.8.0",
            support=RollbackSupportDeclaration(
                release_id="release.other",
                application_rollback_supported=True,
                data_rollback_supported=True,
            ),
            schema_check=SchemaCompatibilityCheck(
                current_schema_revision="20260907_0170",
                target_schema_revision="20260827_0169",
                irreversible_migrations_applied=(),
                compatible=True,
            ),
            component_compatibility=(),
            configuration_rollback_independent=True,
            secret_rollback_independent=True,
            artifacts_available_until=NOW + timedelta(days=7),
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_record_attempt_requires_an_existing_plan() -> None:
    service, _audit, _repository = _service()
    with pytest.raises(BootstrapRollbackError, match="bootstrap_rollback_plan_unavailable"):
        await service.record_attempt(
            attempt_id="attempt.rollback.primary",
            plan_id="plan.no-such-plan",
            started_at=NOW,
            outcome=RollbackOutcome.SUCCEEDED,
            post_rollback_health_check_passed=True,
            post_rollback_security_check_passed=True,
            failure_recovery_reference=None,
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_record_attempt_succeeds_when_the_plan_permits_it() -> None:
    service, audit_sink, _repository = _service()
    plan_id = await _plan(service, permitted=True)
    attempt = await service.record_attempt(
        attempt_id="attempt.rollback.primary",
        plan_id=plan_id,
        started_at=NOW,
        outcome=RollbackOutcome.SUCCEEDED,
        post_rollback_health_check_passed=True,
        post_rollback_security_check_passed=True,
        failure_recovery_reference=None,
        correlation_id="correlation.test",
    )
    assert attempt.outcome is RollbackOutcome.SUCCEEDED
    assert any(item.result_code == "bootstrap_rollback_succeeded" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_record_attempt_refuses_a_successful_outcome_when_the_plan_forbids_it() -> None:
    service, _audit, _repository = _service()
    plan_id = await _plan(service, permitted=False)
    with pytest.raises(BootstrapRollbackError, match="bootstrap_rollback_not_permitted"):
        await service.record_attempt(
            attempt_id="attempt.rollback.primary",
            plan_id=plan_id,
            started_at=NOW,
            outcome=RollbackOutcome.SUCCEEDED,
            post_rollback_health_check_passed=True,
            post_rollback_security_check_passed=True,
            failure_recovery_reference=None,
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_record_attempt_allows_a_failed_outcome_with_documented_recovery() -> None:
    service, audit_sink, repository = _service()
    plan_id = await _plan(service, permitted=False)
    attempt = await service.record_attempt(
        attempt_id="attempt.rollback.primary",
        plan_id=plan_id,
        started_at=NOW,
        outcome=RollbackOutcome.FAILED,
        post_rollback_health_check_passed=False,
        post_rollback_security_check_passed=False,
        failure_recovery_reference="doc.recovery.procedure.001",
        correlation_id="correlation.test",
    )
    assert attempt.outcome is RollbackOutcome.FAILED
    assert any(item.result_code == "bootstrap_rollback_failed" for item in audit_sink.records)
    stored = await repository.get_attempt("attempt.rollback.primary")
    assert stored == attempt
