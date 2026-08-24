from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
ENABLED_RUNTIME_HEALTHY = "enabled_runtime_healthy"


def _validate_ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "connector runtime activation identifier")


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeHealthProbeResult:
    probe_id: str
    outcome: str

    def __post_init__(self) -> None:
        _validate_ids(self.probe_id, self.outcome)
        if self.outcome != "health.passed":
            raise ValueError("Connector runtime health probe did not pass")


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeActivationProfileSnapshot:
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
    source_brokerage_authorization_digest: str
    runtime_profile_digest: str
    runner_identity_digest: str
    image_digest: str
    workload_identity_digest: str
    isolation_profile_digest: str
    filesystem_policy_digest: str
    egress_policy_digest: str
    delivery_policy_id: str
    lease_policy_id: str
    activation_adapter_id: str
    activation_adapter_attestor_id: str
    startup_timeout_seconds: int
    health_probe_ids: tuple[str, ...]
    telemetry_policy_digest: str
    resource_policy_digest: str
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _validate_ids(
            self.profile_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.release_version,
            self.instance_id,
            self.delivery_policy_id,
            self.lease_policy_id,
            self.activation_adapter_id,
            self.activation_adapter_attestor_id,
            *self.health_probe_ids,
            self.signed_by,
        )
        digests = (
            self.package_digest,
            self.manifest_digest,
            self.source_brokerage_authorization_digest,
            self.runtime_profile_digest,
            self.runner_identity_digest,
            self.image_digest,
            self.workload_identity_digest,
            self.isolation_profile_digest,
            self.filesystem_policy_digest,
            self.egress_policy_digest,
            self.telemetry_policy_digest,
            self.resource_policy_digest,
            self.canonical_digest,
        )
        if (
            self.version != 1
            or not 1 <= self.startup_timeout_seconds <= 300
            or not self.health_probe_ids
            or self.health_probe_ids != tuple(sorted(set(self.health_probe_ids)))
            or any(_DIGEST.fullmatch(item) is None for item in digests)
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("Connector runtime activation profile contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeActivationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_brokerage_schema: str
    required_profile_schema: str
    required_profile_signer_id: str
    allowed_activation_adapter_ids: tuple[str, ...]
    required_activation_adapter_attestor_id: str
    required_delivery_policy_id: str
    required_lease_policy_id: str
    maximum_startup_timeout_seconds: int
    required_health_probe_ids: tuple[str, ...]
    maximum_brokerage_age_hours: int
    maximum_profile_age_hours: int
    required_assurance_level: AssuranceLevel
    required_source_state: str
    activation_schema: str
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _validate_ids(
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.required_brokerage_schema,
            self.required_profile_schema,
            self.required_profile_signer_id,
            *self.allowed_activation_adapter_ids,
            self.required_activation_adapter_attestor_id,
            self.required_delivery_policy_id,
            self.required_lease_policy_id,
            *self.required_health_probe_ids,
            self.required_source_state,
            self.activation_schema,
            self.signed_by,
        )
        if (
            self.version != 1
            or not self.allowed_activation_adapter_ids
            or self.allowed_activation_adapter_ids
            != tuple(sorted(set(self.allowed_activation_adapter_ids)))
            or not self.required_health_probe_ids
            or self.required_health_probe_ids != tuple(sorted(set(self.required_health_probe_ids)))
            or not 1 <= self.maximum_startup_timeout_seconds <= 300
            or not 1 <= self.maximum_brokerage_age_hours <= 8760
            or not 1 <= self.maximum_profile_age_hours <= 8760
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Connector runtime activation policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeActivationInstruction:
    activation_id: str
    activation_attempt_id: str
    organization_id: str
    environment_id: str
    source_brokerage_authorization_id: str
    source_brokerage_authorization_digest: str
    package_digest: str
    activation_profile_digest: str
    activation_policy_digest: str
    activation_adapter_id: str
    runner_identity_digest: str
    image_digest: str
    workload_identity_digest: str
    startup_timeout_seconds: int
    health_probe_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_ids(
            self.activation_id,
            self.activation_attempt_id,
            self.organization_id,
            self.environment_id,
            self.source_brokerage_authorization_id,
            self.activation_adapter_id,
            *self.health_probe_ids,
        )
        if not 1 <= self.startup_timeout_seconds <= 300 or any(
            _DIGEST.fullmatch(item) is None
            for item in (
                self.source_brokerage_authorization_digest,
                self.package_digest,
                self.activation_profile_digest,
                self.activation_policy_digest,
                self.runner_identity_digest,
                self.image_digest,
                self.workload_identity_digest,
            )
        ):
            raise ValueError("Connector runtime activation instruction is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeActivationClaim:
    activation_attempt_id: str
    activation_id: str
    source_brokerage_authorization_id: str
    organization_id: str
    environment_id: str
    activated_by_digest: str
    idempotency_digest: str
    replay_digest: str
    claimed_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _validate_ids(
            self.activation_attempt_id,
            self.activation_id,
            self.source_brokerage_authorization_id,
            self.organization_id,
            self.environment_id,
        )
        if (
            self.claimed_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.claimed_at
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.activated_by_digest,
                    self.idempotency_digest,
                    self.replay_digest,
                    self.canonical_digest,
                )
            )
        ):
            raise ValueError("Connector runtime activation claim is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeActivationReceipt:
    receipt_id: str
    schema_version: str
    version: int
    activation_id: str
    activation_attempt_id: str
    organization_id: str
    environment_id: str
    source_brokerage_authorization_digest: str
    package_digest: str
    activation_profile_digest: str
    activation_policy_digest: str
    activation_adapter_id: str
    runner_identity_digest: str
    image_digest: str
    workload_identity_digest: str
    health_probe_results: tuple[ConnectorRuntimeHealthProbeResult, ...]
    started_at: datetime
    healthy_at: datetime
    lease_delivery_confirmed: bool
    delivery_channel_closed: bool
    lease_revocation_confirmed: bool
    runner_started: bool
    package_loaded: bool
    runtime_healthy: bool
    target_network_used: bool
    capability_invoked: bool
    signed_by: str
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _validate_ids(
            self.receipt_id,
            self.schema_version,
            self.activation_id,
            self.activation_attempt_id,
            self.organization_id,
            self.environment_id,
            self.activation_adapter_id,
            self.signed_by,
        )
        digests = (
            self.source_brokerage_authorization_digest,
            self.package_digest,
            self.activation_profile_digest,
            self.activation_policy_digest,
            self.runner_identity_digest,
            self.image_digest,
            self.workload_identity_digest,
            self.canonical_digest,
        )
        if (
            self.version != 1
            or any(_DIGEST.fullmatch(item) is None for item in digests)
            or not self.health_probe_results
            or self.started_at.tzinfo is None
            or self.healthy_at.tzinfo is None
            or self.healthy_at < self.started_at
            or not all(
                (
                    self.lease_delivery_confirmed,
                    self.delivery_channel_closed,
                    self.lease_revocation_confirmed,
                    self.runner_started,
                    self.package_loaded,
                    self.runtime_healthy,
                    self.signature_verified,
                )
            )
            or self.target_network_used
            or self.capability_invoked
        ):
            raise ValueError("Connector runtime activation receipt is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeActivationRecord:
    activation_id: str
    schema_version: str
    version: int
    source_brokerage_authorization_id: str
    source_brokerage_authorization_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    runtime_profile_digest: str
    runner_identity_digest: str
    image_digest: str
    workload_identity_digest: str
    activation_profile_id: str
    activation_profile_digest: str
    activation_policy_id: str
    activation_policy_digest: str
    activation_policy_version: str
    activation_adapter_id: str
    health_probe_results: tuple[ConnectorRuntimeHealthProbeResult, ...]
    instance_state: str
    activated_by: str
    purpose: str
    activated_at: datetime
    healthy_at: datetime
    canonical_digest: str
    replay_digest: str
    idempotency_digest: str
    runtime_boundary_bound: bool = True
    runtime_trust_granted: bool = True
    secret_brokerage_governed: bool = True
    credential_resolution_authorized: bool = True
    secret_lease_issued: bool = True
    credentials_resolved: bool = True
    runner_started: bool = True
    package_loaded: bool = True
    runtime_health_verified: bool = True
    lease_delivery_completed: bool = True
    delivery_channel_closed: bool = True
    lease_revocation_confirmed: bool = True
    eligible_for_target_session_authorization: bool = True
    target_connected: bool = False
    target_connection_authorized: bool = False
    capability_invocation_authorized: bool = False
    capability_invoked: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _validate_ids(
            self.activation_id,
            self.schema_version,
            self.source_brokerage_authorization_id,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.release_version,
            self.instance_id,
            self.instance_key,
            self.activation_profile_id,
            self.activation_policy_id,
            self.activation_policy_version,
            self.activation_adapter_id,
            self.instance_state,
            self.activated_by,
        )
        digests = (
            self.source_brokerage_authorization_digest,
            self.package_digest,
            self.manifest_digest,
            self.runtime_profile_digest,
            self.runner_identity_digest,
            self.image_digest,
            self.workload_identity_digest,
            self.activation_profile_digest,
            self.activation_policy_digest,
            self.canonical_digest,
            self.replay_digest,
            self.idempotency_digest,
        )
        if (
            self.version != 1
            or self.instance_state != ENABLED_RUNTIME_HEALTHY
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.activated_at.tzinfo is None
            or self.healthy_at.tzinfo is None
            or self.healthy_at < self.activated_at
            or any(_DIGEST.fullmatch(item) is None for item in digests)
            or not self.health_probe_results
            or not all(
                (
                    self.runtime_boundary_bound,
                    self.runtime_trust_granted,
                    self.secret_brokerage_governed,
                    self.credential_resolution_authorized,
                    self.secret_lease_issued,
                    self.credentials_resolved,
                    self.runner_started,
                    self.package_loaded,
                    self.runtime_health_verified,
                    self.lease_delivery_completed,
                    self.delivery_channel_closed,
                    self.lease_revocation_confirmed,
                    self.eligible_for_target_session_authorization,
                )
            )
            or any(
                (
                    self.target_connected,
                    self.target_connection_authorized,
                    self.capability_invocation_authorized,
                    self.capability_invoked,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector runtime activation record is invalid")
