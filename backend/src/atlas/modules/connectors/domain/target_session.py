from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
ENABLED_TARGET_SESSION_VERIFIED = "enabled_target_session_verified"


def _validate_ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "connector target session identifier")


@dataclass(frozen=True, slots=True)
class ConnectorTargetConnectivityCheckResult:
    check_id: str
    outcome: str

    def __post_init__(self) -> None:
        _validate_ids(self.check_id, self.outcome)
        if self.outcome != "connectivity.passed":
            raise ValueError("Connector target connectivity check did not pass")


@dataclass(frozen=True, slots=True)
class ConnectorTargetSessionProfileSnapshot:
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
    source_runtime_activation_digest: str
    target_profile_digest: str
    expected_target_product: str
    expected_target_identity_digest: str
    protocol_classification: str
    tls_policy_digest: str
    certificate_policy_digest: str
    network_path_policy_digest: str
    workload_identity_digest: str
    credential_profile_digest: str
    delivery_policy_id: str
    lease_policy_id: str
    session_adapter_id: str
    session_adapter_attestor_id: str
    session_timeout_seconds: int
    connectivity_check_ids: tuple[str, ...]
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
            self.protocol_classification,
            self.delivery_policy_id,
            self.lease_policy_id,
            self.session_adapter_id,
            self.session_adapter_attestor_id,
            *self.connectivity_check_ids,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= len(self.expected_target_product) <= 160
            or not 1 <= self.session_timeout_seconds <= 120
            or not self.connectivity_check_ids
            or self.connectivity_check_ids != tuple(sorted(set(self.connectivity_check_ids)))
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.package_digest,
                    self.manifest_digest,
                    self.source_runtime_activation_digest,
                    self.target_profile_digest,
                    self.expected_target_identity_digest,
                    self.tls_policy_digest,
                    self.certificate_policy_digest,
                    self.network_path_policy_digest,
                    self.workload_identity_digest,
                    self.credential_profile_digest,
                    self.canonical_digest,
                )
            )
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("Connector target session profile contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorTargetSessionPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_activation_schema: str
    required_profile_schema: str
    required_profile_signer_id: str
    allowed_session_adapter_ids: tuple[str, ...]
    required_session_adapter_attestor_id: str
    required_protocol_classification: str
    required_tls_classification: str
    required_delivery_policy_id: str
    required_lease_policy_id: str
    maximum_session_timeout_seconds: int
    required_connectivity_check_ids: tuple[str, ...]
    maximum_activation_age_hours: int
    maximum_profile_age_hours: int
    required_assurance_level: AssuranceLevel
    required_source_state: str
    verification_schema: str
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
            self.required_activation_schema,
            self.required_profile_schema,
            self.required_profile_signer_id,
            *self.allowed_session_adapter_ids,
            self.required_session_adapter_attestor_id,
            self.required_protocol_classification,
            self.required_tls_classification,
            self.required_delivery_policy_id,
            self.required_lease_policy_id,
            *self.required_connectivity_check_ids,
            self.required_source_state,
            self.verification_schema,
            self.signed_by,
        )
        if (
            self.version != 1
            or not self.allowed_session_adapter_ids
            or self.allowed_session_adapter_ids
            != tuple(sorted(set(self.allowed_session_adapter_ids)))
            or not self.required_connectivity_check_ids
            or self.required_connectivity_check_ids
            != tuple(sorted(set(self.required_connectivity_check_ids)))
            or not 1 <= self.maximum_session_timeout_seconds <= 120
            or not 1 <= self.maximum_activation_age_hours <= 8760
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
            raise ValueError("Connector target session policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorTargetSessionInstruction:
    verification_id: str
    organization_id: str
    environment_id: str
    source_runtime_activation_id: str
    source_runtime_activation_digest: str
    package_digest: str
    session_profile_digest: str
    session_policy_digest: str
    session_adapter_id: str
    expected_target_identity_digest: str
    protocol_classification: str
    session_timeout_seconds: int
    connectivity_check_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_ids(
            self.verification_id,
            self.organization_id,
            self.environment_id,
            self.source_runtime_activation_id,
            self.session_adapter_id,
            self.protocol_classification,
            *self.connectivity_check_ids,
        )
        if not 1 <= self.session_timeout_seconds <= 120 or any(
            _DIGEST.fullmatch(item) is None
            for item in (
                self.source_runtime_activation_digest,
                self.package_digest,
                self.session_profile_digest,
                self.session_policy_digest,
                self.expected_target_identity_digest,
            )
        ):
            raise ValueError("Connector target session instruction is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorTargetSessionReceipt:
    receipt_id: str
    schema_version: str
    version: int
    verification_id: str
    organization_id: str
    environment_id: str
    source_runtime_activation_digest: str
    package_digest: str
    session_profile_digest: str
    session_policy_digest: str
    session_adapter_id: str
    target_identity_digest: str
    protocol_classification: str
    tls_classification: str
    connectivity_check_results: tuple[ConnectorTargetConnectivityCheckResult, ...]
    verified_at: datetime
    lease_delivery_confirmed: bool
    authentication_verified: bool
    target_identity_verified: bool
    read_only_privilege_verified: bool
    target_session_established: bool
    target_session_closed: bool
    delivery_channel_closed: bool
    lease_revocation_confirmed: bool
    capability_invoked: bool
    signed_by: str
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _validate_ids(
            self.receipt_id,
            self.schema_version,
            self.verification_id,
            self.organization_id,
            self.environment_id,
            self.session_adapter_id,
            self.protocol_classification,
            self.tls_classification,
            self.signed_by,
        )
        if (
            self.version != 1
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.source_runtime_activation_digest,
                    self.package_digest,
                    self.session_profile_digest,
                    self.session_policy_digest,
                    self.target_identity_digest,
                    self.canonical_digest,
                )
            )
            or not self.connectivity_check_results
            or self.verified_at.tzinfo is None
            or not all(
                (
                    self.lease_delivery_confirmed,
                    self.authentication_verified,
                    self.target_identity_verified,
                    self.read_only_privilege_verified,
                    self.target_session_established,
                    self.target_session_closed,
                    self.delivery_channel_closed,
                    self.lease_revocation_confirmed,
                    self.signature_verified,
                )
            )
            or self.capability_invoked
        ):
            raise ValueError("Connector target session receipt is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorTargetSessionVerificationRecord:
    verification_id: str
    schema_version: str
    version: int
    source_runtime_activation_id: str
    source_runtime_activation_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    target_profile_digest: str
    target_identity_digest: str
    expected_target_product: str
    protocol_classification: str
    tls_classification: str
    session_profile_id: str
    session_profile_digest: str
    session_policy_id: str
    session_policy_digest: str
    session_policy_version: str
    session_adapter_id: str
    connectivity_check_results: tuple[ConnectorTargetConnectivityCheckResult, ...]
    instance_state: str
    verified_by: str
    purpose: str
    verified_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    runtime_health_verified: bool = True
    secret_brokerage_governed: bool = True
    target_connection_authorized: bool = True
    target_connectivity_verified: bool = True
    target_identity_verified: bool = True
    read_only_session_verified: bool = True
    target_session_established: bool = True
    target_session_closed: bool = True
    delivery_channel_closed: bool = True
    lease_revocation_confirmed: bool = True
    eligible_for_capability_invocation_governance: bool = True
    target_connected: bool = False
    capability_invocation_authorized: bool = False
    capability_invoked: bool = False
    scheduled: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _validate_ids(
            self.verification_id,
            self.schema_version,
            self.source_runtime_activation_id,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.release_version,
            self.instance_id,
            self.instance_key,
            self.protocol_classification,
            self.tls_classification,
            self.session_profile_id,
            self.session_policy_id,
            self.session_policy_version,
            self.session_adapter_id,
            self.instance_state,
            self.verified_by,
        )
        if (
            self.version != 1
            or self.instance_state != ENABLED_TARGET_SESSION_VERIFIED
            or not 1 <= len(self.expected_target_product) <= 160
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.verified_at.tzinfo is None
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.source_runtime_activation_digest,
                    self.package_digest,
                    self.manifest_digest,
                    self.target_profile_digest,
                    self.target_identity_digest,
                    self.session_profile_digest,
                    self.session_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not self.connectivity_check_results
            or not all(
                (
                    self.runtime_health_verified,
                    self.secret_brokerage_governed,
                    self.target_connection_authorized,
                    self.target_connectivity_verified,
                    self.target_identity_verified,
                    self.read_only_session_verified,
                    self.target_session_established,
                    self.target_session_closed,
                    self.delivery_channel_closed,
                    self.lease_revocation_confirmed,
                    self.eligible_for_capability_invocation_governance,
                )
            )
            or any(
                (
                    self.target_connected,
                    self.capability_invocation_authorized,
                    self.capability_invoked,
                    self.scheduled,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector target session verification record is invalid")
