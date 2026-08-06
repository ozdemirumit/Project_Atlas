from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
ENABLED_RUNTIME_TRUSTED = "enabled_runtime_trusted"


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeTrustProfileSnapshot:
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
    source_enablement_digest: str
    capability_profile_digest: str
    sdk_profile: str
    runner_runtime_id: str
    runner_pool_id: str
    runner_image_digest: str
    runner_workload_identity_id: str
    isolation_profile_id: str
    filesystem_policy_id: str
    egress_policy_id: str
    secret_delivery_policy_id: str
    telemetry_policy_id: str
    resource_limit_profile_id: str
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
            self.sdk_profile,
            self.runner_runtime_id,
            self.runner_pool_id,
            self.runner_workload_identity_id,
            self.isolation_profile_id,
            self.filesystem_policy_id,
            self.egress_policy_id,
            self.secret_delivery_policy_id,
            self.telemetry_policy_id,
            self.resource_limit_profile_id,
            self.signed_by,
        ):
            validate_stable_identifier(value, "connector runtime trust profile identifier")
        if (
            self.version != 1
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.package_digest,
                    self.manifest_digest,
                    self.source_enablement_digest,
                    self.capability_profile_digest,
                    self.runner_image_digest,
                    self.canonical_digest,
                )
            )
        ):
            raise ValueError("Connector runtime trust profile contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeTrustPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_enablement_schema: str
    required_profile_schema: str
    required_profile_signer_id: str
    allowed_sdk_profiles: tuple[str, ...]
    allowed_runner_runtime_ids: tuple[str, ...]
    allowed_runner_pool_ids: tuple[str, ...]
    allowed_runner_image_digests: tuple[str, ...]
    required_runner_workload_identity_id: str
    required_isolation_profile_id: str
    required_filesystem_policy_id: str
    required_egress_policy_id: str
    required_secret_delivery_policy_id: str
    required_telemetry_policy_id: str
    required_resource_limit_profile_id: str
    maximum_enablement_age_hours: int
    maximum_profile_age_hours: int
    required_assurance_level: AssuranceLevel
    required_effective_state: str
    trust_grant_schema: str
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
            self.required_enablement_schema,
            self.required_profile_schema,
            self.required_profile_signer_id,
            *self.allowed_sdk_profiles,
            *self.allowed_runner_runtime_ids,
            *self.allowed_runner_pool_ids,
            self.required_runner_workload_identity_id,
            self.required_isolation_profile_id,
            self.required_filesystem_policy_id,
            self.required_egress_policy_id,
            self.required_secret_delivery_policy_id,
            self.required_telemetry_policy_id,
            self.required_resource_limit_profile_id,
            self.required_effective_state,
            self.trust_grant_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "connector runtime trust policy identifier")
        identifier_sets = (
            self.allowed_sdk_profiles,
            self.allowed_runner_runtime_ids,
            self.allowed_runner_pool_ids,
        )
        if (
            self.version != 1
            or any(not items or items != tuple(sorted(set(items))) for items in identifier_sets)
            or not self.allowed_runner_image_digests
            or self.allowed_runner_image_digests
            != tuple(sorted(set(self.allowed_runner_image_digests)))
            or any(_DIGEST.fullmatch(item) is None for item in self.allowed_runner_image_digests)
            or not 1 <= self.maximum_enablement_age_hours <= 8760
            or not 1 <= self.maximum_profile_age_hours <= 8760
            or self.required_assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
            or self.required_effective_state != ENABLED_RUNTIME_TRUSTED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Connector runtime trust policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeTrustGrantRecord:
    grant_id: str
    schema_version: str
    version: int
    source_enablement_id: str
    source_enablement_digest: str
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
    capability_count: int
    runtime_profile_id: str
    runtime_profile_digest: str
    sdk_profile: str
    runner_runtime_id: str
    runner_pool_id: str
    runner_image_digest: str
    runner_workload_identity_id: str
    isolation_profile_id: str
    filesystem_policy_id: str
    egress_policy_id: str
    secret_delivery_policy_id: str
    telemetry_policy_id: str
    resource_limit_profile_id: str
    trust_policy_id: str
    trust_policy_digest: str
    trust_policy_version: str
    trust_version: int
    instance_state: str
    granted_by: str
    purpose: str
    granted_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    configuration_validated: bool = True
    connectivity_evidence_verified: bool = True
    capability_governance_applied: bool = True
    connector_enabled: bool = True
    eligible_for_runtime_trust: bool = True
    runtime_boundary_bound: bool = True
    runtime_trust_granted: bool = True
    eligible_for_secret_brokerage: bool = True
    promotion_blocked: bool = False
    runner_started: bool = False
    package_loaded: bool = False
    credential_resolution_authorized: bool = False
    credentials_resolved: bool = False
    target_connection_authorized: bool = False
    capability_invocation_authorized: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.grant_id,
            self.schema_version,
            self.source_enablement_id,
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
            self.runtime_profile_id,
            self.sdk_profile,
            self.runner_runtime_id,
            self.runner_pool_id,
            self.runner_workload_identity_id,
            self.isolation_profile_id,
            self.filesystem_policy_id,
            self.egress_policy_id,
            self.secret_delivery_policy_id,
            self.telemetry_policy_id,
            self.resource_limit_profile_id,
            self.trust_policy_id,
            self.trust_policy_version,
            self.instance_state,
            self.granted_by,
        ):
            validate_stable_identifier(value, "connector runtime trust grant identifier")
        if (
            self.version != 1
            or self.trust_version != 1
            or not 1 <= self.capability_count <= 100
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.granted_at.tzinfo is None
            or self.instance_state != ENABLED_RUNTIME_TRUSTED
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.source_enablement_digest,
                    self.package_digest,
                    self.manifest_digest,
                    self.target_profile_digest,
                    self.credential_profile_digest,
                    self.capability_profile_digest,
                    self.runtime_profile_digest,
                    self.runner_image_digest,
                    self.trust_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not 8 <= len(self.idempotency_key) <= 128
            or not all(
                (
                    self.configuration_validated,
                    self.connectivity_evidence_verified,
                    self.capability_governance_applied,
                    self.connector_enabled,
                    self.eligible_for_runtime_trust,
                    self.runtime_boundary_bound,
                    self.runtime_trust_granted,
                    self.eligible_for_secret_brokerage,
                )
            )
            or any(
                (
                    self.promotion_blocked,
                    self.runner_started,
                    self.package_loaded,
                    self.credential_resolution_authorized,
                    self.credentials_resolved,
                    self.target_connection_authorized,
                    self.capability_invocation_authorized,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector runtime trust grant is invalid")
