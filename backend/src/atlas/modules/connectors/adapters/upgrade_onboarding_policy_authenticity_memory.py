from __future__ import annotations

import base64
import hmac
from hashlib import sha256

from atlas.modules.connectors.domain.upgrade_evidence_authenticity import (
    ConnectorUpgradeSigningProviderOnboardingPolicyAttestation,
    ConnectorUpgradeSigningProviderOnboardingPolicyTrustKey,
)


class InMemoryConnectorUpgradeSigningProviderOnboardingPolicyAttestationSource:
    def __init__(
        self,
        attestations: tuple[ConnectorUpgradeSigningProviderOnboardingPolicyAttestation, ...] = (),
    ) -> None:
        self._attestations = attestations

    async def list_scope(
        self, *, organization_id: str, environment_id: str, policy_id: str
    ) -> tuple[ConnectorUpgradeSigningProviderOnboardingPolicyAttestation, ...]:
        return tuple(
            item
            for item in self._attestations
            if item.organization_id == organization_id
            and item.environment_id == environment_id
            and item.policy_id == policy_id
        )


class InMemoryConnectorUpgradeSigningProviderOnboardingPolicyTrustSource:
    def __init__(
        self, trust_keys: tuple[ConnectorUpgradeSigningProviderOnboardingPolicyTrustKey, ...] = ()
    ) -> None:
        self._trust_keys = trust_keys

    async def list_scope(
        self, *, organization_id: str, environment_id: str, issuer_id: str
    ) -> tuple[ConnectorUpgradeSigningProviderOnboardingPolicyTrustKey, ...]:
        return tuple(
            item
            for item in self._trust_keys
            if item.organization_id == organization_id
            and item.environment_id == environment_id
            and item.issuer_id == issuer_id
        )


class HmacConnectorUpgradeSigningProviderOnboardingPolicyVerifier:
    def __init__(self, *, key_id: str, key_version: str, key_material: bytes) -> None:
        if len(key_material) < 32:
            raise ValueError("Development policy verification key material is too short")
        self._key_id = key_id
        self._key_version = key_version
        self._key_material = key_material

    async def verify(
        self,
        *,
        attestation: ConnectorUpgradeSigningProviderOnboardingPolicyAttestation,
        trust_key: ConnectorUpgradeSigningProviderOnboardingPolicyTrustKey,
    ) -> bool:
        if (
            trust_key.key_id != self._key_id
            or trust_key.key_version != self._key_version
            or attestation.key_id != trust_key.key_id
            or attestation.key_version != trust_key.key_version
            or attestation.algorithm != "algorithm.hmac-sha256-nonproduction"
        ):
            return False
        expected = (
            base64.urlsafe_b64encode(
                hmac.new(
                    self._key_material,
                    attestation.policy_digest.encode("ascii"),
                    sha256,
                ).digest()
            )
            .decode("ascii")
            .rstrip("=")
        )
        return hmac.compare_digest(expected, attestation.signature_value)


class UnavailableConnectorUpgradeSigningProviderOnboardingPolicyVerifier:
    async def verify(
        self,
        *,
        attestation: ConnectorUpgradeSigningProviderOnboardingPolicyAttestation,
        trust_key: ConnectorUpgradeSigningProviderOnboardingPolicyTrustKey,
    ) -> bool:
        del attestation, trust_key
        return False
