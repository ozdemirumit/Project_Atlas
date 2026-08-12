from __future__ import annotations

import base64
import hmac
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.connectors.application.upgrade_evidence_authenticity_ports import (
    ConnectorUpgradeEvidenceAuthenticityError,
)
from atlas.modules.connectors.domain.upgrade_evidence_authenticity import (
    ConnectorUpgradeEvidenceSignature,
    ConnectorUpgradeEvidenceSigningKey,
    ConnectorUpgradeEvidenceSigningKeyState,
    ConnectorUpgradeEvidenceSigningProviderDiagnostic,
    ConnectorUpgradeEvidenceSigningProviderTrust,
    ConnectorUpgradeSigningProviderConformanceState,
)


class NonProductionHmacUpgradeEvidenceAuthenticityProvider:
    def __init__(
        self,
        *,
        key: ConnectorUpgradeEvidenceSigningKey,
        key_material: bytes,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(key_material) < 32:
            raise ValueError("Non-production signing key must be at least 32 bytes")
        if key.algorithm != "algorithm.hmac-sha256-nonproduction":
            raise ValueError("Non-production signing algorithm is invalid")
        self._key = key
        self._key_material = key_material
        self._clock = clock or (lambda: datetime.now(UTC))

    async def trust_inventory(
        self, *, organization_id: str, environment_id: str
    ) -> ConnectorUpgradeEvidenceSigningProviderTrust:
        if (
            self._key.organization_id != organization_id
            or self._key.environment_id != environment_id
        ):
            raise ConnectorUpgradeEvidenceAuthenticityError(
                "connector_upgrade_evidence_signing_key_scope_invalid"
            )
        return ConnectorUpgradeEvidenceSigningProviderTrust(
            provider_class="provider.nonproduction-hmac",
            organization_id=organization_id,
            environment_id=environment_id,
            provider_available=True,
            production_approved=False,
            keys=(self._key,),
        )

    async def active_key(
        self, *, organization_id: str, environment_id: str
    ) -> ConnectorUpgradeEvidenceSigningKey:
        self._validate_key(self._key, organization_id, environment_id)
        return self._key

    async def sign(
        self,
        *,
        key: ConnectorUpgradeEvidenceSigningKey,
        payload_digest: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> ConnectorUpgradeEvidenceSignature:
        self._validate_key(key, key.organization_id, key.environment_id)
        if key != self._key:
            raise ConnectorUpgradeEvidenceAuthenticityError(
                "connector_upgrade_evidence_signing_key_unknown"
            )
        value = self._signature_value(payload_digest)
        raw = base64.urlsafe_b64decode(value + "=")
        return ConnectorUpgradeEvidenceSignature(
            key_id=key.key_id,
            key_version=key.key_version,
            signer_profile_id=key.signer_profile_id,
            signer_workload_id=key.signer_workload_id,
            algorithm=key.algorithm,
            signed_payload_digest=payload_digest,
            signature_value=value,
            signature_digest=sha256(raw).hexdigest(),
            issued_at=issued_at,
            expires_at=expires_at,
        )

    async def diagnostic_sign_and_verify(
        self,
        *,
        organization_id: str,
        environment_id: str,
        challenge_digest: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> ConnectorUpgradeEvidenceSigningProviderDiagnostic:
        try:
            key = await self.active_key(
                organization_id=organization_id, environment_id=environment_id
            )
        except ConnectorUpgradeEvidenceAuthenticityError:
            return ConnectorUpgradeEvidenceSigningProviderDiagnostic(
                provider_class="provider.nonproduction-hmac",
                organization_id=organization_id,
                environment_id=environment_id,
                key=None,
                state=ConnectorUpgradeSigningProviderConformanceState.INELIGIBLE_KEY,
            )
        try:
            signature = await self.sign(
                key=key,
                payload_digest=challenge_digest,
                issued_at=issued_at,
                expires_at=expires_at,
            )
        except ConnectorUpgradeEvidenceAuthenticityError:
            return ConnectorUpgradeEvidenceSigningProviderDiagnostic(
                provider_class="provider.nonproduction-hmac",
                organization_id=organization_id,
                environment_id=environment_id,
                key=key,
                state=ConnectorUpgradeSigningProviderConformanceState.SIGN_FAILED,
            )
        try:
            verified_key = await self.verify(
                signature=signature,
                payload_digest=challenge_digest,
                organization_id=organization_id,
                environment_id=environment_id,
            )
        except ConnectorUpgradeEvidenceAuthenticityError:
            state = ConnectorUpgradeSigningProviderConformanceState.VERIFY_FAILED
        else:
            state = (
                ConnectorUpgradeSigningProviderConformanceState.CONFORMANT
                if verified_key == key
                else ConnectorUpgradeSigningProviderConformanceState.VERIFY_FAILED
            )
        return ConnectorUpgradeEvidenceSigningProviderDiagnostic(
            provider_class="provider.nonproduction-hmac",
            organization_id=organization_id,
            environment_id=environment_id,
            key=key,
            state=state,
        )

    async def verify(
        self,
        *,
        signature: ConnectorUpgradeEvidenceSignature,
        payload_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorUpgradeEvidenceSigningKey:
        key = self._key
        if signature.key_id != key.key_id or signature.key_version != key.key_version:
            raise ConnectorUpgradeEvidenceAuthenticityError(
                "connector_upgrade_evidence_signing_key_unknown"
            )
        self._validate_key(key, organization_id, environment_id)
        if (
            signature.algorithm != key.algorithm
            or signature.signer_profile_id != key.signer_profile_id
            or signature.signer_workload_id != key.signer_workload_id
            or signature.signed_payload_digest != payload_digest
            or not hmac.compare_digest(
                signature.signature_value, self._signature_value(payload_digest)
            )
        ):
            raise ConnectorUpgradeEvidenceAuthenticityError(
                "connector_upgrade_evidence_signature_invalid"
            )
        return key

    def _validate_key(
        self,
        key: ConnectorUpgradeEvidenceSigningKey,
        organization_id: str,
        environment_id: str,
    ) -> None:
        now = self._clock()
        if key.organization_id != organization_id or key.environment_id != environment_id:
            raise ConnectorUpgradeEvidenceAuthenticityError(
                "connector_upgrade_evidence_signing_key_scope_invalid"
            )
        if key.state is ConnectorUpgradeEvidenceSigningKeyState.REVOKED:
            raise ConnectorUpgradeEvidenceAuthenticityError(
                "connector_upgrade_evidence_signing_key_revoked"
            )
        if key.state is not ConnectorUpgradeEvidenceSigningKeyState.ACTIVE:
            raise ConnectorUpgradeEvidenceAuthenticityError(
                "connector_upgrade_evidence_signing_key_disabled"
            )
        if now < key.not_before or now >= key.expires_at:
            raise ConnectorUpgradeEvidenceAuthenticityError(
                "connector_upgrade_evidence_signing_key_expired"
            )

    def _signature_value(self, payload_digest: str) -> str:
        raw = hmac.new(self._key_material, payload_digest.encode("ascii"), sha256).digest()
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class UnavailableUpgradeEvidenceAuthenticityProvider:
    async def trust_inventory(
        self, *, organization_id: str, environment_id: str
    ) -> ConnectorUpgradeEvidenceSigningProviderTrust:
        return ConnectorUpgradeEvidenceSigningProviderTrust(
            provider_class="provider.unavailable",
            organization_id=organization_id,
            environment_id=environment_id,
            provider_available=False,
            production_approved=False,
            keys=(),
        )

    async def active_key(
        self, *, organization_id: str, environment_id: str
    ) -> ConnectorUpgradeEvidenceSigningKey:
        del organization_id, environment_id
        raise ConnectorUpgradeEvidenceAuthenticityError(
            "connector_upgrade_evidence_signing_provider_unavailable"
        )

    async def sign(
        self,
        *,
        key: ConnectorUpgradeEvidenceSigningKey,
        payload_digest: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> ConnectorUpgradeEvidenceSignature:
        del key, payload_digest, issued_at, expires_at
        raise ConnectorUpgradeEvidenceAuthenticityError(
            "connector_upgrade_evidence_signing_provider_unavailable"
        )

    async def diagnostic_sign_and_verify(
        self,
        *,
        organization_id: str,
        environment_id: str,
        challenge_digest: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> ConnectorUpgradeEvidenceSigningProviderDiagnostic:
        del challenge_digest, issued_at, expires_at
        return ConnectorUpgradeEvidenceSigningProviderDiagnostic(
            provider_class="provider.unavailable",
            organization_id=organization_id,
            environment_id=environment_id,
            key=None,
            state=ConnectorUpgradeSigningProviderConformanceState.UNAVAILABLE,
        )

    async def verify(
        self,
        *,
        signature: ConnectorUpgradeEvidenceSignature,
        payload_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorUpgradeEvidenceSigningKey:
        del signature, payload_digest, organization_id, environment_id
        raise ConnectorUpgradeEvidenceAuthenticityError(
            "connector_upgrade_evidence_signing_provider_unavailable"
        )
