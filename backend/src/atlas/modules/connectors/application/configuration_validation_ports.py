from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.configuration_validation import (
    ConnectorConfigurationEvidenceSnapshot,
    ConnectorConfigurationValidationPolicySnapshot,
    ConnectorConfigurationValidationRecord,
)
from atlas.modules.connectors.domain.credential_assignment import (
    ConnectorCredentialAssignmentRecord,
)
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
)


class ConnectorConfigurationValidationError(RuntimeError):
    pass


class ConnectorConfigurationAssignmentSource(Protocol):
    async def configuration_validation_source(
        self, *, assignment_id: str
    ) -> tuple[
        ConnectorCredentialAssignmentRecord,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]: ...


class ConnectorConfigurationEvidenceSource(Protocol):
    async def get_by_id(
        self, *, evidence_id: str
    ) -> ConnectorConfigurationEvidenceSnapshot | None: ...


class ConnectorConfigurationValidationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorConfigurationValidationPolicySnapshot | None: ...


class ConnectorConfigurationValidationRepository(Protocol):
    async def get(self, *, validation_id: str) -> ConnectorConfigurationValidationRecord | None: ...

    async def get_by_assignment(
        self, *, source_assignment_id: str
    ) -> ConnectorConfigurationValidationRecord | None: ...

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorConfigurationValidationRecord | None: ...

    async def add(self, record: ConnectorConfigurationValidationRecord) -> bool: ...

    async def close(self) -> None: ...
