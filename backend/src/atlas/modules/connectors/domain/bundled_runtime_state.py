from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

DISABLED = "disabled"
ENABLED_READ_ONLY = "enabled_read_only"


@dataclass(frozen=True, slots=True)
class BundledConnectorRuntimeState:
    organization_id: str
    environment_id: str
    connector_id: str
    instance_id: str
    state: str
    version: int
    changed_at: datetime | None
    changed_by: str | None
    reason: str | None
    configuration_id: str | None
    connection_test_id: str | None
    managed_infrastructure_contacted: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.instance_id,
        ):
            validate_stable_identifier(value, "bundled connector runtime state identifier")
        for optional_value in (
            self.changed_by,
            self.configuration_id,
            self.connection_test_id,
        ):
            if optional_value is not None:
                validate_stable_identifier(
                    optional_value, "bundled connector runtime state identifier"
                )
        initial = self.version == 0
        if (
            self.state not in {DISABLED, ENABLED_READ_ONLY}
            or self.version < 0
            or self.managed_infrastructure_contacted
            or self.infrastructure_mutation_performed
            or initial
            != (
                self.changed_at is None
                and self.changed_by is None
                and self.reason is None
                and self.configuration_id is None
                and self.connection_test_id is None
            )
            or (self.changed_at is not None and self.changed_at.tzinfo is None)
            or (self.reason is not None and not 20 <= len(self.reason.strip()) <= 1000)
            or (
                self.state == ENABLED_READ_ONLY
                and (self.configuration_id is None or self.connection_test_id is None)
            )
        ):
            raise ValueError("Bundled connector runtime state is invalid")
