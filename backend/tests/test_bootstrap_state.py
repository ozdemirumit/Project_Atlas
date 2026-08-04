from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.core.persistence.models import Base
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.platform.adapters.bootstrap_state_memory import (
    InMemoryBootstrapStateRepository,
)
from atlas.modules.platform.adapters.bootstrap_state_postgres import (
    PostgreSQLBootstrapStateRepository,
)
from atlas.modules.platform.application.bootstrap_state import (
    BootstrapStateScopeError,
    BootstrapStateService,
)
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapRepositoryError
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapRunIdentity,
    BootstrapRunRecord,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

NOW = datetime(2026, 8, 4, 14, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class AuditSink:
    def __init__(self, fail: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail = fail

    async def record(self, event: AuditRecord) -> None:
        if self.fail and event.event_type.startswith("atlas.platform.bootstrap-state"):
            raise RuntimeError("audit unavailable")
        self.records.append(event)


class IdentityProvider:
    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        if authentication_input.authorization_scheme != "basic":
            return None
        return actor()


def actor(subject_id: str = "subject.development.operator") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name="Bootstrap Operator",
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
        "phase_ids": ("phase.acquire", "phase.configure", "phase.trust"),
    }
    values.update(overrides)
    return BootstrapRunIdentity(**values)  # type: ignore[arg-type]


def service(
    *, sink: AuditSink | None = None, clock: MutableClock | None = None
) -> tuple[BootstrapStateService, InMemoryBootstrapStateRepository, AuditSink, MutableClock]:
    resolved_sink = sink or AuditSink()
    resolved_clock = clock or MutableClock()
    repository = InMemoryBootstrapStateRepository()
    return (
        BootstrapStateService(
            repository=repository,
            environment_id="environment.test",
            site_id="site.local",
            audit_sink=resolved_sink,
            clock=resolved_clock,
        ),
        repository,
        resolved_sink,
        resolved_clock,
    )


async def claim(
    state_service: BootstrapStateService,
    *,
    claimant: AuthenticatedSubject | None = None,
    lease_holder_id: str = "session.bootstrap.primary",
    key: str = "bootstrap-claim-0001",
    run_identity: BootstrapRunIdentity | None = None,
) -> BootstrapMutationResult:
    return await state_service.claim(
        actor=claimant or actor(),
        lease_holder_id=lease_holder_id,
        identity=run_identity or identity(),
        lease_duration=timedelta(minutes=5),
        idempotency_key=key,
        correlation_id=f"correlation.{key}",
    )


@pytest.mark.asyncio
async def test_claim_is_idempotent_and_exposes_non_executing_state() -> None:
    state_service, _, sink, _ = service()
    first = await claim(state_service)
    replay = await claim(state_service)
    view = await state_service.current(
        actor=actor(),
        lease_holder_id="session.bootstrap.primary",
        correlation_id="correlation.read",
    )

    assert first.record.version == 1
    assert replay.record == first.record and replay.replayed is True
    assert view.record == first.record and view.durable is False
    assert view.lease_held_by_current_actor is True and view.lease_available is False
    assert view.execution_authorized is False
    assert view.infrastructure_mutation_authorized is False
    assert any(item.event_type == "atlas.platform.bootstrap-state.claim" for item in sink.records)


@pytest.mark.asyncio
async def test_concurrent_claim_has_one_winner_and_hides_foreign_owner() -> None:
    state_service, _, _, _ = service()
    results = await asyncio.gather(
        claim(state_service, lease_holder_id="session.operator.one", key="claim-one-0001"),
        claim(state_service, lease_holder_id="session.operator.two", key="claim-two-0001"),
        return_exceptions=True,
    )
    assert sum(not isinstance(item, BaseException) for item in results) == 1
    errors = [item for item in results if isinstance(item, BootstrapRepositoryError)]
    assert len(errors) == 1 and errors[0].code == "bootstrap_lease_unavailable"
    losing_holder = "session.operator.two"
    if not isinstance(results[1], BaseException):
        losing_holder = "session.operator.one"
    view = await state_service.current(
        actor=actor(),
        lease_holder_id=losing_holder,
        correlation_id="correlation.loser",
    )
    assert view.lease_held_by_current_actor is False and view.lease_available is False


@pytest.mark.asyncio
async def test_expired_lease_can_be_reclaimed_without_plan_substitution() -> None:
    state_service, _, _, clock = service()
    first = await claim(state_service, lease_holder_id="session.operator.one")
    clock.now = NOW + timedelta(minutes=6)
    reclaimed = await claim(
        state_service,
        lease_holder_id="session.operator.two",
        key="claim-reclaim-0001",
    )
    assert reclaimed.record.version == first.record.version + 1
    assert reclaimed.reclaimed_expired_lease is True

    clock.now += timedelta(minutes=6)
    with pytest.raises(BootstrapRepositoryError) as mismatch:
        await claim(
            state_service,
            lease_holder_id="session.operator.one",
            key="claim-mismatch-0001",
            run_identity=replace(identity(), plan_digest="c" * 64),
        )
    assert mismatch.value.code == "bootstrap_plan_mismatch"


@pytest.mark.asyncio
async def test_checkpoints_enforce_revision_order_and_safe_replay() -> None:
    state_service, _, _, _ = service()
    claimed = await claim(state_service)
    first = await state_service.checkpoint(
        actor=actor(),
        lease_holder_id="session.bootstrap.primary",
        run_id=claimed.record.run_id,
        plan_digest=identity().plan_digest,
        resume_key=identity().resume_key,
        phase_id="phase.acquire",
        state=BootstrapCheckpointState.COMPLETED,
        safe_output_references=("artifact.release-manifest-001",),
        expected_version=claimed.record.version,
        idempotency_key="checkpoint-acquire-0001",
        correlation_id="correlation.checkpoint.acquire",
    )
    replay = await state_service.checkpoint(
        actor=actor(),
        lease_holder_id="session.bootstrap.primary",
        run_id=claimed.record.run_id,
        plan_digest=identity().plan_digest,
        resume_key=identity().resume_key,
        phase_id="phase.acquire",
        state=BootstrapCheckpointState.COMPLETED,
        safe_output_references=("artifact.release-manifest-001",),
        expected_version=claimed.record.version,
        idempotency_key="checkpoint-acquire-0001",
        correlation_id="correlation.checkpoint.replay",
    )
    assert first.record.version == 2 and replay.replayed is True

    with pytest.raises(BootstrapRepositoryError) as stale:
        await state_service.checkpoint(
            actor=actor(),
            lease_holder_id="session.bootstrap.primary",
            run_id=claimed.record.run_id,
            plan_digest=identity().plan_digest,
            resume_key=identity().resume_key,
            phase_id="phase.configure",
            state=BootstrapCheckpointState.COMPLETED,
            safe_output_references=(),
            expected_version=1,
            idempotency_key="checkpoint-stale-0001",
            correlation_id="correlation.checkpoint.stale",
        )
    assert stale.value.code == "bootstrap_stale_revision"


@pytest.mark.asyncio
async def test_skipped_phase_secret_output_and_foreign_scope_fail_closed() -> None:
    state_service, _, sink, _ = service()
    claimed = await claim(state_service)
    with pytest.raises(BootstrapRepositoryError) as skipped:
        await state_service.checkpoint(
            actor=actor(),
            lease_holder_id="session.bootstrap.primary",
            run_id=claimed.record.run_id,
            plan_digest=identity().plan_digest,
            resume_key=identity().resume_key,
            phase_id="phase.configure",
            state=BootstrapCheckpointState.COMPLETED,
            safe_output_references=(),
            expected_version=1,
            idempotency_key="checkpoint-skipped-0001",
            correlation_id="correlation.checkpoint.skipped",
        )
    assert skipped.value.code == "bootstrap_dependency_unsatisfied"
    with pytest.raises(ValueError, match="opaque safe reference"):
        await state_service.checkpoint(
            actor=actor(),
            lease_holder_id="session.bootstrap.primary",
            run_id=claimed.record.run_id,
            plan_digest=identity().plan_digest,
            resume_key=identity().resume_key,
            phase_id="phase.acquire",
            state=BootstrapCheckpointState.COMPLETED,
            safe_output_references=("secret.database-password",),
            expected_version=1,
            idempotency_key="checkpoint-secret-0001",
            correlation_id="correlation.checkpoint.secret",
        )
    with pytest.raises(BootstrapStateScopeError):
        await claim(
            state_service,
            key="claim-foreign-0001",
            run_identity=replace(identity(), site_id="site.foreign"),
        )
    assert sink.records[-1].scope_reference == "scope.redacted"


@pytest.mark.asyncio
async def test_required_audit_failure_prevents_state_mutation() -> None:
    failing_sink = AuditSink(fail=True)
    state_service, repository, _, _ = service(sink=failing_sink)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await claim(state_service)
    assert (
        await repository.get_current(
            organization_id="organization.development",
            environment_id="environment.test",
            site_id="site.local",
        )
        is None
    )


@pytest.mark.asyncio
async def test_release_is_idempotent_and_blocks_checkpoint_without_active_lease() -> None:
    state_service, _, _, _ = service()
    claimed = await claim(state_service)
    released = await state_service.release(
        actor=actor(),
        lease_holder_id="session.bootstrap.primary",
        run_id=claimed.record.run_id,
        expected_version=1,
        idempotency_key="release-lease-0001",
        correlation_id="correlation.release",
    )
    replay = await state_service.release(
        actor=actor(),
        lease_holder_id="session.bootstrap.primary",
        run_id=claimed.record.run_id,
        expected_version=1,
        idempotency_key="release-lease-0001",
        correlation_id="correlation.release.replay",
    )
    view = await state_service.current(
        actor=actor(),
        lease_holder_id="session.bootstrap.primary",
        correlation_id="correlation.after-release",
    )
    assert released.record.version == 2 and replay.replayed is True
    assert view.lease_available is True and view.lease_held_by_current_actor is False
    with pytest.raises(BootstrapRepositoryError) as unavailable:
        await state_service.checkpoint(
            actor=actor(),
            lease_holder_id="session.bootstrap.primary",
            run_id=claimed.record.run_id,
            plan_digest=identity().plan_digest,
            resume_key=identity().resume_key,
            phase_id="phase.acquire",
            state=BootstrapCheckpointState.COMPLETED,
            safe_output_references=(),
            expected_version=2,
            idempotency_key="checkpoint-without-lease-0001",
            correlation_id="correlation.checkpoint.without-lease",
        )
    assert unavailable.value.code == "bootstrap_lease_unavailable"


def test_postgresql_mapping_and_schema_preserve_safe_state_contract() -> None:
    state_service, _, _, _ = service()
    assert state_service is not None
    table = Base.metadata.tables["platform_bootstrap_runs"]
    assert {"phase_ids", "checkpoints", "idempotency_records"}.issubset(table.columns.keys())
    assert len(table.primary_key.columns) == 1

    record = asyncio.run(_claimed_record())
    encoded = PostgreSQLBootstrapStateRepository._record_to_json(record)
    decoded = PostgreSQLBootstrapStateRepository._record_from_json(encoded)
    assert decoded == record
    assert "token" not in repr(encoded).lower() and "password" not in repr(encoded).lower()
    model = PostgreSQLBootstrapStateRepository._new_model(record)
    result = BootstrapMutationResult(
        record=replace(record, version=record.version + 1),
        replayed=False,
        preserved_checkpoint_phase_ids=("phase.acquire",),
        invalidated_checkpoint_phase_ids=("phase.configure",),
        invalidation_reason_codes=("bootstrap.configuration.changed",),
        earliest_affected_phase_id="phase.configure",
    )
    PostgreSQLBootstrapStateRepository._remember(
        model,
        "session.bootstrap.primary",
        "postgres-rebase-replay-0001",
        "f" * 64,
        result,
    )
    replay = PostgreSQLBootstrapStateRepository._replay(
        model,
        "session.bootstrap.primary",
        "postgres-rebase-replay-0001",
        "f" * 64,
    )
    assert replay is not None and replay.replayed is True
    assert replay.preserved_checkpoint_phase_ids == ("phase.acquire",)
    assert replay.invalidated_checkpoint_phase_ids == ("phase.configure",)


async def _claimed_record() -> BootstrapRunRecord:
    state_service, _, _, _ = service()
    return (await claim(state_service)).record


def claim_payload() -> dict[str, object]:
    return {
        "schema_version": "atlas.bootstrap-claim.v1",
        "release_id": identity().release_id,
        "profile": identity().profile.value,
        "organization_id": identity().organization_id,
        "environment_id": identity().environment_id,
        "site_id": identity().site_id,
        "plan_digest": identity().plan_digest,
        "resume_key": identity().resume_key,
        "configuration_digest": identity().configuration_digest,
        "phase_ids": list(identity().phase_ids),
        "lease_minutes": 5,
    }


def test_api_empty_state_csrf_mutation_and_owner_redaction() -> None:
    app = create_app(
        Settings(environment="test", development_identity_enabled=True),
        identity_provider=IdentityProvider(),
        audit_sink=AuditSink(),
    )
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/authentication/sessions",
            json={"username": "operator", "password": "valid-password"},
        )
        csrf = login.headers["X-CSRF-Token"]
        empty = client.get("/api/v1/platform/bootstrap-state/current")
        denied = client.post(
            "/api/v1/platform/bootstrap-state/claims",
            json=claim_payload(),
            headers={"Idempotency-Key": "api-claim-denied-0001"},
        )
        created = client.post(
            "/api/v1/platform/bootstrap-state/claims",
            json=claim_payload(),
            headers={
                "Idempotency-Key": "api-claim-created-0001",
                "X-CSRF-Token": csrf,
            },
        )
        current = client.get("/api/v1/platform/bootstrap-state/current")

    assert login.status_code == 201
    assert empty.status_code == 200 and empty.json()["data"]["run"] is None
    assert denied.status_code == 403 and denied.json()["code"] == "csrf_validation_failed"
    assert created.status_code == 201 and created.json()["data"]["run"]["version"] == 1
    assert current.status_code == 200 and current.json()["data"]["durable"] is False
    assert "lease_owner" not in created.text and "subject.development.operator" not in created.text
    assert created.json()["data"]["execution_authorized"] is False


def test_api_c0_read_supports_exact_scope_non_browser_identity() -> None:
    app = create_app(
        Settings(environment="test", development_identity_enabled=True), audit_sink=AuditSink()
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/platform/bootstrap-state/current")
    assert response.status_code == 200
    assert response.json()["data"] == {
        "run": None,
        "durable": False,
        "lease_available": True,
        "lease_held_by_current_actor": False,
        "execution_authorized": False,
        "infrastructure_mutation_authorized": False,
    }


async def checkpoint_phase(
    state_service: BootstrapStateService,
    run_id: str,
    version: int,
    phase_id: str,
    key: str,
) -> BootstrapMutationResult:
    return await state_service.checkpoint(
        actor=actor(),
        lease_holder_id="session.bootstrap.primary",
        run_id=run_id,
        plan_digest=identity().plan_digest,
        resume_key=identity().resume_key,
        phase_id=phase_id,
        state=BootstrapCheckpointState.COMPLETED,
        safe_output_references=(f"evidence.{phase_id}",),
        expected_version=version,
        idempotency_key=key,
        correlation_id=f"correlation.{key}",
    )


@pytest.mark.asyncio
async def test_rebase_preserves_only_safe_checkpoints_and_replays_exactly() -> None:
    state_service, repository, sink, _ = service()
    claimed = await claim(state_service)
    acquired = await checkpoint_phase(
        state_service, claimed.record.run_id, 1, "phase.acquire", "rebase-acquire-0001"
    )
    configured = await checkpoint_phase(
        state_service, claimed.record.run_id, 2, "phase.configure", "rebase-configure-0001"
    )
    candidate = replace(identity(), configuration_digest="d" * 64)

    rebased = await state_service.rebase(
        actor=actor(),
        lease_holder_id="session.bootstrap.primary",
        run_id=claimed.record.run_id,
        candidate=candidate,
        expected_version=configured.record.version,
        preview_source_version=configured.record.version,
        justification="Approved configuration correction for the lab deployment.",
        idempotency_key="rebase-config-change-0001",
        correlation_id="correlation.rebase.config",
    )
    replay = await state_service.rebase(
        actor=actor(),
        lease_holder_id="session.bootstrap.primary",
        run_id=claimed.record.run_id,
        candidate=candidate,
        expected_version=configured.record.version,
        preview_source_version=configured.record.version,
        justification="Approved configuration correction for the lab deployment.",
        idempotency_key="rebase-config-change-0001",
        correlation_id="correlation.rebase.replay",
    )

    assert rebased.record.version == 4
    assert rebased.record.identity == candidate
    assert rebased.record.completed_phase_ids == ("phase.acquire",)
    assert rebased.preserved_checkpoint_phase_ids == ("phase.acquire",)
    assert rebased.invalidated_checkpoint_phase_ids == ("phase.configure",)
    assert rebased.invalidation_reason_codes == ("bootstrap.configuration.changed",)
    assert rebased.earliest_affected_phase_id == "phase.configure"
    assert replay.replayed is True and replay.record == rebased.record
    current = await repository.get_current(
        organization_id=actor().organization_id,
        environment_id="environment.test",
        site_id="site.local",
    )
    assert current == rebased.record
    rebase_audit = next(item for item in sink.records if item.event_type.endswith(".rebase"))
    assert "Approved configuration" not in repr(rebase_audit)
    assert acquired.record.version == 2


@pytest.mark.asyncio
async def test_rebase_rejects_stale_unchanged_foreign_lease_and_changed_replay() -> None:
    state_service, _, _, _ = service()
    claimed = await claim(state_service)
    candidate = replace(identity(), plan_digest="d" * 64)

    for expected_code, kwargs in (
        ("bootstrap_stale_revision", {"expected_version": 2}),
        ("bootstrap_lease_unavailable", {"lease_holder_id": "session.bootstrap.other"}),
        ("bootstrap_plan_unchanged", {"candidate": identity()}),
    ):
        request = {
            "actor": actor(),
            "lease_holder_id": "session.bootstrap.primary",
            "run_id": claimed.record.run_id,
            "candidate": candidate,
            "expected_version": 1,
            "preview_source_version": 1,
            "justification": "Reviewed plan correction for deterministic resume safety.",
            "idempotency_key": f"rebase-reject-{expected_code}",
            "correlation_id": f"correlation.{expected_code}",
        }
        request.update(kwargs)
        with pytest.raises(BootstrapRepositoryError) as error:
            await state_service.rebase(**request)  # type: ignore[arg-type]
        assert error.value.code == expected_code

    first = await state_service.rebase(
        actor=actor(),
        lease_holder_id="session.bootstrap.primary",
        run_id=claimed.record.run_id,
        candidate=candidate,
        expected_version=1,
        preview_source_version=1,
        justification="Reviewed plan correction for deterministic resume safety.",
        idempotency_key="rebase-conflict-0001",
        correlation_id="correlation.rebase.first",
    )
    assert first.record.version == 2
    with pytest.raises(BootstrapRepositoryError) as conflict:
        await state_service.rebase(
            actor=actor(),
            lease_holder_id="session.bootstrap.primary",
            run_id=claimed.record.run_id,
            candidate=replace(candidate, configuration_digest="e" * 64),
            expected_version=1,
            preview_source_version=1,
            justification="Reviewed plan correction for deterministic resume safety.",
            idempotency_key="rebase-conflict-0001",
            correlation_id="correlation.rebase.conflict",
        )
    assert conflict.value.code == "bootstrap_idempotency_conflict"


@pytest.mark.asyncio
async def test_completed_run_and_required_audit_block_rebase_without_mutation() -> None:
    state_service, _, _, _ = service()
    claimed = await claim(state_service)
    version = claimed.record.version
    for index, phase_id in enumerate(identity().phase_ids):
        completed = await checkpoint_phase(
            state_service, claimed.record.run_id, version, phase_id, f"complete-{index}-0001"
        )
        version = completed.record.version
    with pytest.raises(BootstrapRepositoryError) as completed_error:
        await state_service.rebase(
            actor=actor(),
            lease_holder_id="session.bootstrap.primary",
            run_id=claimed.record.run_id,
            candidate=replace(identity(), plan_digest="f" * 64),
            expected_version=version,
            preview_source_version=version,
            justification="Reviewed replacement plan after completed deployment state.",
            idempotency_key="rebase-completed-0001",
            correlation_id="correlation.rebase.completed",
        )
    assert completed_error.value.code == "bootstrap_run_completed"

    failing_service, failing_repository, _, _ = service(sink=AuditSink(fail=True))
    failing_claim = await failing_repository.claim(
        identity=identity(),
        lease_holder_id="session.bootstrap.primary",
        lease_duration=timedelta(minutes=5),
        idempotency_key="seed-audit-rebase-0001",
        request_fingerprint="f" * 64,
        now=NOW,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await failing_service.rebase(
            actor=actor(),
            lease_holder_id="session.bootstrap.primary",
            run_id=failing_claim.record.run_id,
            candidate=replace(identity(), plan_digest="e" * 64),
            expected_version=1,
            preview_source_version=1,
            justification="Reviewed plan correction while required audit is unavailable.",
            idempotency_key="rebase-audit-fail-0001",
            correlation_id="correlation.rebase.audit-fail",
        )
    unchanged = await failing_repository.get_current(
        organization_id=actor().organization_id,
        environment_id="environment.test",
        site_id="site.local",
    )
    assert unchanged == failing_claim.record


def rebase_payload(version: int, **overrides: object) -> dict[str, object]:
    values = claim_payload()
    values.pop("lease_minutes")
    values.update(
        {
            "schema_version": "atlas.bootstrap-rebase.v1",
            "configuration_digest": "d" * 64,
            "expected_version": version,
            "preview_source_version": version,
            "justification": "Approved configuration correction for deterministic resume safety.",
        }
    )
    values.update(overrides)
    return values


def test_api_rebase_requires_csrf_strict_input_and_returns_safe_metadata() -> None:
    app = create_app(
        Settings(environment="test", development_identity_enabled=True),
        identity_provider=IdentityProvider(),
        audit_sink=AuditSink(),
    )
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/authentication/sessions",
            json={"username": "operator", "password": "valid-password"},
        )
        csrf = login.headers["X-CSRF-Token"]
        created = client.post(
            "/api/v1/platform/bootstrap-state/claims",
            json=claim_payload(),
            headers={"Idempotency-Key": "api-rebase-claim-0001", "X-CSRF-Token": csrf},
        )
        run_id = created.json()["data"]["run"]["run_id"]
        denied = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/rebase",
            json=rebase_payload(1),
            headers={"Idempotency-Key": "api-rebase-denied-0001"},
        )
        malformed = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/rebase",
            json=rebase_payload(1, unknown="unsafe"),
            headers={"Idempotency-Key": "api-rebase-malformed-0001", "X-CSRF-Token": csrf},
        )
        rebased = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/rebase",
            json=rebase_payload(1),
            headers={"Idempotency-Key": "api-rebase-created-0001", "X-CSRF-Token": csrf},
        )
        current = client.get("/api/v1/platform/bootstrap-state/current")

    assert denied.status_code == 403 and denied.json()["code"] == "csrf_validation_failed"
    assert malformed.status_code == 422
    assert rebased.status_code == 200 and rebased.headers["cache-control"] == "no-store"
    data = rebased.json()["data"]
    assert data["run"]["version"] == 2
    assert data["earliest_affected_phase_id"] == "phase.configure"
    assert data["invalidation_reason_codes"] == ["bootstrap.configuration.changed"]
    assert data["execution_authorized"] is False
    assert data["infrastructure_mutation_authorized"] is False
    assert "lease_holder" not in rebased.text and "justification" not in rebased.text
    assert current.json()["data"]["run"]["version"] == 2
