from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.platform.adapters.bootstrap_state_memory import (
    InMemoryBootstrapStateRepository,
)
from atlas.modules.platform.application.bootstrap_invalidation import (
    BootstrapInvalidationScopeError,
    BootstrapInvalidationService,
)
from atlas.modules.platform.domain.bootstrap_invalidation import BootstrapInvalidationState
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapRunIdentity,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

NOW = datetime(2026, 8, 4, 15, 0, tzinfo=UTC)


class AuditSink:
    def __init__(self, fail: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail = fail

    async def record(self, event: AuditRecord) -> None:
        if self.fail and event.event_type == "atlas.platform.bootstrap-invalidation.read":
            raise RuntimeError("audit unavailable")
        self.records.append(event)


def actor() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.development.operator",
        display_name="Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.development",
        role_ids=("role.development.operator",),
    )


def identity(**overrides: object) -> BootstrapRunIdentity:
    values: dict[str, object] = {
        "release_id": "release.atlas.lab-0.1.0",
        "profile": DeploymentProfile.LINUX_LAB,
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "plan_digest": "a" * 64,
        "resume_key": "resume.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "configuration_digest": "b" * 64,
        "phase_ids": (
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
        ),
    }
    values.update(overrides)
    return BootstrapRunIdentity(**values)  # type: ignore[arg-type]


async def seeded_repository() -> InMemoryBootstrapStateRepository:
    repository = InMemoryBootstrapStateRepository()
    claimed = await repository.claim(
        identity=identity(),
        lease_holder_id="session.bootstrap.primary",
        lease_duration=timedelta(minutes=10),
        idempotency_key="claim-invalidation-0001",
        request_fingerprint="c" * 64,
        now=NOW,
    )
    version = claimed.record.version
    for index, phase_id in enumerate(identity().phase_ids[:3], 1):
        result = await repository.checkpoint(
            run_id=claimed.record.run_id,
            plan_digest=identity().plan_digest,
            resume_key=identity().resume_key,
            phase_id=phase_id,
            state=BootstrapCheckpointState.COMPLETED,
            safe_output_references=(f"evidence.phase-{index}",),
            lease_holder_id="session.bootstrap.primary",
            expected_version=version,
            idempotency_key=f"checkpoint-invalidation-{index}",
            request_fingerprint=str(index) * 64,
            now=NOW + timedelta(seconds=index),
        )
        version = result.record.version
    return repository


def service(
    repository: InMemoryBootstrapStateRepository, sink: AuditSink | None = None
) -> BootstrapInvalidationService:
    return BootstrapInvalidationService(
        repository=repository,
        environment_id="environment.test",
        site_id="site.local",
        audit_sink=sink or AuditSink(),
        clock=lambda: NOW + timedelta(minutes=1),
    )


@pytest.mark.asyncio
async def test_identical_input_preserves_every_completed_checkpoint_without_mutation() -> None:
    repository = await seeded_repository()
    before = await repository.get_current(
        organization_id=actor().organization_id,
        environment_id="environment.test",
        site_id="site.local",
    )
    preview = await service(repository).preview(
        actor=actor(), candidate=identity(), correlation_id="correlation.unchanged"
    )
    after = await repository.get_current(
        organization_id=actor().organization_id,
        environment_id="environment.test",
        site_id="site.local",
    )
    assert preview.state is BootstrapInvalidationState.UNCHANGED
    assert preview.reusable_checkpoint_phase_ids == identity().phase_ids[:3]
    assert preview.changes == () and preview.earliest_affected_phase_id is None
    assert before == after


@pytest.mark.asyncio
async def test_configuration_drift_invalidates_from_configuration_only() -> None:
    repository = await seeded_repository()
    preview = await service(repository).preview(
        actor=actor(),
        candidate=replace(identity(), configuration_digest="d" * 64),
        correlation_id="correlation.configuration-drift",
    )
    assert preview.state is BootstrapInvalidationState.DRIFTED
    assert preview.earliest_affected_phase_id == "phase.configure"
    assert preview.reusable_checkpoint_phase_ids == ("phase.acquire",)
    assert preview.invalidated_checkpoint_phase_ids == ("phase.configure", "phase.trust")
    assert preview.downstream_phase_ids == identity().phase_ids[1:]
    assert preview.changes[0].reason_code == "bootstrap.configuration.changed"
    assert preview.changes[0].old_reference.startswith("sha256:")


@pytest.mark.asyncio
async def test_plan_drift_takes_precedence_over_configuration_and_phase_order() -> None:
    repository = await seeded_repository()
    reordered = (
        "phase.acquire",
        "phase.trust",
        "phase.configure",
        "phase.data",
        "phase.services",
    )
    preview = await service(repository).preview(
        actor=actor(),
        candidate=replace(
            identity(),
            plan_digest="e" * 64,
            configuration_digest="f" * 64,
            phase_ids=reordered,
        ),
        correlation_id="correlation.combined-drift",
    )
    assert preview.earliest_affected_phase_id == "phase.acquire"
    assert preview.reusable_checkpoint_phase_ids == ()
    assert preview.invalidated_checkpoint_phase_ids == identity().phase_ids[:3]
    assert {item.reason_code for item in preview.changes} == {
        "bootstrap.plan.changed",
        "bootstrap.configuration.changed",
        "bootstrap.phase-order.changed",
    }


@pytest.mark.asyncio
async def test_empty_foreign_scope_and_audit_failure_fail_closed() -> None:
    repository = InMemoryBootstrapStateRepository()
    empty = await service(repository).preview(
        actor=actor(), candidate=identity(), correlation_id="correlation.empty"
    )
    assert empty.state is BootstrapInvalidationState.EMPTY and empty.source_run_id is None

    sink = AuditSink()
    with pytest.raises(BootstrapInvalidationScopeError):
        await service(repository, sink).preview(
            actor=actor(),
            candidate=replace(identity(), site_id="site.foreign"),
            correlation_id="correlation.foreign",
        )
    assert sink.records[-1].scope_reference == "scope.redacted"

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service(repository, AuditSink(fail=True)).preview(
            actor=actor(), candidate=identity(), correlation_id="correlation.audit"
        )


def payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "schema_version": "atlas.bootstrap-invalidation-request.v1",
        "release_id": identity().release_id,
        "profile": identity().profile.value,
        "organization_id": identity().organization_id,
        "environment_id": identity().environment_id,
        "site_id": identity().site_id,
        "plan_digest": identity().plan_digest,
        "resume_key": identity().resume_key,
        "configuration_digest": identity().configuration_digest,
        "phase_ids": list(identity().phase_ids),
    }
    values.update(overrides)
    return values


def test_api_strict_empty_preview_authorization_and_non_executing_contract() -> None:
    app = create_app(
        Settings(environment="test", development_identity_enabled=True), audit_sink=AuditSink()
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/platform/bootstrap-invalidation-preview", json=payload())
        malformed = client.post(
            "/api/v1/platform/bootstrap-invalidation-preview",
            json=payload(unknown="unsafe"),
        )
    assert response.status_code == 200 and response.json()["data"]["state"] == "empty"
    assert response.headers["cache-control"] == "no-store"
    assert malformed.status_code == 422
    assert response.json()["data"]["execution_authorized"] is False
    assert response.json()["data"]["checkpoint_mutation_authorized"] is False

    denied = create_app(
        Settings(environment="test", development_identity_enabled=True, development_role_ids=())
    )
    with TestClient(denied) as client:
        denied_response = client.post(
            "/api/v1/platform/bootstrap-invalidation-preview", json=payload()
        )
    assert denied_response.status_code == 403 and "downstream_phase_ids" not in denied_response.text
