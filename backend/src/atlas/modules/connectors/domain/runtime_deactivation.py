from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
DISABLED_RUNTIME = "disabled_runtime"


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeDeactivationRecord:
    deactivation_id: str
    schema_version: str
    version: int
    activation_id: str
    activation_version: int
    activation_digest: str
    organization_id: str
    environment_id: str
    connector_id: str
    instance_id: str
    effective_runtime_state: str
    deactivated_by: str
    reason: str
    deactivated_at: datetime
    request_fingerprint: str
    idempotency_digest: str
    canonical_digest: str
    atlas_runtime_disabled: bool = True
    target_authority_revoked: bool = True
    managed_infrastructure_contacted: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.deactivation_id,
            self.schema_version,
            self.activation_id,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.instance_id,
            self.effective_runtime_state,
            self.deactivated_by,
        ):
            validate_stable_identifier(value, "connector runtime deactivation identifier")
        if (
            self.version != 1
            or self.activation_version != 1
            or self.effective_runtime_state != DISABLED_RUNTIME
            or not 20 <= len(self.reason.strip()) <= 1000
            or self.deactivated_at.tzinfo is None
            or any(
                _DIGEST.fullmatch(value) is None
                for value in (
                    self.activation_digest,
                    self.request_fingerprint,
                    self.idempotency_digest,
                    self.canonical_digest,
                )
            )
            or not self.atlas_runtime_disabled
            or not self.target_authority_revoked
            or self.managed_infrastructure_contacted
            or self.infrastructure_mutation_performed
        ):
            raise ValueError("Connector runtime deactivation record is invalid")
