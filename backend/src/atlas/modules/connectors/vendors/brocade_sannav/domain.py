from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

# World Wide Names are commonly rendered as 16 hex characters, colon-separated in pairs (e.g.
# "10:00:00:05:1e:35:1a:00"), but SANnav's exact serialization was not independently confirmed
# against a real instance during connector construction -- validated loosely (bounded length,
# hex-and-colon charset) rather than against an exact pattern that might reject a real value.
_PRINCIPAL_SWITCH_WWN = re.compile(r"^[0-9A-Fa-f:]{8,64}$")


@dataclass(frozen=True, slots=True)
class BrocadeAbout:
    """`GET /external-api/v1/about/` -- confirmed against Broadcom's SANnav Management Portal
    REST API Reference Manual, v3.0.1x (SANnav-301x-REST-API-RM100), introduced in SANnav v2.3.1.
    Not scoped to one fabric; used only to confirm the target is a compatible SANnav instance."""

    product_brand_name: str
    version: str


@dataclass(frozen=True, slots=True)
class BrocadeFabric:
    principal_switch_wwn: str
    name: str

    def __post_init__(self) -> None:
        if not _PRINCIPAL_SWITCH_WWN.fullmatch(self.principal_switch_wwn):
            raise ValueError("principal_switch_wwn has an invalid format")
        if not self.name.strip():
            raise ValueError("name must not be empty")


@dataclass(frozen=True, slots=True)
class BrocadeSwitch:
    fabric_principal_switch_wwn: str
    ip_address: str

    def __post_init__(self) -> None:
        if not _PRINCIPAL_SWITCH_WWN.fullmatch(self.fabric_principal_switch_wwn):
            raise ValueError("fabric_principal_switch_wwn has an invalid format")
        if not self.ip_address.strip():
            raise ValueError("ip_address must not be empty")


@dataclass(frozen=True, slots=True)
class BrocadeInventoryResult:
    fabrics: tuple[BrocadeFabric, ...]
    switches: tuple[BrocadeSwitch, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("inventory results require evidence")
        fabric_wwns = {fabric.principal_switch_wwn for fabric in self.fabrics}
        if any(switch.fabric_principal_switch_wwn not in fabric_wwns for switch in self.switches):
            raise ValueError("every switch must reference a fabric in this same result")


@dataclass(frozen=True, slots=True)
class BrocadeFaultSummary:
    """Deliberately coarse. The response *envelope* for POST /external-api/v2/fault/events/ is now
    confirmed against Broadcom's authoritative SANnav Management Portal REST API Reference Manual,
    v3.0.1x (SANnav-301x-REST-API-RM100): a top-level `events` array plus a `totalRecords` total
    count (see FaultEventsResponse). Per-event severity is deliberately still not parsed here --
    the manual's own worked example returns a `severityGroup` value ("MAJOR") that does not appear
    in its own declared `SeverityGroup` enum (ALL/ALERT/ERROR/WARNING/INFO/UNKNOWN), so the exact
    severity vocabulary remains unconfirmed even against the vendor's own authoritative reference.
    Rather than guess a severity mapping that could misreport, this still only counts events from a
    real, confirmed request/response round-trip. Per-event detail is a documented follow-up once
    that vocabulary discrepancy is resolved with Broadcom or verified live."""

    fabric_principal_switch_wwn: str
    event_count: int
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _PRINCIPAL_SWITCH_WWN.fullmatch(self.fabric_principal_switch_wwn):
            raise ValueError("fabric_principal_switch_wwn has an invalid format")
        if self.event_count < 0:
            raise ValueError("event_count must not be negative")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("fault summary results require evidence")
