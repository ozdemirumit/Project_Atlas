from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

_RESULT_CODE = re.compile(r"^[a-z][a-z0-9_]{2,127}$")


@dataclass(frozen=True, slots=True)
class ConnectorConnectionTestResult:
    test_id: str
    connector_id: str
    instance_id: str
    outcome: str
    result_code: str
    retryable: bool
    checked_at: datetime
    duration_ms: int
    read_only_request_performed: bool
    managed_infrastructure_contacted: bool
    target_details_disclosed: bool = False
    secret_material_disclosed: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (self.test_id, self.connector_id, self.instance_id):
            validate_stable_identifier(value, "connector connection test identifier")
        if (
            self.outcome not in {"passed", "failed"}
            or _RESULT_CODE.fullmatch(self.result_code) is None
            or self.checked_at.tzinfo is None
            or not 0 <= self.duration_ms <= 300_000
            or self.target_details_disclosed
            or self.secret_material_disclosed
            or self.infrastructure_mutation_performed
        ):
            raise ValueError("Connector connection test result is invalid")
