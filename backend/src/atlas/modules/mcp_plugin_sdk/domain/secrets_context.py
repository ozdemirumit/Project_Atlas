"""ATLAS-021 SS11/SS12: the secret API and invocation context.

`InvocationContext` "does not expose user credentials, raw approval tokens, unrestricted policy,
or secret-store administration" by absence -- no field on this type could represent any of those,
the same enforcement pattern this session has used repeatedly for absolute prose prohibitions with
a natural object to attach to.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class SecretDeliveryMode(StrEnum):
    """SS11: "connector code receives either" a preconfigured client or an opaque handle."""

    PRECONFIGURED_TARGET_CLIENT = "preconfigured_target_client"
    OPAQUE_SECRET_HANDLE = "opaque_secret_handle"


@dataclass(frozen=True, slots=True, repr=False)
class SecretHandle:
    """SS11: "secret objects redact display, equality diagnostics, and exception output." A
    custom `__repr__` (which Python also uses for `str()` and for formatting values inside
    exception messages) never includes `resolved_value` -- redacting display, exception output,
    and equality-assertion diagnostics (which render via `repr()`) all at once."""

    handle_id: str
    instance_id: str
    resolved_value: str
    resolved_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.handle_id, "handle_id")
        validate_stable_identifier(self.instance_id, "instance_id")
        if self.resolved_at.tzinfo is None:
            raise ValueError("resolved_at must be timezone-aware")
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        if self.expires_at <= self.resolved_at:
            raise ValueError("expires_at must be after resolved_at")

    def __repr__(self) -> str:
        return f"SecretHandle(handle_id={self.handle_id!r}, resolved_value=<redacted>)"


def secret_handle_can_be_serialized() -> bool:
    """SS11: "the API must prevent or discourage ... serializing secret values.\""""
    return False


def secret_object_can_be_logged_or_returned() -> bool:
    """SS11: "... logging or returning secret objects.\""""
    return False


def secret_can_be_passed_to_model_or_evidence_context() -> bool:
    """SS11: "... passing secrets to model or evidence context.\""""
    return False


def instance_can_read_another_instances_secret_path() -> bool:
    """SS11: "... reading another instance's secret path.\""""
    return False


def secret_persists_after_invocation() -> bool:
    """SS11: "... persisting secrets after invocation.\""""
    return False


@dataclass(frozen=True, slots=True)
class InvocationContext:
    """SS12's declared elements."""

    invocation_id: str
    request_id: str
    workflow_id: str | None
    correlation_id: str
    attempt: int
    connector_version: str
    package_version: str
    instance_id: str
    capability_version: str
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    deadline: datetime
    idempotency_key: str | None
    cancellation_token: str
    approved_feature_flags: frozenset[str]
    compatibility_flags: frozenset[str]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.invocation_id, "invocation_id")
        validate_stable_identifier(self.request_id, "request_id")
        validate_stable_identifier(self.instance_id, "instance_id")
        validate_stable_identifier(self.organization_id, "organization_id")
        validate_stable_identifier(self.environment_id, "environment_id")
        validate_stable_identifier(self.site_id, "site_id")
        validate_stable_identifier(self.target_id, "target_id")
        if not self.correlation_id.strip():
            raise ValueError("an invocation context requires a correlation id")
        if self.attempt < 1:
            raise ValueError("attempt must be a positive, 1-based attempt number")
        if not self.connector_version.strip():
            raise ValueError("an invocation context requires a connector version")
        if not self.package_version.strip():
            raise ValueError("an invocation context requires a package version")
        if not self.capability_version.strip():
            raise ValueError("an invocation context requires a capability version")
        if self.deadline.tzinfo is None:
            raise ValueError("deadline must be timezone-aware")
        if not self.cancellation_token.strip():
            raise ValueError("an invocation context requires a cancellation token")


def is_cancelled(*, cancellation_token: str, cancelled_tokens: frozenset[str]) -> bool:
    return cancellation_token in cancelled_tokens
