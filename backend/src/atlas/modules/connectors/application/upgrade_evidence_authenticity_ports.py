from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.connectors.domain.upgrade_evidence_authenticity import (
    ConnectorUpgradeEvidenceSignature,
    ConnectorUpgradeEvidenceSigningKey,
)


class ConnectorUpgradeEvidenceAuthenticityError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ConnectorUpgradeEvidenceAuthenticityProvider(Protocol):
    async def active_key(
        self, *, organization_id: str, environment_id: str
    ) -> ConnectorUpgradeEvidenceSigningKey: ...

    async def sign(
        self,
        *,
        key: ConnectorUpgradeEvidenceSigningKey,
        payload_digest: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> ConnectorUpgradeEvidenceSignature: ...

    async def verify(
        self,
        *,
        signature: ConnectorUpgradeEvidenceSignature,
        payload_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorUpgradeEvidenceSigningKey: ...
