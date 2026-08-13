from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
ENABLED_SECRET_BROKERAGE_GOVERNED = "enabled_secret_brokerage_governed"


@dataclass(frozen=True, slots=True)
class ConnectorSecretBrokerageProfileSnapshot:
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
    source_runtime_trust_digest: str
    credential_profile_digest: str
    runtime_profile_digest: str
    runner_workload_identity_id: str
    broker_id: str
    secret_store_profile_id: str
    delivery_policy_id: str
    lease_policy_id: str
    maximum_lease_seconds: int
    revocation_policy_id: str
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
            self.runner_workload_identity_id,
            self.broker_id,
            self.secret_store_profile_id,
            self.delivery_policy_id,
            self.lease_policy_id,
            self.revocation_policy_id,
            self.signed_by,
        ):
            validate_stable_identifier(value, "connector secret brokerage profile identifier")
        if (
            self.version != 1
            or not 1 <= self.maximum_lease_seconds <= 900
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.package_digest,
                    self.manifest_digest,
                    self.source_runtime_trust_digest,
                    self.credential_profile_digest,
                    self.runtime_profile_digest,
                    self.canonical_digest,
                )
            )
        ):
            raise ValueError("Connector secret brokerage profile contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorSecretBrokeragePolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_runtime_trust_schema: str
    required_profile_schema: str
    required_profile_signer_id: str
    allowed_broker_ids: tuple[str, ...]
    allowed_secret_store_profile_ids: tuple[str, ...]
    required_delivery_policy_id: str
    required_lease_policy_id: str
    maximum_lease_seconds: int
    required_revocation_policy_id: str
    required_privilege_class: str
    required_rotation_state: str
    required_revocation_state: str
    minimum_rotation_window_hours: int
    maximum_runtime_trust_age_hours: int
    maximum_profile_age_hours: int
    required_assurance_level: AssuranceLevel
    required_effective_state: str
    authorization_schema: str
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
            self.required_runtime_trust_schema,
            self.required_profile_schema,
            self.required_profile_signer_id,
            *self.allowed_broker_ids,
            *self.allowed_secret_store_profile_ids,
            self.required_delivery_policy_id,
            self.required_lease_policy_id,
            self.required_revocation_policy_id,
            self.required_privilege_class,
            self.required_rotation_state,
            self.required_revocation_state,
            self.required_effective_state,
            self.authorization_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "connector secret brokerage policy identifier")
        if (
            self.version != 1
            or not self.allowed_broker_ids
            or self.allowed_broker_ids != tuple(sorted(set(self.allowed_broker_ids)))
            or not self.allowed_secret_store_profile_ids
            or self.allowed_secret_store_profile_ids
            != tuple(sorted(set(self.allowed_secret_store_profile_ids)))
            or not 1 <= self.maximum_lease_seconds <= 900
            or not 1 <= self.minimum_rotation_window_hours <= 8760
            or not 1 <= self.maximum_runtime_trust_age_hours <= 8760
            or not 1 <= self.maximum_profile_age_hours <= 8760
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or self.required_effective_state != ENABLED_SECRET_BROKERAGE_GOVERNED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Connector secret brokerage policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorSecretBrokerageAuthorizationRecord:
    authorization_id: str
    schema_version: str
    version: int
    source_runtime_trust_grant_id: str
    source_runtime_trust_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    credential_profile_id: str
    credential_profile_digest: str
    credential_class: str
    authentication_method: str
    privilege_class: str
    rotation_state: str
    revocation_state: str
    next_rotation_at: datetime
    runtime_profile_id: str
    runtime_profile_digest: str
    runner_workload_identity_id: str
    secret_delivery_policy_id: str
    brokerage_profile_id: str
    brokerage_profile_digest: str
    broker_id: str
    secret_store_profile_id: str
    delivery_policy_id: str
    lease_policy_id: str
    maximum_lease_seconds: int
    revocation_policy_id: str
    brokerage_policy_id: str
    brokerage_policy_digest: str
    brokerage_policy_version: str
    authorization_version: int
    instance_state: str
    authorized_by: str
    purpose: str
    authorized_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    runtime_boundary_bound: bool = True
    runtime_trust_granted: bool = True
    eligible_for_secret_brokerage: bool = True
    secret_brokerage_governed: bool = True
    credential_resolution_authorized: bool = True
    eligible_for_runtime_activation: bool = True
    promotion_blocked: bool = False
    secret_lease_issued: bool = False
    credentials_resolved: bool = False
    runner_started: bool = False
    package_loaded: bool = False
    target_connection_authorized: bool = False
    capability_invocation_authorized: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.authorization_id,
            self.schema_version,
            self.source_runtime_trust_grant_id,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.release_version,
            self.instance_id,
            self.instance_key,
            self.credential_profile_id,
            self.credential_class,
            self.authentication_method,
            self.privilege_class,
            self.rotation_state,
            self.revocation_state,
            self.runtime_profile_id,
            self.runner_workload_identity_id,
            self.secret_delivery_policy_id,
            self.brokerage_profile_id,
            self.broker_id,
            self.secret_store_profile_id,
            self.delivery_policy_id,
            self.lease_policy_id,
            self.revocation_policy_id,
            self.brokerage_policy_id,
            self.brokerage_policy_version,
            self.instance_state,
            self.authorized_by,
        ):
            validate_stable_identifier(value, "connector secret brokerage record identifier")
        if (
            self.version != 1
            or self.authorization_version != 1
            or not 1 <= self.maximum_lease_seconds <= 900
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.authorized_at.tzinfo is None
            or self.next_rotation_at.tzinfo is None
            or self.instance_state != ENABLED_SECRET_BROKERAGE_GOVERNED
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.source_runtime_trust_digest,
                    self.package_digest,
                    self.manifest_digest,
                    self.credential_profile_digest,
                    self.runtime_profile_digest,
                    self.brokerage_profile_digest,
                    self.brokerage_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not all(
                (
                    self.runtime_boundary_bound,
                    self.runtime_trust_granted,
                    self.eligible_for_secret_brokerage,
                    self.secret_brokerage_governed,
                    self.credential_resolution_authorized,
                    self.eligible_for_runtime_activation,
                )
            )
            or any(
                (
                    self.promotion_blocked,
                    self.secret_lease_issued,
                    self.credentials_resolved,
                    self.runner_started,
                    self.package_loaded,
                    self.target_connection_authorized,
                    self.capability_invocation_authorized,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector secret brokerage authorization is invalid")
