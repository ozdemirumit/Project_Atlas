from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.connectors.domain.upgrade_approval import ConnectorUpgradeEvidenceReceipt
from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{43,512}$")


class ConnectorUpgradeEvidenceAuthenticityState(StrEnum):
    AUTHENTIC = "authentic"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNVERIFIABLE = "unverifiable"


class ConnectorUpgradeEvidenceSigningKeyState(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    REVOKED = "revoked"


class ConnectorUpgradeEvidenceSigningKeyEffectiveState(StrEnum):
    ACTIVE = "active"
    NOT_YET_VALID = "not_yet_valid"
    EXPIRED = "expired"
    DISABLED = "disabled"
    REVOKED = "revoked"


class ConnectorUpgradeSigningProviderConformanceState(StrEnum):
    CONFORMANT = "conformant"
    UNAVAILABLE = "unavailable"
    INELIGIBLE_KEY = "ineligible_key"
    SIGN_FAILED = "sign_failed"
    VERIFY_FAILED = "verify_failed"
    POLICY_BLOCKED = "policy_blocked"


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeEvidenceSigningKey:
    key_id: str
    key_version: str
    signer_profile_id: str
    signer_workload_id: str
    algorithm: str
    organization_id: str
    environment_id: str
    state: ConnectorUpgradeEvidenceSigningKeyState
    not_before: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        for value in (
            self.key_id,
            self.key_version,
            self.signer_profile_id,
            self.signer_workload_id,
            self.algorithm,
            self.organization_id,
            self.environment_id,
        ):
            validate_stable_identifier(value, "connector upgrade evidence signing key")
        if (
            self.not_before.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.not_before
        ):
            raise ValueError("Connector upgrade evidence signing key lifetime is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeEvidenceSigningProviderTrust:
    provider_class: str
    organization_id: str
    environment_id: str
    provider_available: bool
    production_approved: bool
    keys: tuple[ConnectorUpgradeEvidenceSigningKey, ...]

    def __post_init__(self) -> None:
        for value in (self.provider_class, self.organization_id, self.environment_id):
            validate_stable_identifier(value, "connector upgrade evidence signing provider trust")
        references = {(key.key_id, key.key_version) for key in self.keys}
        if (
            len(references) != len(self.keys)
            or any(
                key.organization_id != self.organization_id
                or key.environment_id != self.environment_id
                for key in self.keys
            )
            or (not self.provider_available and self.keys)
        ):
            raise ValueError("Connector upgrade evidence signing provider trust is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeEvidenceSigningProviderDiagnostic:
    provider_class: str
    organization_id: str
    environment_id: str
    key: ConnectorUpgradeEvidenceSigningKey | None
    state: ConnectorUpgradeSigningProviderConformanceState

    def __post_init__(self) -> None:
        for value in (self.provider_class, self.organization_id, self.environment_id):
            validate_stable_identifier(value, "connector upgrade signing provider diagnostic")
        if self.state not in {
            ConnectorUpgradeSigningProviderConformanceState.CONFORMANT,
            ConnectorUpgradeSigningProviderConformanceState.UNAVAILABLE,
            ConnectorUpgradeSigningProviderConformanceState.INELIGIBLE_KEY,
            ConnectorUpgradeSigningProviderConformanceState.SIGN_FAILED,
            ConnectorUpgradeSigningProviderConformanceState.VERIFY_FAILED,
        }:
            raise ValueError("Connector upgrade signing provider diagnostic state is invalid")
        if self.key is not None and (
            self.key.organization_id != self.organization_id
            or self.key.environment_id != self.environment_id
        ):
            raise ValueError("Connector upgrade signing provider diagnostic scope is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeEvidenceSigningKeyTrust:
    key_id: str
    key_version: str
    signer_profile_id: str
    signer_workload_id: str
    algorithm: str
    configured_state: ConnectorUpgradeEvidenceSigningKeyState
    effective_state: ConnectorUpgradeEvidenceSigningKeyEffectiveState
    not_before: datetime
    expires_at: datetime
    signing_eligible: bool
    verification_trusted: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for value in (
            self.key_id,
            self.key_version,
            self.signer_profile_id,
            self.signer_workload_id,
            self.algorithm,
        ):
            validate_stable_identifier(value, "connector upgrade evidence signing key trust")
        if (
            self.not_before.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.not_before
            or not self.reason_codes
            or any(
                not reason.startswith("connector.upgrade.signing-key-trust.")
                for reason in self.reason_codes
            )
            or self.signing_eligible
            != (self.effective_state is ConnectorUpgradeEvidenceSigningKeyEffectiveState.ACTIVE)
        ):
            raise ValueError("Connector upgrade evidence signing key trust is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeEvidenceSigningKeyTrustInventory:
    schema_version: str
    organization_id: str
    environment_id: str
    provider_class: str
    provider_state: str
    generated_at: datetime
    keys: tuple[ConnectorUpgradeEvidenceSigningKeyTrust, ...]
    canonical_digest: str
    provider_available: bool
    production_approved: bool
    key_management_authorized: bool = False
    signing_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.provider_class,
        ):
            validate_stable_identifier(value, "connector upgrade signing key trust inventory")
        if (
            self.schema_version != "atlas.connector-upgrade-signing-key-trust-inventory.v1"
            or self.provider_state not in {"available", "unavailable"}
            or self.provider_available != (self.provider_state == "available")
            or self.generated_at.tzinfo is None
            or _DIGEST.fullmatch(self.canonical_digest) is None
            or any(
                (
                    self.key_management_authorized,
                    self.signing_authorized,
                    self.execution_authorized,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector upgrade signing key trust inventory is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeSigningProviderConformanceAssessment:
    assessment_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    assessed_by: str
    provider_class: str
    production_approved: bool
    key_id: str | None
    key_version: str | None
    algorithm: str | None
    challenge_digest: str
    policy_id: str
    policy_version: str
    observed_at: datetime
    valid_until: datetime
    state: ConnectorUpgradeSigningProviderConformanceState
    reason_codes: tuple[str, ...]
    request_fingerprint: str
    idempotency_key: str
    canonical_digest: str
    diagnostic_only: bool = True
    signing_provider_conformant: bool = False
    key_management_authorized: bool = False
    receipt_signing_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.assessment_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.assessed_by,
            self.provider_class,
            self.policy_id,
            self.policy_version,
        ):
            validate_stable_identifier(value, "connector upgrade signing provider conformance")
        for optional_value in (self.key_id, self.key_version, self.algorithm):
            if optional_value is not None:
                validate_stable_identifier(
                    optional_value, "connector upgrade signing provider conformance key"
                )
        if (
            self.schema_version
            != "atlas.connector-upgrade-signing-provider-conformance-assessment.v1"
            or self.version != 1
            or _DIGEST.fullmatch(self.challenge_digest) is None
            or _DIGEST.fullmatch(self.request_fingerprint) is None
            or _DIGEST.fullmatch(self.canonical_digest) is None
            or self.observed_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_until <= self.observed_at
            or not self.reason_codes
            or any(
                not reason.startswith("connector.upgrade.signing-provider-conformance.")
                for reason in self.reason_codes
            )
            or self.signing_provider_conformant
            != (self.state is ConnectorUpgradeSigningProviderConformanceState.CONFORMANT)
            or not self.diagnostic_only
            or any(
                (
                    self.key_management_authorized,
                    self.receipt_signing_authorized,
                    self.execution_authorized,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector upgrade signing provider conformance is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeEvidenceSignature:
    key_id: str
    key_version: str
    signer_profile_id: str
    signer_workload_id: str
    algorithm: str
    signed_payload_digest: str
    signature_value: str
    signature_digest: str
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        for value in (
            self.key_id,
            self.key_version,
            self.signer_profile_id,
            self.signer_workload_id,
            self.algorithm,
        ):
            validate_stable_identifier(value, "connector upgrade evidence signature")
        if (
            _DIGEST.fullmatch(self.signed_payload_digest) is None
            or _SIGNATURE.fullmatch(self.signature_value) is None
            or _DIGEST.fullmatch(self.signature_digest) is None
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("Connector upgrade evidence signature is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeSignedEvidenceReceipt:
    signed_receipt_id: str
    schema_version: str
    version: int
    receipt: ConnectorUpgradeEvidenceReceipt
    signature: ConnectorUpgradeEvidenceSignature
    organization_id: str
    environment_id: str
    request_id: str
    canonical_digest: str
    evidence_receipt_only: bool = True
    authenticity_claimed: bool = True
    runtime_acceptable: bool = False
    approval_consumed: bool = False
    handoff_ready: bool = False
    handoff_artifact_issued: bool = False
    target_contacted: bool = False
    package_rebound: bool = False
    configuration_changed: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.signed_receipt_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.request_id,
        ):
            validate_stable_identifier(value, "connector upgrade signed evidence receipt")
        if (
            self.schema_version != "atlas.connector-upgrade-signed-evidence-receipt.v1"
            or self.version != 1
            or _DIGEST.fullmatch(self.canonical_digest) is None
            or self.receipt.organization_id != self.organization_id
            or self.receipt.environment_id != self.environment_id
            or self.receipt.request_id != self.request_id
            or self.signature.signed_payload_digest == self.receipt.canonical_digest
            or not self.evidence_receipt_only
            or not self.authenticity_claimed
            or any(
                (
                    self.runtime_acceptable,
                    self.approval_consumed,
                    self.handoff_ready,
                    self.handoff_artifact_issued,
                    self.target_contacted,
                    self.package_rebound,
                    self.configuration_changed,
                    self.execution_authorized,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector upgrade signed evidence receipt is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorUpgradeSignedEvidenceReceiptVerification:
    verification_id: str
    schema_version: str
    signed_receipt_id: str
    signed_receipt_digest: str
    receipt_id: str
    receipt_digest: str
    request_id: str
    organization_id: str
    environment_id: str
    verified_by: str
    verified_at: datetime
    key_id: str
    key_version: str
    signer_workload_id: str
    algorithm: str
    authenticity_state: ConnectorUpgradeEvidenceAuthenticityState
    receipt_verification_state: str
    reason_codes: tuple[str, ...]
    canonical_digest: str
    integrity_valid: bool = True
    authenticity_proven: bool = False
    current_state_matches: bool = False
    evidence_receipt_only: bool = True
    approval_consumed: bool = False
    handoff_ready: bool = False
    handoff_artifact_issued: bool = False
    target_contacted: bool = False
    package_rebound: bool = False
    configuration_changed: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.verification_id,
            self.schema_version,
            self.signed_receipt_id,
            self.receipt_id,
            self.request_id,
            self.organization_id,
            self.environment_id,
            self.verified_by,
            self.key_id,
            self.key_version,
            self.signer_workload_id,
            self.algorithm,
        ):
            validate_stable_identifier(value, "connector upgrade signed receipt verification")
        if (
            self.schema_version != "atlas.connector-upgrade-signed-evidence-receipt-verification.v1"
            or _DIGEST.fullmatch(self.signed_receipt_digest) is None
            or _DIGEST.fullmatch(self.receipt_digest) is None
            or _DIGEST.fullmatch(self.canonical_digest) is None
            or self.verified_at.tzinfo is None
            or self.receipt_verification_state
            not in {"current", "stale", "expired", "unverifiable", "not_compared"}
            or not self.reason_codes
            or any(
                not reason.startswith("connector.upgrade.signed-evidence-receipt.")
                for reason in self.reason_codes
            )
            or self.authenticity_proven
            != (self.authenticity_state is ConnectorUpgradeEvidenceAuthenticityState.AUTHENTIC)
            or self.current_state_matches != (self.receipt_verification_state == "current")
            or not self.integrity_valid
            or not self.evidence_receipt_only
            or any(
                (
                    self.approval_consumed,
                    self.handoff_ready,
                    self.handoff_artifact_issued,
                    self.target_contacted,
                    self.package_rebound,
                    self.configuration_changed,
                    self.execution_authorized,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector upgrade signed receipt verification is invalid")
