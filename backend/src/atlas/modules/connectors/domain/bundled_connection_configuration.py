from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

_DNS_NAME = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
_SYSTEM_ID = re.compile(r"^[A-Za-z0-9]{1,32}$")


def validate_connection_hostname(hostname: str) -> str:
    normalized = hostname.strip().lower()
    if normalized != hostname.lower() or not _DNS_NAME.fullmatch(normalized):
        raise ValueError("Connection hostname must be one bounded DNS name or IP address")
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        if normalized == "localhost" or normalized.endswith(".localhost"):
            raise ValueError("Localhost is not a connector target") from None
    else:
        if (
            address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
        ):
            raise ValueError("Unsafe connector target address")
    return normalized


@dataclass(frozen=True, slots=True)
class BundledConnectionConfiguration:
    configuration_id: str
    organization_id: str
    environment_id: str
    connector_id: str
    instance_id: str
    hostname: str
    port: int
    trust_profile_id: str
    secret_reference_id: str
    configured_by: str
    configured_at: datetime
    protocol: str = "https"
    development_only: bool = True
    secret_material_stored: bool = False
    infrastructure_mutation_performed: bool = False
    # Optional per-vendor scoping identifier, e.g. Huawei OceanStor's system_id: a value baked
    # into every request URL for a connector whose real API is scoped to one exact target per
    # configured instance, unlike Hitachi's single management endpoint fronting many arrays.
    # Left unset (None) by every vendor that doesn't need it.
    system_id: str | None = None

    def __post_init__(self) -> None:
        for value in (
            self.configuration_id,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.instance_id,
            self.trust_profile_id,
            self.secret_reference_id,
            self.configured_by,
        ):
            validate_stable_identifier(value, "bundled connection configuration identifier")
        validate_connection_hostname(self.hostname)
        if (
            not 1 <= self.port <= 65_535
            or self.configured_at.tzinfo is None
            or self.protocol != "https"
            or not self.development_only
            or self.secret_material_stored
            or self.infrastructure_mutation_performed
            or (self.system_id is not None and not _SYSTEM_ID.fullmatch(self.system_id))
        ):
            raise ValueError("Bundled connection configuration is invalid")
