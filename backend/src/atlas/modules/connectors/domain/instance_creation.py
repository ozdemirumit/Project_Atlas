from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
DISABLED_UNCONFIGURED = "disabled_unconfigured"
RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class ConnectorInstanceCreationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_installation_receipt_schema: str
    maximum_installation_age_hours: int
    required_assurance_level: AssuranceLevel
    required_installation_store_profile_id: str
    required_installation_artifact_reference_schema: str
    allowed_sdk_profiles: tuple[str, ...]
    allowed_capability_classes: tuple[str, ...]
    required_initial_state: str
    support_group_id: str
    maximum_instance_key_length: int
    maximum_display_name_length: int
    record_schema: str
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
            self.required_installation_receipt_schema,
            self.required_installation_store_profile_id,
            self.required_installation_artifact_reference_schema,
            *self.allowed_sdk_profiles,
            self.required_initial_state,
            self.support_group_id,
            self.record_schema,
            self.signed_by,
        ):
            validate_stable_identifier(value, "connector instance creation policy identifier")
        if (
            self.version != 1
            or not 1 <= self.maximum_installation_age_hours <= 87600
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not self.allowed_sdk_profiles
            or self.allowed_capability_classes != ("C0", "C1")
            or self.required_initial_state != DISABLED_UNCONFIGURED
            or not 3 <= self.maximum_instance_key_length <= 128
            or not 3 <= self.maximum_display_name_length <= 200
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Connector instance creation policy contract is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorInstanceRecord:
    record_id: str
    schema_version: str
    version: int
    source_installation_receipt_id: str
    source_installation_receipt_digest: str
    source_registration_record_id: str
    source_registration_record_digest: str
    source_publication_receipt_id: str
    source_publication_receipt_digest: str
    source_signing_receipt_id: str
    source_signing_receipt_digest: str
    source_approval_request_id: str
    source_approval_request_digest: str
    source_final_validation_id: str
    source_final_validation_digest: str
    source_acquisition_id: str
    source_acquisition_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    package_size_bytes: int
    publisher_id: str
    connector_id: str
    release_version: str
    provenance_digest: str
    manifest_digest: str
    sdk_profile: str
    registry_profile_id: str
    installation_policy_id: str
    installation_policy_digest: str
    installation_store_profile_id: str
    installation_artifact_reference_schema: str
    instance_policy_id: str
    instance_policy_digest: str
    instance_policy_version: str
    instance_id: str
    instance_key: str
    display_name: str
    instance_state: str
    owner_id: str
    support_group_id: str
    created_by: str
    purpose: str
    created_at: datetime
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    package_published: bool = True
    connector_registered: bool = True
    package_installed: bool = True
    instance_created: bool = True
    eligible_for_configuration_governance: bool = True
    promotion_blocked: bool = False
    target_configured: bool = False
    credentials_resolved: bool = False
    connector_enabled: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False
    retired_by: str | None = None
    retired_at: datetime | None = None
    retirement_reason: str | None = None
    retirement_request_fingerprint: str | None = None
    retirement_idempotency_key: str | None = None

    def __post_init__(self) -> None:
        for value in (
            self.record_id,
            self.schema_version,
            self.source_installation_receipt_id,
            self.source_registration_record_id,
            self.source_publication_receipt_id,
            self.source_signing_receipt_id,
            self.source_approval_request_id,
            self.source_final_validation_id,
            self.source_acquisition_id,
            self.organization_id,
            self.environment_id,
            self.publisher_id,
            self.connector_id,
            self.release_version,
            self.sdk_profile,
            self.registry_profile_id,
            self.installation_policy_id,
            self.installation_store_profile_id,
            self.installation_artifact_reference_schema,
            self.instance_policy_id,
            self.instance_policy_version,
            self.instance_id,
            self.instance_key,
            self.instance_state,
            self.owner_id,
            self.support_group_id,
            self.created_by,
        ):
            validate_stable_identifier(value, "connector instance record identifier")
        if (
            self.version not in {1, 2}
            or any(
                _DIGEST.fullmatch(value) is None
                for value in (
                    self.source_installation_receipt_digest,
                    self.source_registration_record_digest,
                    self.source_publication_receipt_digest,
                    self.source_signing_receipt_digest,
                    self.source_approval_request_digest,
                    self.source_final_validation_digest,
                    self.source_acquisition_digest,
                    self.package_digest,
                    self.provenance_digest,
                    self.manifest_digest,
                    self.installation_policy_digest,
                    self.instance_policy_digest,
                    self.canonical_digest,
                    self.request_fingerprint,
                )
            )
            or not 1 <= self.package_size_bytes <= 25_000_000
            or not 3 <= len(self.instance_key) <= 128
            or self.instance_key != self.instance_key.lower()
            or not 3 <= len(self.display_name.strip()) <= 200
            or self.instance_state not in {DISABLED_UNCONFIGURED, RETIRED}
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or self.created_at.tzinfo is None
            or not all(
                (
                    self.package_published,
                    self.connector_registered,
                    self.package_installed,
                    self.instance_created,
                )
            )
            or self.eligible_for_configuration_governance
            != (self.instance_state == DISABLED_UNCONFIGURED)
            or self.promotion_blocked
            or any(
                (
                    self.target_configured,
                    self.credentials_resolved,
                    self.connector_enabled,
                    self.runtime_trust_granted,
                    self.execution_authorized,
                    self.deployment_approved,
                    self.infrastructure_mutation_performed,
                )
            )
        ):
            raise ValueError("Connector instance record violates the authority boundary")
        retirement_values = (
            self.retired_by,
            self.retired_at,
            self.retirement_reason,
            self.retirement_request_fingerprint,
            self.retirement_idempotency_key,
        )
        if self.instance_state == DISABLED_UNCONFIGURED:
            if self.version != 1 or any(value is not None for value in retirement_values):
                raise ValueError("Active connector instance retirement metadata is invalid")
        elif (
            self.version != 2
            or self.retired_by is None
            or self.retired_at is None
            or self.retired_at.tzinfo is None
            or self.retirement_reason is None
            or not 20 <= len(self.retirement_reason.strip()) <= 1000
            or self.retirement_request_fingerprint is None
            or _DIGEST.fullmatch(self.retirement_request_fingerprint) is None
            or self.retirement_idempotency_key is None
            or not 8 <= len(self.retirement_idempotency_key) <= 128
        ):
            raise ValueError("Retired connector instance metadata is invalid")
