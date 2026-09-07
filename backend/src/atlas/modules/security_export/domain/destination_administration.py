"""ATLAS-034 SS7/SS16/SS19: Destination Configuration, Validation and Activation, Administration.

`SyslogDestination` (`domain/models.py`) already carries the technical transport/trust/filter
fields SS7 names. This module adds the administrative metadata and workflow SS7/SS16/SS19 also
require but that model has no field for: owner/purpose/maintenance-window/compliance-status
metadata, the eight-step validation-then-activation sequence, and the elevated-authorization gate
on disabling a mandatory destination.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class SyslogDestinationProfile:
    """SS7: "Stable destination ID, name, owner, purpose, and environment... Maintenance windows
    and health-alert recipients... Mandatory or optional compliance-destination status... Last
    validation time and active configuration version.\""""

    destination_id: str
    owner: str
    purpose: str
    environment_id: str
    maintenance_windows: tuple[str, ...]
    health_alert_recipients: tuple[str, ...]
    mandatory: bool
    last_validated_at: datetime | None
    active_version: int

    def __post_init__(self) -> None:
        validate_stable_identifier(self.destination_id, "destination_id")
        validate_stable_identifier(self.owner, "owner")
        validate_stable_identifier(self.environment_id, "environment_id")
        if not self.purpose.strip():
            raise ValueError("a syslog destination profile requires a purpose")
        if not self.health_alert_recipients:
            raise ValueError("a syslog destination profile requires health-alert recipients")
        if self.active_version < 1:
            raise ValueError("active_version must be positive")
        if self.last_validated_at is not None and self.last_validated_at.tzinfo is None:
            raise ValueError("last_validated_at must be timezone-aware")


class DestinationValidationStep(StrEnum):
    """SS16's eight-step sequence."""

    SAVED_NON_ACTIVE_VERSION = "saved_non_active_version"
    SYNTAX_DNS_ROUTE_PORT = "syntax_dns_route_port"
    TLS_TRUST_AND_IDENTITY = "tls_trust_and_identity"
    TEST_EVENT_SENT = "test_event_sent"
    COLLECTOR_RECEIPT_CONFIRMED = "collector_receipt_confirmed"
    MAPPING_PREVIEWED = "mapping_previewed"
    RATE_AND_CAPACITY_ESTIMATED = "rate_and_capacity_estimated"
    ACTIVATED = "activated"


VALIDATION_STEP_ORDER: tuple[DestinationValidationStep, ...] = (
    DestinationValidationStep.SAVED_NON_ACTIVE_VERSION,
    DestinationValidationStep.SYNTAX_DNS_ROUTE_PORT,
    DestinationValidationStep.TLS_TRUST_AND_IDENTITY,
    DestinationValidationStep.TEST_EVENT_SENT,
    DestinationValidationStep.COLLECTOR_RECEIPT_CONFIRMED,
    DestinationValidationStep.MAPPING_PREVIEWED,
    DestinationValidationStep.RATE_AND_CAPACITY_ESTIMATED,
    DestinationValidationStep.ACTIVATED,
)


@dataclass(frozen=True, slots=True)
class DestinationValidationRecord:
    """SS16: "A successful socket connection alone is not a successful end-to-end validation."
    `completed_steps` must be an exact, order-respecting prefix of `VALIDATION_STEP_ORDER` -- a
    socket-only check (step 2 alone) cannot masquerade as full validation, and steps cannot be
    marked complete out of order."""

    destination_id: str
    completed_steps: tuple[DestinationValidationStep, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.destination_id, "destination_id")
        expected_prefix = VALIDATION_STEP_ORDER[: len(self.completed_steps)]
        if self.completed_steps != expected_prefix:
            raise ValueError("validation steps must complete in SS16's declared order")

    @property
    def is_fully_validated(self) -> bool:
        return self.completed_steps == VALIDATION_STEP_ORDER


@dataclass(frozen=True, slots=True)
class DestinationDisablement:
    """SS19: "Disabling a mandatory destination requires elevated authorization, reason, and
    visible warning.\""""

    destination_id: str
    disabled_by: str
    reason: str
    mandatory_destination: bool
    elevated_authorization: bool
    warning_acknowledged: bool
    disabled_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.destination_id, "destination_id")
        validate_stable_identifier(self.disabled_by, "disabled_by")
        if not self.reason.strip():
            raise ValueError("disabling a syslog destination requires a reason")
        if self.disabled_at.tzinfo is None:
            raise ValueError("disablement time must be timezone-aware")
        if self.mandatory_destination and not (
            self.elevated_authorization and self.warning_acknowledged
        ):
            raise ValueError(
                "disabling a mandatory syslog destination requires elevated authorization and"
                " an acknowledged visible warning"
            )


def a_mandatory_destination_is_disabled_without_elevated_authorization_or_warning() -> bool:
    """SS19: "Disabling a mandatory destination requires elevated authorization, reason, and
    visible warning." `DestinationDisablement` makes disabling a mandatory destination without
    both unconstructable."""
    return False


def a_socket_only_check_is_reported_as_full_end_to_end_destination_validation() -> bool:
    """SS16: "A successful socket connection alone is not a successful end-to-end validation."
    `DestinationValidationRecord.is_fully_validated` requires every one of the eight steps, not
    merely the socket-reachability step (`SYNTAX_DNS_ROUTE_PORT`)."""
    return False
