from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
ENABLED_BOUNDED_CAPABILITY_INVOCATION_COMPLETED = "enabled_bounded_capability_invocation_completed"


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "bounded connector invocation identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class ConnectorBoundedInvocationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_source_schema: str
    required_source_state: str
    allowed_capability_classes: tuple[str, ...]
    maximum_authorization_age_minutes: int
    maximum_invocation_duration_seconds: int
    maximum_output_bytes: int
    maximum_observations: int
    required_adapter_id: str
    required_adapter_attestor_id: str
    required_receipt_schema: str
    required_assurance_level: AssuranceLevel
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
            self.required_source_state,
            self.required_adapter_id,
            self.required_adapter_attestor_id,
            self.required_receipt_schema,
            self.signed_by,
        )
        if (
            self.version != 1
            or self.allowed_capability_classes != ("C0", "C1")
            or not 1 <= self.maximum_authorization_age_minutes <= 60
            or not 1 <= self.maximum_invocation_duration_seconds <= 120
            or not 1 <= self.maximum_output_bytes <= 1_048_576
            or not 1 <= self.maximum_observations <= 1000
            or self.required_assurance_level is not AssuranceLevel.HARDWARE_BACKED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Bounded connector invocation policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorBoundedInvocationInstruction:
    invocation_id: str
    organization_id: str
    environment_id: str
    source_authorization_id: str
    source_authorization_digest: str
    package_digest: str
    connector_id: str
    instance_id: str
    capability_id: str
    capability_class: str
    required_permission: str
    invocation_profile_digest: str
    input_envelope_id: str
    input_envelope_digest: str
    input_schema_digest: str
    output_schema_digest: str
    result_policy_digest: str
    maximum_timeout_seconds: int
    maximum_output_bytes: int
    maximum_observations: int
    invocation_policy_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.invocation_id,
            self.organization_id,
            self.environment_id,
            self.source_authorization_id,
            self.connector_id,
            self.instance_id,
            self.capability_id,
            self.required_permission,
            self.input_envelope_id,
        )
        if (
            self.capability_class not in {"C0", "C1"}
            or not 1 <= self.maximum_timeout_seconds <= 120
            or not 1 <= self.maximum_output_bytes <= 1_048_576
            or not 1 <= self.maximum_observations <= 1000
            or not _digests(
                self.source_authorization_digest,
                self.package_digest,
                self.invocation_profile_digest,
                self.input_envelope_digest,
                self.input_schema_digest,
                self.output_schema_digest,
                self.result_policy_digest,
                self.invocation_policy_digest,
            )
        ):
            raise ValueError("Bounded connector invocation instruction is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorBoundedInvocationReceipt:
    invocation_id: str
    schema_version: str
    version: int
    adapter_id: str
    attested_by: str
    source_authorization_digest: str
    capability_id: str
    invocation_profile_digest: str
    input_envelope_digest: str
    result_schema_digest: str
    result_policy_digest: str
    normalized_redacted_result_digest: str
    observation_count: int
    output_bytes: int
    started_at: datetime
    completed_at: datetime
    target_connection_opened: bool
    capability_invoked_once: bool
    result_received: bool
    result_schema_validated: bool
    result_redacted: bool
    target_session_closed: bool
    delivery_channel_closed: bool
    lease_revocation_confirmed: bool
    target_disconnected: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.invocation_id,
            self.schema_version,
            self.adapter_id,
            self.attested_by,
            self.capability_id,
        )
        if (
            self.version != 1
            or not 0 <= self.observation_count <= 1000
            or not 0 <= self.output_bytes <= 1_048_576
            or self.started_at.tzinfo is None
            or self.completed_at.tzinfo is None
            or self.completed_at < self.started_at
            or not all(
                (
                    self.target_connection_opened,
                    self.capability_invoked_once,
                    self.result_received,
                    self.result_schema_validated,
                    self.result_redacted,
                    self.target_session_closed,
                    self.delivery_channel_closed,
                    self.lease_revocation_confirmed,
                    self.target_disconnected,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.source_authorization_digest,
                self.invocation_profile_digest,
                self.input_envelope_digest,
                self.result_schema_digest,
                self.result_policy_digest,
                self.normalized_redacted_result_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Bounded connector invocation receipt is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorInvocationConsumptionClaim:
    claim_id: str
    schema_version: str
    version: int
    source_authorization_id: str
    source_authorization_digest: str
    invocation_id: str
    organization_id: str
    environment_id: str
    claimed_by: str
    purpose: str
    claimed_at: datetime
    request_binding_digest: str
    idempotency_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.source_authorization_id,
            self.invocation_id,
            self.organization_id,
            self.environment_id,
            self.claimed_by,
        )
        if (
            self.version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_authorization_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Connector invocation consumption claim is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorBoundedInvocationRecord:
    invocation_id: str
    schema_version: str
    version: int
    consumption_claim_id: str
    source_authorization_id: str
    source_authorization_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    instance_id: str
    instance_key: str
    display_name: str
    capability_id: str
    capability_class: str
    required_permission: str
    invocation_profile_id: str
    invocation_profile_digest: str
    input_envelope_id: str
    input_envelope_digest: str
    input_schema_digest: str
    output_schema_digest: str
    result_policy_digest: str
    invocation_policy_id: str
    invocation_policy_digest: str
    invocation_policy_version: str
    invocation_adapter_id: str
    normalized_redacted_result_digest: str
    observation_count: int
    output_bytes: int
    instance_state: str
    invoked_by: str
    purpose: str
    started_at: datetime
    completed_at: datetime
    canonical_digest: str
    authorization_consumed: bool = True
    target_connection_opened: bool = True
    capability_invoked: bool = True
    result_received: bool = True
    result_validated: bool = True
    result_redacted: bool = True
    target_session_closed: bool = True
    delivery_channel_closed: bool = True
    lease_revocation_confirmed: bool = True
    target_connected: bool = False
    reusable_session_available: bool = False
    scheduled: bool = False
    evidence_ingested: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.invocation_id,
            self.schema_version,
            self.consumption_claim_id,
            self.source_authorization_id,
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
            self.invocation_policy_id,
            self.invocation_policy_version,
            self.invocation_adapter_id,
            self.instance_state,
            self.invoked_by,
        )
        if (
            self.version != 1
            or self.instance_state != ENABLED_BOUNDED_CAPABILITY_INVOCATION_COMPLETED
            or self.capability_class not in {"C0", "C1"}
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.started_at.tzinfo is None
            or self.completed_at.tzinfo is None
            or self.completed_at < self.started_at
            or not 0 <= self.observation_count <= 1000
            or not 0 <= self.output_bytes <= 1_048_576
            or not _digests(
                self.source_authorization_digest,
                self.package_digest,
                self.manifest_digest,
                self.invocation_profile_digest,
                self.input_envelope_digest,
                self.input_schema_digest,
                self.output_schema_digest,
                self.result_policy_digest,
                self.invocation_policy_digest,
                self.normalized_redacted_result_digest,
                self.canonical_digest,
            )
            or not all(
                (
                    self.authorization_consumed,
                    self.target_connection_opened,
                    self.capability_invoked,
                    self.result_received,
                    self.result_validated,
                    self.result_redacted,
                    self.target_session_closed,
                    self.delivery_channel_closed,
                    self.lease_revocation_confirmed,
                )
            )
            or any(
                (
                    self.target_connected,
                    self.reusable_session_available,
                    self.scheduled,
                    self.evidence_ingested,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Bounded connector invocation record is invalid")
