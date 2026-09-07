from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.identity.adapters.local_credentials import InMemoryLocalCredentialRepository
from atlas.modules.identity.application.composite import CompositeIdentityProvider
from atlas.modules.identity.application.local_credentials import (
    BOOTSTRAP_SETUP_ROLE_ID,
    LocalCredentialError,
    LocalCredentialIdentityProvider,
    LocalCredentialService,
)
from atlas.modules.identity.domain.local_credentials import (
    DEFAULT_LOCAL_CREDENTIAL_LOCKOUT_POLICY,
    LocalCredentialLockoutPolicy,
    LocalCredentialState,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, delta: timedelta) -> None:
        self.moment += delta


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service(
    *,
    lockout_policy: LocalCredentialLockoutPolicy = DEFAULT_LOCAL_CREDENTIAL_LOCKOUT_POLICY,
    clock: MutableClock | None = None,
) -> tuple[LocalCredentialService, CollectingAuditSink, MutableClock]:
    resolved_clock = clock or MutableClock(NOW)
    audit_sink = CollectingAuditSink()
    service = LocalCredentialService(
        repository=InMemoryLocalCredentialRepository(),
        audit_sink=audit_sink,
        lockout_policy=lockout_policy,
        clock=resolved_clock,
    )
    return service, audit_sink, resolved_clock


async def _bootstrap(service: LocalCredentialService) -> None:
    await service.bootstrap_administrator(
        subject_id="subject.bootstrap-administrator.primary",
        organization_id="organization.atlas.local",
        display_name="Bootstrap Administrator",
        role_ids=("role.platform-administrator",),
        password="atlas-test-fixture-password-bootstrap-1",
        deployment_ownership_verified=True,
        correlation_id="correlation.test",
    )


@pytest.mark.asyncio
async def test_bootstrap_requires_deployment_ownership_verification() -> None:
    service, _audit, _clock = _service()
    with pytest.raises(LocalCredentialError, match="local_bootstrap_ownership_unverified"):
        await service.bootstrap_administrator(
            subject_id="subject.bootstrap-administrator.primary",
            organization_id="organization.atlas.local",
            display_name="Bootstrap Administrator",
            role_ids=("role.platform-administrator",),
            password="atlas-test-fixture-password-bootstrap-1",
            deployment_ownership_verified=False,
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_bootstrap_creates_a_must_replace_credential() -> None:
    service, audit_sink, _clock = _service()
    record = await service.bootstrap_administrator(
        subject_id="subject.bootstrap-administrator.primary",
        organization_id="organization.atlas.local",
        display_name="Bootstrap Administrator",
        role_ids=("role.platform-administrator",),
        password="atlas-test-fixture-password-bootstrap-1",
        deployment_ownership_verified=True,
        correlation_id="correlation.test",
    )
    assert record.state is LocalCredentialState.MUST_REPLACE
    assert any(item.result_code == "local_credential_created" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_bootstrap_is_not_reusable_for_the_same_subject() -> None:
    service, _audit, _clock = _service()
    await _bootstrap(service)
    with pytest.raises(LocalCredentialError, match="local_credential_already_exists"):
        await _bootstrap(service)


@pytest.mark.asyncio
async def test_authenticate_while_must_replace_is_restricted_to_bootstrap_setup_scope() -> None:
    service, _audit, _clock = _service()
    await _bootstrap(service)
    subject = await service.authenticate(
        subject_id="subject.bootstrap-administrator.primary",
        password="atlas-test-fixture-password-bootstrap-1",
        correlation_id="correlation.test",
    )
    assert subject is not None
    assert subject.role_ids == (BOOTSTRAP_SETUP_ROLE_ID,)
    assert subject.authentication_method is AuthenticationMethod.LOCAL


@pytest.mark.asyncio
async def test_authenticate_after_replacement_uses_the_real_role_grants() -> None:
    service, _audit, _clock = _service()
    await _bootstrap(service)
    await service.replace_credential(
        subject_id="subject.bootstrap-administrator.primary",
        current_password="atlas-test-fixture-password-bootstrap-1",
        new_password="atlas-test-fixture-password-replaced-2",
        correlation_id="correlation.test",
    )
    subject = await service.authenticate(
        subject_id="subject.bootstrap-administrator.primary",
        password="atlas-test-fixture-password-replaced-2",
        correlation_id="correlation.test",
    )
    assert subject is not None
    assert subject.role_ids == ("role.platform-administrator",)


@pytest.mark.asyncio
async def test_authenticate_rejects_an_unknown_subject_with_the_generic_denial_code() -> None:
    service, audit_sink, _clock = _service()
    subject = await service.authenticate(
        subject_id="subject.no-such-account", password="anything", correlation_id="correlation.x"
    )
    assert subject is None
    denials = [item for item in audit_sink.records if item.outcome == "denied"]
    assert denials[-1].result_code == "local_credential_invalid"


@pytest.mark.asyncio
async def test_authenticate_rejects_a_wrong_password_with_the_same_generic_denial_code() -> None:
    service, audit_sink, _clock = _service()
    await _bootstrap(service)
    subject = await service.authenticate(
        subject_id="subject.bootstrap-administrator.primary",
        password="wrong-password",
        correlation_id="correlation.x",
    )
    assert subject is None
    denials = [item for item in audit_sink.records if item.outcome == "denied"]
    assert denials[-1].result_code == "local_credential_invalid"


@pytest.mark.asyncio
async def test_repeated_failures_lock_the_credential_and_emit_a_distinct_audit_event() -> None:
    policy = LocalCredentialLockoutPolicy(
        max_failed_attempts=3, lockout_duration=timedelta(minutes=15)
    )
    service, audit_sink, clock = _service(lockout_policy=policy)
    await _bootstrap(service)
    for _ in range(3):
        assert (
            await service.authenticate(
                subject_id="subject.bootstrap-administrator.primary",
                password="wrong-password",
                correlation_id="correlation.x",
            )
            is None
        )
    assert any(item.result_code == "local_credential_lockout" for item in audit_sink.records)
    locked = await service.authenticate(
        subject_id="subject.bootstrap-administrator.primary",
        password="atlas-test-fixture-password-bootstrap-1",
        correlation_id="correlation.x",
    )
    assert locked is None
    clock.advance(timedelta(minutes=16))
    unlocked = await service.authenticate(
        subject_id="subject.bootstrap-administrator.primary",
        password="atlas-test-fixture-password-bootstrap-1",
        correlation_id="correlation.x",
    )
    assert unlocked is not None


@pytest.mark.asyncio
async def test_disabled_credential_never_authenticates() -> None:
    service, _audit, _clock = _service()
    await _bootstrap(service)
    await service.disable(
        subject_id="subject.bootstrap-administrator.primary",
        disabled_by="subject.security-administrator",
        reason="Enterprise directory verified; sealing bootstrap material.",
        correlation_id="correlation.x",
    )
    subject = await service.authenticate(
        subject_id="subject.bootstrap-administrator.primary",
        password="atlas-test-fixture-password-bootstrap-1",
        correlation_id="correlation.x",
    )
    assert subject is None


@pytest.mark.asyncio
async def test_disable_requires_a_reason_and_rejects_a_second_disablement() -> None:
    service, _audit, _clock = _service()
    await _bootstrap(service)
    with pytest.raises(LocalCredentialError, match="local_credential_disable_reason_required"):
        await service.disable(
            subject_id="subject.bootstrap-administrator.primary",
            disabled_by="subject.security-administrator",
            reason="   ",
            correlation_id="correlation.x",
        )
    await service.disable(
        subject_id="subject.bootstrap-administrator.primary",
        disabled_by="subject.security-administrator",
        reason="Sealing unused bootstrap material.",
        correlation_id="correlation.x",
    )
    with pytest.raises(LocalCredentialError, match="local_credential_already_disabled"):
        await service.disable(
            subject_id="subject.bootstrap-administrator.primary",
            disabled_by="subject.security-administrator",
            reason="Sealing again.",
            correlation_id="correlation.x",
        )


@pytest.mark.asyncio
async def test_replace_credential_rejects_wrong_current_password() -> None:
    service, _audit, _clock = _service()
    await _bootstrap(service)
    with pytest.raises(LocalCredentialError, match="local_credential_invalid"):
        await service.replace_credential(
            subject_id="subject.bootstrap-administrator.primary",
            current_password="wrong-password",
            new_password="atlas-test-fixture-password-replaced-2",
            correlation_id="correlation.x",
        )


@pytest.mark.asyncio
async def test_replace_credential_rejects_reusing_the_same_password() -> None:
    service, _audit, _clock = _service()
    await _bootstrap(service)
    with pytest.raises(LocalCredentialError, match="local_credential_reuse_denied"):
        await service.replace_credential(
            subject_id="subject.bootstrap-administrator.primary",
            current_password="atlas-test-fixture-password-bootstrap-1",
            new_password="atlas-test-fixture-password-bootstrap-1",
            correlation_id="correlation.x",
        )


@pytest.mark.asyncio
async def test_recovery_credential_cannot_authenticate_without_an_active_activation() -> None:
    service, _audit, _clock = _service()
    await service.create_recovery_credential(
        subject_id="subject.recovery.primary",
        organization_id="organization.atlas.local",
        display_name="Recovery Administrator",
        role_ids=("role.platform-administrator",),
        password="atlas-test-fixture-password-recovery-3",
        correlation_id="correlation.x",
    )
    subject = await service.authenticate(
        subject_id="subject.recovery.primary",
        password="atlas-test-fixture-password-recovery-3",
        correlation_id="correlation.x",
    )
    assert subject is None


@pytest.mark.asyncio
async def test_recovery_activation_permits_authentication_within_the_window_only() -> None:
    service, audit_sink, clock = _service()
    await service.create_recovery_credential(
        subject_id="subject.recovery.primary",
        organization_id="organization.atlas.local",
        display_name="Recovery Administrator",
        role_ids=("role.platform-administrator",),
        password="atlas-test-fixture-password-recovery-3",
        correlation_id="correlation.x",
    )
    await service.activate_recovery(
        subject_id="subject.recovery.primary",
        justification="Production incident INC-1234; directory outage.",
        activated_by="subject.security-administrator",
        ttl=timedelta(hours=1),
        correlation_id="correlation.x",
    )
    assert any(item.result_code == "local_recovery_activated" for item in audit_sink.records)
    subject = await service.authenticate(
        subject_id="subject.recovery.primary",
        password="atlas-test-fixture-password-recovery-3",
        correlation_id="correlation.x",
    )
    assert subject is not None
    assert any(item.result_code == "local_recovery_used" for item in audit_sink.records)
    clock.advance(timedelta(hours=2))
    expired = await service.authenticate(
        subject_id="subject.recovery.primary",
        password="atlas-test-fixture-password-recovery-3",
        correlation_id="correlation.x",
    )
    assert expired is None


@pytest.mark.asyncio
async def test_activate_recovery_rejects_an_overlapping_window() -> None:
    service, _audit, _clock = _service()
    await service.create_recovery_credential(
        subject_id="subject.recovery.primary",
        organization_id="organization.atlas.local",
        display_name="Recovery Administrator",
        role_ids=("role.platform-administrator",),
        password="atlas-test-fixture-password-recovery-3",
        correlation_id="correlation.x",
    )
    await service.activate_recovery(
        subject_id="subject.recovery.primary",
        justification="Production incident INC-1234.",
        activated_by="subject.security-administrator",
        ttl=timedelta(hours=1),
        correlation_id="correlation.x",
    )
    with pytest.raises(LocalCredentialError, match="local_recovery_already_active"):
        await service.activate_recovery(
            subject_id="subject.recovery.primary",
            justification="A second, overlapping justification.",
            activated_by="subject.security-administrator",
            ttl=timedelta(hours=1),
            correlation_id="correlation.x",
        )


@pytest.mark.asyncio
async def test_review_recovery_requires_a_prior_use_and_only_happens_once() -> None:
    service, audit_sink, _clock = _service()
    await service.create_recovery_credential(
        subject_id="subject.recovery.primary",
        organization_id="organization.atlas.local",
        display_name="Recovery Administrator",
        role_ids=("role.platform-administrator",),
        password="atlas-test-fixture-password-recovery-3",
        correlation_id="correlation.x",
    )
    with pytest.raises(LocalCredentialError, match="local_recovery_review_unavailable"):
        await service.review_recovery(
            subject_id="subject.recovery.primary",
            reviewed_by="subject.security-administrator",
            notes="premature",
            correlation_id="correlation.x",
        )
    await service.activate_recovery(
        subject_id="subject.recovery.primary",
        justification="Production incident INC-1234.",
        activated_by="subject.security-administrator",
        ttl=timedelta(hours=1),
        correlation_id="correlation.x",
    )
    await service.authenticate(
        subject_id="subject.recovery.primary",
        password="atlas-test-fixture-password-recovery-3",
        correlation_id="correlation.x",
    )
    reviewed = await service.review_recovery(
        subject_id="subject.recovery.primary",
        reviewed_by="subject.security-administrator",
        notes="Confirmed legitimate incident response.",
        correlation_id="correlation.x",
    )
    assert reviewed.reviewed_by == "subject.security-administrator"
    assert any(item.result_code == "local_recovery_reviewed" for item in audit_sink.records)
    with pytest.raises(LocalCredentialError, match="local_recovery_already_reviewed"):
        await service.review_recovery(
            subject_id="subject.recovery.primary",
            reviewed_by="subject.security-administrator",
            notes="again",
            correlation_id="correlation.x",
        )


def _basic_auth_input(username: str, password: str) -> AuthenticationInput:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return AuthenticationInput(
        correlation_id="correlation.provider", authorization_scheme="basic", credential=token
    )


@pytest.mark.asyncio
async def test_provider_decodes_basic_auth_and_delegates_to_the_service() -> None:
    service, _audit, _clock = _service()
    await _bootstrap(service)
    provider = LocalCredentialIdentityProvider(service)
    subject = await provider.authenticate(
        _basic_auth_input(
            "subject.bootstrap-administrator.primary", "atlas-test-fixture-password-bootstrap-1"
        )
    )
    assert subject is not None
    assert subject.subject_id == "subject.bootstrap-administrator.primary"


@pytest.mark.asyncio
async def test_provider_rejects_non_basic_or_missing_credentials() -> None:
    service, _audit, _clock = _service()
    provider = LocalCredentialIdentityProvider(service)
    assert (
        await provider.authenticate(AuthenticationInput(correlation_id="correlation.provider"))
        is None
    )
    assert (
        await provider.authenticate(
            AuthenticationInput(
                correlation_id="correlation.provider",
                authorization_scheme="bearer",
                credential="token",
            )
        )
        is None
    )


_FALLBACK_SUBJECT = AuthenticatedSubject(
    subject_id="subject.fallback.provider",
    display_name="Fallback Provider Subject",
    kind=SubjectKind.HUMAN,
    provider_id="provider.fallback.test",
    authentication_method=AuthenticationMethod.DEVELOPMENT,
    assurance_level=AssuranceLevel.DEVELOPMENT,
    authenticated_at=NOW,
    organization_id="organization.atlas.local",
    role_ids=("role.fallback",),
)


class StubProvider:
    def __init__(self, result: AuthenticatedSubject | None) -> None:
        self._result = result
        self.calls = 0

    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        self.calls += 1
        return self._result


@pytest.mark.asyncio
async def test_composite_provider_falls_through_to_the_next_provider() -> None:
    service, _audit, _clock = _service()
    local_provider = LocalCredentialIdentityProvider(service)
    fallback = StubProvider(result=_FALLBACK_SUBJECT)
    composite = CompositeIdentityProvider((local_provider, fallback))
    result = await composite.authenticate(
        AuthenticationInput(correlation_id="correlation.composite")
    )
    assert result is not None
    assert result.subject_id == _FALLBACK_SUBJECT.subject_id
    assert fallback.calls == 1


@pytest.mark.asyncio
async def test_composite_provider_prefers_the_first_matching_provider() -> None:
    service, _audit, _clock = _service()
    await _bootstrap(service)
    local_provider = LocalCredentialIdentityProvider(service)
    fallback = StubProvider(result=_FALLBACK_SUBJECT)
    composite = CompositeIdentityProvider((local_provider, fallback))
    result = await composite.authenticate(
        _basic_auth_input(
            "subject.bootstrap-administrator.primary", "atlas-test-fixture-password-bootstrap-1"
        )
    )
    assert result is not None
    assert result.subject_id != _FALLBACK_SUBJECT.subject_id
    assert fallback.calls == 0


def test_composite_provider_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="at least one provider"):
        CompositeIdentityProvider(())
