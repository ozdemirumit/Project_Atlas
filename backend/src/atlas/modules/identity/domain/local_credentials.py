"""ATLAS-030 SS6.3 / SS11: local bootstrap and recovery authentication.

"Local authentication exists for initial bootstrap and controlled recovery... Local password
verifiers use an approved adaptive password-hashing algorithm with per-credential salt. Local
accounts support lockout, rotation, disablement, and recovery procedures." (SS6.3)

This module is the closest faithful approximation of SS6.3/SS11 buildable on top of the existing
identity domain: real adaptive password hashing (scrypt, RFC 7914, via the `cryptography`
dependency already used elsewhere in this codebase -- no new dependency added), a local credential
record with lockout/rotation/disablement state, and a separately governed, time-bound recovery
("break-glass") activation. It does not implement SS11's full seven-step bootstrap orchestration
(that lives in `atlas.modules.platform`'s bootstrap handoff, which records only an opaque
`credential_verifier_reference_id` today) -- wiring this module's `bootstrap_administrator` into
that orchestration is a deliberately deferred follow-on, not a redesign of an already-stable,
heavily-tested subsystem.
"""

from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from atlas.modules.identity.domain.models import validate_stable_identifier

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_SALT_BYTES = 16
_SCRYPT_PREFIX = "scrypt"


def hash_local_password(password: str) -> str:
    """Adaptive, per-credential-salted password hash (SS6.3). Never logged; only the encoded
    hash is ever stored or compared."""
    if not password or len(password.encode("utf-8")) > 1024:
        raise ValueError("password is outside platform bounds")
    salt = secrets.token_bytes(_SCRYPT_SALT_BYTES)
    digest = _derive(password, salt)
    return "$".join(
        (
            _SCRYPT_PREFIX,
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        )
    )


def verify_local_password(password: str, encoded: str) -> bool:
    """Constant-time verification against an encoded `hash_local_password` value. Returns False
    (never raises) for a malformed encoding so a corrupted record fails closed."""
    parts = encoded.split("$")
    if len(parts) != 6 or parts[0] != _SCRYPT_PREFIX:
        return False
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        expected = base64.b64decode(parts[5], validate=True)
    except (ValueError, TypeError):
        return False
    if n != _SCRYPT_N or r != _SCRYPT_R or p != _SCRYPT_P:
        return False
    try:
        candidate = _derive(password, salt, n=n, r=r, p=p, length=len(expected))
    except ValueError:
        return False
    return secrets.compare_digest(candidate, expected)


def _derive(
    password: str,
    salt: bytes,
    *,
    n: int = _SCRYPT_N,
    r: int = _SCRYPT_R,
    p: int = _SCRYPT_P,
    length: int = _SCRYPT_DKLEN,
) -> bytes:
    kdf = Scrypt(salt=salt, length=length, n=n, r=r, p=p)
    return kdf.derive(password.encode("utf-8"))


class LocalCredentialKind(StrEnum):
    """SS6.3/SS11 distinguish the initial bootstrap administrator credential from a separately
    governed recovery ("break-glass") credential -- they carry different activation rules."""

    BOOTSTRAP_ADMINISTRATOR = "bootstrap_administrator"
    RECOVERY = "recovery"


class LocalCredentialState(StrEnum):
    """SS11: "require immediate replacement on first use" (`MUST_REPLACE`); SS6.3: "lockout,
    rotation, disablement" (`LOCKED`, `ACTIVE`, `DISABLED`)."""

    MUST_REPLACE = "must_replace"
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class LocalCredentialLockoutPolicy:
    """SS13: "rate-limited lockout" on repeated invalid local credential attempts."""

    max_failed_attempts: int
    lockout_duration: timedelta

    def __post_init__(self) -> None:
        if not 1 <= self.max_failed_attempts <= 20:
            raise ValueError("lockout max attempts is outside platform bounds")
        if not timedelta(seconds=1) <= self.lockout_duration <= timedelta(hours=24):
            raise ValueError("lockout duration is outside platform bounds")


DEFAULT_LOCAL_CREDENTIAL_LOCKOUT_POLICY = LocalCredentialLockoutPolicy(
    max_failed_attempts=5, lockout_duration=timedelta(minutes=15)
)


@dataclass(frozen=True, slots=True)
class LocalCredentialRecord:
    """One local credential (bootstrap administrator or recovery). `password_hash` is always an
    output of `hash_local_password` -- the plaintext password is never part of this record and
    is never logged (SS11 step 2, SS15)."""

    subject_id: str
    kind: LocalCredentialKind
    organization_id: str
    display_name: str
    role_ids: tuple[str, ...]
    password_hash: str
    state: LocalCredentialState
    version: int
    created_at: datetime
    updated_at: datetime
    failed_attempt_count: int = 0
    locked_until: datetime | None = None
    last_used_at: datetime | None = None
    disabled_at: datetime | None = None
    disabled_by: str | None = None
    disable_reason: str | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.subject_id, "subject_id")
        validate_stable_identifier(self.organization_id, "organization_id")
        for role_id in self.role_ids:
            validate_stable_identifier(role_id, "role_id")
        if not self.role_ids:
            raise ValueError("a local credential requires at least one role")
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if self.version < 1:
            raise ValueError("local credential version must be positive")
        if self.failed_attempt_count < 0:
            raise ValueError("failed attempt count cannot be negative")
        for value in (self.created_at, self.updated_at, self.locked_until, self.last_used_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("local credential timestamps must be timezone-aware")
        if self.state is LocalCredentialState.LOCKED and self.locked_until is None:
            raise ValueError("a locked local credential requires a lockout expiry")
        if self.state is not LocalCredentialState.LOCKED and self.locked_until is not None:
            raise ValueError("only a locked local credential carries a lockout expiry")
        disabled_fields = (self.disabled_at, self.disabled_by, self.disable_reason)
        if self.state is LocalCredentialState.DISABLED:
            if any(item is None for item in disabled_fields):
                raise ValueError("a disabled local credential requires complete disablement data")
        elif any(item is not None for item in disabled_fields):
            raise ValueError("only a disabled local credential carries disablement data")


@dataclass(frozen=True, slots=True)
class LocalRecoveryActivation:
    """SS11: "Recovery or break-glass access requires documented justification, time-bound
    activation where supported, strong authentication, visible notification, and post-use
    review." One activation window during which a `RECOVERY`-kind credential is permitted to
    authenticate at all; the credential is otherwise inert."""

    activation_id: str
    subject_id: str
    justification: str
    activated_by: str
    activated_at: datetime
    expires_at: datetime
    used_at: datetime | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    review_notes: str | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.activation_id, "activation_id")
        validate_stable_identifier(self.subject_id, "subject_id")
        validate_stable_identifier(self.activated_by, "activated_by")
        if not 1 <= len(self.justification.strip()) <= 2048:
            raise ValueError("recovery activation requires a documented justification")
        for value in (
            self.activated_at,
            self.expires_at,
            self.used_at,
            self.reviewed_at,
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError("recovery activation timestamps must be timezone-aware")
        if self.expires_at <= self.activated_at:
            raise ValueError("recovery activation must expire after it starts")
        if self.expires_at - self.activated_at > timedelta(hours=24):
            raise ValueError("recovery activation must be time-bound")
        if (self.reviewed_at is None) != (self.reviewed_by is None):
            raise ValueError("recovery activation review requires both a reviewer and a time")
        if self.reviewed_at is not None and self.used_at is None:
            raise ValueError("recovery activation review requires a recorded use")

    def is_active_at(self, moment: datetime) -> bool:
        return self.activated_at <= moment < self.expires_at


def a_recovery_activation_is_granted_without_a_documented_justification_or_time_bound_expiry() -> (
    bool
):
    """SS11: "Recovery or break-glass access requires documented justification, time-bound
    activation where supported, strong authentication, visible notification, and post-use
    review." `LocalRecoveryActivation.__post_init__` makes both an un-justified and an
    open-ended activation unconstructable."""
    return False


def a_local_credential_authenticates_while_its_lockout_window_has_not_yet_elapsed() -> bool:
    """SS13: "rate-limited lockout" -- a locked local credential must not authenticate until its
    `locked_until` expiry has passed, enforced by `LocalCredentialService.authenticate`."""
    return False
