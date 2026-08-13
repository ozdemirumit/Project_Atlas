from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
DISABLED_CONFIGURATION_VALIDATED = "disabled_configuration_validated"


@dataclass(frozen=True, slots=True)
class ConnectorConfigurationEvidenceSnapshot:
    evidence_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    source_assignment_id: str
    source_assignment_digest: str
    package_digest: str
    instance_id: str
    target_profile_id: str
    credential_profile_id: str
    target_type: str
    target_product: str
    probe_runner_id: str
    probe_runner_version: str
    network_zone_id: str
    configuration_result: str
    connectivity_result: str
    tls_result: str
    endpoint_identity_result: str
    authentication_result: str
    authorization_result: str
    product_identity_result: str
    latency_band: str
    completed_checks: tuple[str, ...]
    signed_by: str
    signature_verified: bool
    observed_at: datetime
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.evidence_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.source_assignment_id,
            self.instance_id,
            self.target_profile_id,
            self.credential_profile_id,
            self.target_type,
            self.probe_runner_id,
            self.probe_runner_version,
            self.network_zone_id,
            self.configuration_result,
            self.connectivity_result,
            self.tls_result,
            self.endpoint_identity_result,
            self.authentication_result,
            self.authorization_result,
            self.product_identity_result,
            self.latency_band,
            *self.completed_checks,
            self.signed_by,
        ):
            validate_stable_identifier(value, "connector configuration evidence identifier")
        if (
            self.version != 1
            or not 1 <= len(self.target_product.strip()) <= 200
            or not self.completed_checks
            or len(set(self.completed_checks)) != len(self.completed_checks)
            or not self.signature_verified
            or any(
                item.tzinfo is None for item in (self.observed_at, self.issued_at, self.expires_at)
            )
            or not self.observed_at <= self.issued_at < self.expires_at
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.source_assignment_digest,
                    self.package_digest,
                    self.canonical_digest,
                )
            )
        ):
            raise ValueError("Connector configuration evidence contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorConfigurationValidationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_assignment_schema: str
    required_evidence_schema: str
    required_evidence_signer_id: str
    allowed_probe_runner_ids: tuple[str, ...]
    allowed_network_zone_ids: tuple[str, ...]
    required_checks: tuple[str, ...]
    maximum_assignment_age_hours: int
    maximum_observation_age_minutes: int
    required_configuration_result: str
    required_connectivity_result: str
    required_tls_result: str
    required_endpoint_identity_result: str
    required_authentication_result: str
    required_authorization_result: str
    required_product_identity_result: str
    required_assurance_level: AssuranceLevel
    required_effective_state: str
    validation_record_schema: str
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
            self.required_assignment_schema,
            self.required_evidence_schema,
            self.required_evidence_signer_id,
            *self.allowed_probe_runner_ids,
            *self.allowed_network_zone_ids,
            *self.required_checks,
            self.required_configuration_result,
            self.required_connectivity_result,
            self.required_tls_result,
            self.required_endpoint_identity_result,
            self.required_authentication_result,
            self.required_authorization_result,
            self.required_product_identity_result,
            self.required_effective_state,
            self.validation_record_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "configuration validation policy identifier")
        if (
            self.version != 1
            or not self.allowed_probe_runner_ids
            or not self.allowed_network_zone_ids
            or not self.required_checks
            or not 1 <= self.maximum_assignment_age_hours <= 87600
            or not 1 <= self.maximum_observation_age_minutes <= 10080
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or self.required_effective_state != DISABLED_CONFIGURATION_VALIDATED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Configuration validation policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorConfigurationValidationRecord:
    validation_id: str
    schema_version: str
    version: int
    source_assignment_id: str
    source_assignment_digest: str
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
    credential_class: str
    authentication_method: str
    privilege_class: str
    evidence_id: str
    evidence_digest: str
    probe_runner_id: str
    probe_runner_version: str
    network_zone_id: str
    configuration_result: str
    connectivity_result: str
    tls_result: str
    endpoint_identity_result: str
    authentication_result: str
    authorization_result: str
    product_identity_result: str
    latency_band: str
    completed_checks: tuple[str, ...]
    evidence_observed_at: datetime
    validation_policy_id: str
    validation_policy_digest: str
    validation_policy_version: str
    validation_version: int
    instance_state: str
    validated_by: str
    purpose: str
    validated_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    package_installed: bool = True
    instance_created: bool = True
    target_configured: bool = True
    credential_references_assigned: bool = True
    eligible_for_configuration_validation: bool = True
    configuration_validated: bool = True
    connectivity_evidence_verified: bool = True
    eligible_for_capability_governance: bool = True
    promotion_blocked: bool = False
    credentials_resolved: bool = False
    connector_enabled: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.validation_id,
            self.schema_version,
            self.source_assignment_id,
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
            self.credential_class,
            self.authentication_method,
            self.privilege_class,
            self.evidence_id,
            self.probe_runner_id,
            self.probe_runner_version,
            self.network_zone_id,
            self.configuration_result,
            self.connectivity_result,
            self.tls_result,
            self.endpoint_identity_result,
            self.authentication_result,
            self.authorization_result,
            self.product_identity_result,
            self.latency_band,
            *self.completed_checks,
            self.validation_policy_id,
            self.validation_policy_version,
            self.instance_state,
            self.validated_by,
        ):
            validate_stable_identifier(value, "configuration validation record identifier")
        if (
            self.version != 1
            or self.validation_version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not self.completed_checks
            or not self.evidence_observed_at.tzinfo
            or not self.validated_at.tzinfo
            or self.instance_state != DISABLED_CONFIGURATION_VALIDATED
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.source_assignment_digest,
                    self.package_digest,
                    self.manifest_digest,
                    self.target_profile_digest,
                    self.credential_profile_digest,
                    self.evidence_digest,
                    self.validation_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not 8 <= len(self.idempotency_key) <= 128
            or not all(
                (
                    self.package_installed,
                    self.instance_created,
                    self.target_configured,
                    self.credential_references_assigned,
                    self.eligible_for_configuration_validation,
                    self.configuration_validated,
                    self.connectivity_evidence_verified,
                    self.eligible_for_capability_governance,
                )
            )
            or any(
                (
                    self.promotion_blocked,
                    self.credentials_resolved,
                    self.connector_enabled,
                    self.runtime_trust_granted,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector configuration validation record is invalid")
