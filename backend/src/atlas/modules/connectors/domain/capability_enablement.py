from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
ENABLED_CAPABILITIES_GOVERNED = "enabled_capabilities_governed"


@dataclass(frozen=True, slots=True)
class ConnectorGovernedCapability:
    capability_id: str
    capability_class: str
    required_permission: str

    def __post_init__(self) -> None:
        for value in (
            self.capability_id,
            self.required_permission,
        ):
            validate_stable_identifier(value, "governed connector capability identifier")
        if self.capability_class not in {"C0", "C1"}:
            raise ValueError("Governed connector capability is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorCapabilityProfileSnapshot:
    profile_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    target_type: str
    capabilities: tuple[ConnectorGovernedCapability, ...]
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.profile_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.release_version,
            self.instance_id,
            self.target_type,
            self.signed_by,
        ):
            validate_stable_identifier(value, "connector capability profile identifier")
        capability_keys = tuple(item.capability_id for item in self.capabilities)
        if (
            self.version != 1
            or not self.capabilities
            or capability_keys != tuple(sorted(capability_keys))
            or len(capability_keys) != len(set(capability_keys))
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (self.package_digest, self.manifest_digest, self.canonical_digest)
            )
        ):
            raise ValueError("Connector capability profile contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorCapabilityEnablementPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_validation_schema: str
    required_profile_schema: str
    required_profile_signer_id: str
    allowed_capability_classes: tuple[str, ...]
    maximum_capabilities: int
    maximum_validation_age_hours: int
    maximum_profile_age_hours: int
    required_assurance_level: AssuranceLevel
    required_effective_state: str
    enablement_record_schema: str
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.required_validation_schema,
            self.required_profile_schema,
            self.required_profile_signer_id,
            self.required_effective_state,
            self.enablement_record_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "capability enablement policy identifier")
        if (
            self.version != 1
            or self.allowed_capability_classes != ("C0", "C1")
            or not 1 <= self.maximum_capabilities <= 100
            or not 1 <= self.maximum_validation_age_hours <= 8760
            or not 1 <= self.maximum_profile_age_hours <= 8760
            or self.required_assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
            or self.required_effective_state != ENABLED_CAPABILITIES_GOVERNED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Capability enablement policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorCapabilityEnablementRecord:
    enablement_id: str
    schema_version: str
    version: int
    source_validation_id: str
    source_validation_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    owner_id: str
    target_profile_id: str
    target_profile_digest: str
    site_id: str
    target_type: str
    target_product: str
    credential_profile_id: str
    credential_profile_digest: str
    capability_profile_id: str
    capability_profile_digest: str
    capabilities: tuple[ConnectorGovernedCapability, ...]
    enablement_policy_id: str
    enablement_policy_digest: str
    enablement_policy_version: str
    enablement_version: int
    instance_state: str
    enabled_by: str
    purpose: str
    enabled_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    configuration_validated: bool = True
    connectivity_evidence_verified: bool = True
    eligible_for_capability_governance: bool = True
    capability_governance_applied: bool = True
    connector_enabled: bool = True
    eligible_for_runtime_trust: bool = True
    promotion_blocked: bool = False
    credentials_resolved: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.enablement_id,
            self.schema_version,
            self.source_validation_id,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.release_version,
            self.instance_id,
            self.instance_key,
            self.owner_id,
            self.target_profile_id,
            self.site_id,
            self.target_type,
            self.credential_profile_id,
            self.capability_profile_id,
            self.enablement_policy_id,
            self.enablement_policy_version,
            self.instance_state,
            self.enabled_by,
        ):
            validate_stable_identifier(value, "capability enablement record identifier")
        if (
            self.version != 1
            or self.enablement_version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not self.capabilities
            or self.enabled_at.tzinfo is None
            or self.instance_state != ENABLED_CAPABILITIES_GOVERNED
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.source_validation_digest,
                    self.package_digest,
                    self.manifest_digest,
                    self.target_profile_digest,
                    self.credential_profile_digest,
                    self.capability_profile_digest,
                    self.enablement_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not 8 <= len(self.idempotency_key) <= 128
            or not all(
                (
                    self.configuration_validated,
                    self.connectivity_evidence_verified,
                    self.eligible_for_capability_governance,
                    self.capability_governance_applied,
                    self.connector_enabled,
                    self.eligible_for_runtime_trust,
                )
            )
            or any(
                (
                    self.promotion_blocked,
                    self.credentials_resolved,
                    self.runtime_trust_granted,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector capability enablement record is invalid")
