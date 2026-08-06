from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
ENABLED_CAPABILITY_INVOCATION_GOVERNED = "enabled_capability_invocation_governed"


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "connector invocation authorization identifier")


@dataclass(frozen=True, slots=True)
class ConnectorInvocationProfileSnapshot:
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
    source_target_session_digest: str
    target_profile_digest: str
    target_identity_digest: str
    capability_id: str
    capability_class: str
    required_permission: str
    input_schema_digest: str
    output_schema_digest: str
    input_envelope_schema: str
    result_policy_digest: str
    maximum_timeout_seconds: int
    maximum_output_bytes: int
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.profile_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.release_version,
            self.instance_id,
            self.capability_id,
            self.required_permission,
            self.input_envelope_schema,
            self.signed_by,
        )
        if (
            self.version != 1
            or self.capability_class not in {"C0", "C1"}
            or not 1 <= self.maximum_timeout_seconds <= 120
            or not 1 <= self.maximum_output_bytes <= 1_048_576
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.package_digest,
                    self.manifest_digest,
                    self.source_target_session_digest,
                    self.target_profile_digest,
                    self.target_identity_digest,
                    self.input_schema_digest,
                    self.output_schema_digest,
                    self.result_policy_digest,
                    self.canonical_digest,
                )
            )
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("Connector invocation profile contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorInvocationInputEnvelopeSnapshot:
    envelope_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    capability_id: str
    invocation_profile_digest: str
    input_schema_digest: str
    normalized_input_digest: str
    field_count: int
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.envelope_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.capability_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 0 <= self.field_count <= 64
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.invocation_profile_digest,
                    self.input_schema_digest,
                    self.normalized_input_digest,
                    self.canonical_digest,
                )
            )
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("Connector invocation input envelope contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorInvocationAuthorizationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_source_schema: str
    required_profile_schema: str
    required_envelope_schema: str
    required_profile_signer_id: str
    required_envelope_signer_id: str
    allowed_capability_classes: tuple[str, ...]
    maximum_timeout_seconds: int
    maximum_output_bytes: int
    maximum_source_age_hours: int
    maximum_profile_age_hours: int
    maximum_envelope_age_hours: int
    authorization_lifetime_minutes: int
    required_assurance_level: AssuranceLevel
    required_source_state: str
    authorization_schema: str
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.required_source_schema,
            self.required_profile_schema,
            self.required_envelope_schema,
            self.required_profile_signer_id,
            self.required_envelope_signer_id,
            self.required_source_state,
            self.authorization_schema,
            self.signed_by,
        )
        if (
            self.version != 1
            or self.allowed_capability_classes != ("C0", "C1")
            or not 1 <= self.maximum_timeout_seconds <= 120
            or not 1 <= self.maximum_output_bytes <= 1_048_576
            or not 1 <= self.maximum_source_age_hours <= 8760
            or not 1 <= self.maximum_profile_age_hours <= 8760
            or not 1 <= self.maximum_envelope_age_hours <= 8760
            or not 1 <= self.authorization_lifetime_minutes <= 60
            or self.required_assurance_level is not AssuranceLevel.HARDWARE_BACKED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Connector invocation authorization policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorInvocationAuthorizationRecord:
    authorization_id: str
    schema_version: str
    version: int
    source_target_session_verification_id: str
    source_target_session_digest: str
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
    capability_id: str
    capability_class: str
    required_permission: str
    invocation_profile_id: str
    invocation_profile_digest: str
    input_envelope_id: str
    input_envelope_digest: str
    input_envelope_schema: str
    normalized_input_digest: str
    input_schema_digest: str
    output_schema_digest: str
    result_policy_digest: str
    maximum_timeout_seconds: int
    maximum_output_bytes: int
    authorization_policy_id: str
    authorization_policy_digest: str
    authorization_policy_version: str
    instance_state: str
    authorized_by: str
    purpose: str
    authorized_at: datetime
    expires_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    target_session_verified: bool = True
    capability_enabled: bool = True
    capability_permission_verified: bool = True
    capability_invocation_authorized: bool = True
    eligible_for_bounded_capability_invocation: bool = True
    single_use: bool = True
    renewable: bool = False
    consumed: bool = False
    target_connected: bool = False
    capability_invoked: bool = False
    scheduled: bool = False
    result_received: bool = False
    result_validated: bool = False
    evidence_ingested: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.authorization_id,
            self.schema_version,
            self.source_target_session_verification_id,
            self.organization_id,
            self.environment_id,
            self.connector_id,
            self.release_version,
            self.instance_id,
            self.instance_key,
            self.capability_id,
            self.required_permission,
            self.invocation_profile_id,
            self.input_envelope_id,
            self.input_envelope_schema,
            self.authorization_policy_id,
            self.authorization_policy_version,
            self.instance_state,
            self.authorized_by,
        )
        if (
            self.version != 1
            or self.instance_state != ENABLED_CAPABILITY_INVOCATION_GOVERNED
            or self.capability_class not in {"C0", "C1"}
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.authorized_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.authorized_at
            or not 1 <= self.maximum_timeout_seconds <= 120
            or not 1 <= self.maximum_output_bytes <= 1_048_576
            or any(
                _DIGEST.fullmatch(item) is None
                for item in (
                    self.source_target_session_digest,
                    self.package_digest,
                    self.manifest_digest,
                    self.target_profile_digest,
                    self.target_identity_digest,
                    self.invocation_profile_digest,
                    self.input_envelope_digest,
                    self.normalized_input_digest,
                    self.input_schema_digest,
                    self.output_schema_digest,
                    self.result_policy_digest,
                    self.authorization_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not all(
                (
                    self.target_session_verified,
                    self.capability_enabled,
                    self.capability_permission_verified,
                    self.capability_invocation_authorized,
                    self.eligible_for_bounded_capability_invocation,
                    self.single_use,
                )
            )
            or any(
                (
                    self.renewable,
                    self.consumed,
                    self.target_connected,
                    self.capability_invoked,
                    self.scheduled,
                    self.result_received,
                    self.result_validated,
                    self.evidence_ingested,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector invocation authorization record is invalid")
