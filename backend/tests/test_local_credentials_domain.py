from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.identity.domain.local_credentials import (
    LocalCredentialKind,
    LocalCredentialLockoutPolicy,
    LocalCredentialRecord,
    LocalCredentialState,
    LocalRecoveryActivation,
    a_local_credential_authenticates_while_its_lockout_window_has_not_yet_elapsed,
    a_recovery_activation_is_granted_without_a_documented_justification_or_time_bound_expiry,
    hash_local_password,
    verify_local_password,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _record(**overrides: object) -> LocalCredentialRecord:
    values: dict[object, object] = {
        "subject_id": "subject.bootstrap-administrator.primary",
        "kind": LocalCredentialKind.BOOTSTRAP_ADMINISTRATOR,
        "organization_id": "organization.atlas.local",
        "display_name": "Bootstrap Administrator",
        "role_ids": ("role.platform-administrator",),
        "password_hash": hash_local_password("atlas-test-fixture-password-bootstrap-1"),
        "state": LocalCredentialState.MUST_REPLACE,
        "version": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return LocalCredentialRecord(**values)  # type: ignore[arg-type]


def test_absolute_rules_are_false() -> None:
    assert (
        a_recovery_activation_is_granted_without_a_documented_justification_or_time_bound_expiry()
        is False
    )
    assert a_local_credential_authenticates_while_its_lockout_window_has_not_yet_elapsed() is False


def test_password_hash_verifies_correctly() -> None:
    encoded = hash_local_password("atlas-test-fixture-password-bootstrap-1")
    assert encoded.startswith("scrypt$")
    assert verify_local_password("atlas-test-fixture-password-bootstrap-1", encoded) is True
    assert verify_local_password("wrong-password", encoded) is False


def test_password_hash_is_salted_differently_each_time() -> None:
    first = hash_local_password("same-password-value-1")
    second = hash_local_password("same-password-value-1")
    assert first != second
    assert verify_local_password("same-password-value-1", first) is True
    assert verify_local_password("same-password-value-1", second) is True


def test_verify_rejects_malformed_encodings() -> None:
    assert verify_local_password("anything", "not-a-scrypt-encoding") is False
    assert verify_local_password("anything", "scrypt$1$2$3$not-base64!!$also-not") is False


def test_verify_rejects_tampered_parameters() -> None:
    encoded = hash_local_password("atlas-test-fixture-password-bootstrap-1")
    prefix, _n, r, p, salt, digest = encoded.split("$")
    tampered = "$".join((prefix, "99", r, p, salt, digest))
    assert verify_local_password("atlas-test-fixture-password-bootstrap-1", tampered) is False


def test_empty_password_is_rejected() -> None:
    with pytest.raises(ValueError, match="outside platform bounds"):
        hash_local_password("")


def test_lockout_policy_bounds() -> None:
    with pytest.raises(ValueError, match="max attempts"):
        LocalCredentialLockoutPolicy(max_failed_attempts=0, lockout_duration=timedelta(minutes=1))
    with pytest.raises(ValueError, match="lockout duration"):
        LocalCredentialLockoutPolicy(max_failed_attempts=5, lockout_duration=timedelta(days=2))


def test_record_requires_at_least_one_role() -> None:
    with pytest.raises(ValueError, match="at least one role"):
        _record(role_ids=())


def test_record_requires_non_empty_display_name() -> None:
    with pytest.raises(ValueError, match="display_name"):
        _record(display_name="  ")


def test_locked_state_requires_lockout_expiry() -> None:
    with pytest.raises(ValueError, match="lockout expiry"):
        _record(state=LocalCredentialState.LOCKED, locked_until=None)


def test_non_locked_state_forbids_lockout_expiry() -> None:
    with pytest.raises(ValueError, match="only a locked"):
        _record(state=LocalCredentialState.ACTIVE, locked_until=NOW + timedelta(minutes=5))


def test_disabled_state_requires_complete_disablement_data() -> None:
    with pytest.raises(ValueError, match="disablement data"):
        _record(state=LocalCredentialState.DISABLED)


def test_active_state_forbids_disablement_data() -> None:
    with pytest.raises(ValueError, match="only a disabled"):
        _record(
            state=LocalCredentialState.ACTIVE,
            disabled_at=NOW,
            disabled_by="subject.reviewer",
            disable_reason="test",
        )


def test_recovery_activation_requires_justification() -> None:
    with pytest.raises(ValueError, match="documented justification"):
        LocalRecoveryActivation(
            activation_id="activation.abc123",
            subject_id="subject.recovery.primary",
            justification="   ",
            activated_by="subject.reviewer",
            activated_at=NOW,
            expires_at=NOW + timedelta(hours=1),
        )


def test_recovery_activation_must_be_time_bound() -> None:
    with pytest.raises(ValueError, match="time-bound"):
        LocalRecoveryActivation(
            activation_id="activation.abc123",
            subject_id="subject.recovery.primary",
            justification="Production incident INC-1234.",
            activated_by="subject.reviewer",
            activated_at=NOW,
            expires_at=NOW + timedelta(hours=48),
        )


def test_recovery_activation_must_expire_after_it_starts() -> None:
    with pytest.raises(ValueError, match="expire after"):
        LocalRecoveryActivation(
            activation_id="activation.abc123",
            subject_id="subject.recovery.primary",
            justification="Production incident INC-1234.",
            activated_by="subject.reviewer",
            activated_at=NOW,
            expires_at=NOW,
        )


def test_recovery_activation_review_requires_reviewer_and_use() -> None:
    with pytest.raises(ValueError, match="reviewer and a time"):
        LocalRecoveryActivation(
            activation_id="activation.abc123",
            subject_id="subject.recovery.primary",
            justification="Production incident INC-1234.",
            activated_by="subject.reviewer",
            activated_at=NOW,
            expires_at=NOW + timedelta(hours=1),
            reviewed_at=NOW + timedelta(minutes=30),
        )
    with pytest.raises(ValueError, match="recorded use"):
        LocalRecoveryActivation(
            activation_id="activation.abc123",
            subject_id="subject.recovery.primary",
            justification="Production incident INC-1234.",
            activated_by="subject.reviewer",
            activated_at=NOW,
            expires_at=NOW + timedelta(hours=1),
            reviewed_at=NOW + timedelta(minutes=30),
            reviewed_by="subject.reviewer",
        )


def test_is_active_at_bounds() -> None:
    activation = LocalRecoveryActivation(
        activation_id="activation.abc123",
        subject_id="subject.recovery.primary",
        justification="Production incident INC-1234.",
        activated_by="subject.reviewer",
        activated_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    assert activation.is_active_at(NOW) is True
    assert activation.is_active_at(NOW + timedelta(minutes=30)) is True
    assert activation.is_active_at(NOW + timedelta(hours=1)) is False
    assert activation.is_active_at(NOW - timedelta(seconds=1)) is False
